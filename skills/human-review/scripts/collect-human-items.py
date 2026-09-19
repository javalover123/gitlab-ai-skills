#!/usr/bin/env python3
"""
Collect parked (needs_human / requires_human_review) items from active
iteratotron and bug-burndown sessions into a single JSONL stream.

Reads `.iteratotron/CURRENT` and `.bug-burndown/CURRENT`, then enumerates
queue entries whose `status` is in the parked set. Emits one JSON object
per line to stdout with a normalised shape so the SKILL.md interview loop
doesn't have to branch on source-skill differences.

Harness-spawned sessions
------------------------
The `harness-builder` runtime harness drives its burndown bridge by
launching *new* `bug-burndown` sessions per iteration — one per
`.harness/iter-NNN/` capture. Those sessions are NOT pointed at by
`.bug-burndown/CURRENT` (CURRENT tracks the interactive session, not the
harness fleet), so their parked `needs_human` items are invisible to the
default CURRENT-only discovery and silently block the harness loop from
ever reaching its global fixpoint.

`--scan-harness` enumerates every `.bug-burndown/<id>/` session whose
`manifest.yaml` carries `origin: <something>-harness` and collects its parked
items. The harness iteration that spawned each session (parsed from the
manifest's `log_files: .harness/iter-NNN/...` entry) is surfaced in the
`harness_iter` field so the interview can name the run that produced the
item. `--all-sessions` is broader still: it scans every bug-burndown and
iteratotron session directory regardless of origin or CURRENT, useful for
draining a backlog that accumulated across many runs.

Either scan skips a session that already has a non-empty
`human_decisions/` directory unless `--include-decided` is passed, so
re-running the drain doesn't re-surface already-resolved items.

Usage:
  collect-human-items.py [--session-iteratotron <id>] [--session-bug-burndown <id>]
                         [--scan-harness] [--all-sessions] [--include-decided]
                         [--include-blocked] [--repo-root <path>]

Exit codes:
  0 — completed (may have emitted zero items)
  1 — invalid arguments
  2 — repo root not a git repo and no override given

Output schema (one JSON object per line):
  {
    "source_skill":       "iteratotron" | "bug-burndown",
    "session_id":         "<session id>",
    "item_id":            "<scope_id or bug_id>",
    "status":             "needs_human" | "requires_human_review" | "blocked",
    "kind":               "<scope.kind or bug.kind>",
    "priority":           "<P0..P3 or severity>",
    "title":              "<one-line title>",
    "linked_artefacts":   ["<artefact_id1>", "<artefact_id2>", ...],
    "attempt_count":      <int>,
    "last_error":         "<short string>",
    "queue_path":         "<absolute path to queue.jsonl or scope_queue.jsonl>",
    "needs_human_dir":    "<absolute path to needs_human/<id>/ if present, else null>",
    "origin":             "<manifest origin, e.g. vulnmapper-harness, or null>",
    "harness_iter":       "<iter-NNN that spawned a harness session, or null>",
    "raw":                { ...original queue entry, opaque... }
  }
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

PARKED_STATUSES = {"needs_human", "requires_human_review"}
PARKED_PLUS_BLOCKED = PARKED_STATUSES | {"blocked"}

ITERATOTRON_QUEUE_NAME = "scope_queue.jsonl"
BUG_BURNDOWN_QUEUE_NAME = "queue.jsonl"

ITER_RE = re.compile(r"\.harness/(iter-\d+)")


def is_harness_origin(origin, extra_origins):
    """True if a session's manifest origin marks it harness-spawned.

    Repos tag harness-spawned sessions with a project-specific origin ending
    in "-harness" (e.g. "vulnmapper-harness"), so the suffix is the general
    match. Pass extra exact origins via --harness-origin for anything that
    doesn't follow the convention.
    """
    if not origin:
        return False
    if origin in extra_origins:
        return True
    return origin.endswith("-harness")
ORIGIN_RE = re.compile(r"^\s*origin:\s*(\S+)", re.MULTILINE)


def read_jsonl(path):
    """Yield parsed entries from a JSONL file, skipping malformed lines."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def read_manifest_meta(session_dir):
    """Return (origin, harness_iter) parsed from a session's manifest.yaml.

    `origin` is the manifest's `origin:` value (e.g. "vulnmapper-harness") or
    None. `harness_iter` is the first `.harness/iter-NNN` reference found
    anywhere in the manifest (usually under `log_files:`) or None. We parse
    with regexes rather than a YAML dependency — the two fields we need are
    flat scalars / a path list, so this stays dependency-free and tolerant
    of a slightly malformed manifest.
    """
    manifest = session_dir / "manifest.yaml"
    if not manifest.is_file():
        return None, None
    text = manifest.read_text()
    origin_m = ORIGIN_RE.search(text)
    iter_m = ITER_RE.search(text)
    origin = origin_m.group(1).strip().strip('"').strip("'") if origin_m else None
    harness_iter = iter_m.group(1) if iter_m else None
    return origin, harness_iter


def item_has_decision(session_dir, item_id):
    """True if a decision record already exists for this specific item.

    Records are written as human_decisions/<item_id>.md (see Phase 5). We match
    the stem so an item is skipped only when its own decision exists — never
    because a sibling in the same session was decided.
    """
    hd = session_dir / "human_decisions"
    if not hd.is_dir():
        return False
    return any(p.stem == item_id for p in hd.iterdir() if p.is_file())


def session_for(skill_root, override):
    """Return (session_id, session_dir) or (None, None) if not active."""
    if override:
        session_id = override
    else:
        current = skill_root / "CURRENT"
        if not current.is_file():
            return None, None
        session_id = current.read_text().strip()
    if not session_id:
        return None, None
    session_dir = skill_root / session_id
    if not session_dir.is_dir():
        return None, None
    return session_id, session_dir


def normalise_iteratotron(entry, session_id, session_dir, origin, harness_iter):
    item_id = entry.get("scope_id") or entry.get("id") or "unknown"
    needs_human_dir = session_dir / "needs_human" / item_id
    return {
        "source_skill": "iteratotron",
        "session_id": session_id,
        "item_id": item_id,
        "status": entry.get("status", "unknown"),
        "kind": entry.get("kind", "scope"),
        "priority": entry.get("priority", "P?"),
        "title": entry.get("title") or entry.get("path") or item_id,
        "linked_artefacts": entry.get("linked_artefacts", []),
        "attempt_count": int(entry.get("attempt_count", 0) or 0),
        "last_error": entry.get("last_error", ""),
        "queue_path": str((session_dir / ITERATOTRON_QUEUE_NAME).resolve()),
        "needs_human_dir": (
            str(needs_human_dir.resolve()) if needs_human_dir.is_dir() else None
        ),
        "origin": origin,
        "harness_iter": harness_iter,
        "raw": entry,
    }


def normalise_bug_burndown(entry, session_id, session_dir, origin, harness_iter):
    item_id = entry.get("bug_id") or entry.get("id") or "unknown"
    needs_human_dir = session_dir / "needs_human" / item_id
    return {
        "source_skill": "bug-burndown",
        "session_id": session_id,
        "item_id": item_id,
        "status": entry.get("status", "unknown"),
        "kind": entry.get("kind", "bug"),
        "priority": entry.get("severity", "unknown"),
        "title": entry.get("title") or entry.get("description") or item_id,
        "linked_artefacts": entry.get("linked_artefacts", []),
        "attempt_count": int(entry.get("attempt_count", 0) or 0),
        "last_error": entry.get("last_error", ""),
        "queue_path": str((session_dir / BUG_BURNDOWN_QUEUE_NAME).resolve()),
        "needs_human_dir": (
            str(needs_human_dir.resolve()) if needs_human_dir.is_dir() else None
        ),
        "origin": origin,
        "harness_iter": harness_iter,
        "raw": entry,
    }


def collect(session_dir, queue_name, normaliser, session_id, parked_set,
            include_decided=False):
    queue_path = session_dir / queue_name
    origin, harness_iter = read_manifest_meta(session_dir)
    items = []
    for entry in read_jsonl(queue_path):
        status = entry.get("status", "")
        if status not in parked_set:
            continue
        item = normaliser(entry, session_id, session_dir, origin, harness_iter)
        # Skip only items that already have their own decision record, not the
        # whole session — otherwise undecided siblings are silently dropped.
        if not include_decided and item_has_decision(session_dir, item["item_id"]):
            continue
        items.append(item)
    return items


def discover_sessions(skill_root, queue_name):
    """Yield (session_id, session_dir) for every session directory under a
    skill root that contains the expected queue file. Sorted by name so the
    output is deterministic (session ids are timestamp-prefixed)."""
    if not skill_root.is_dir():
        return
    for child in sorted(skill_root.iterdir()):
        if not child.is_dir():
            continue
        if (child / queue_name).is_file():
            yield child.name, child


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session-iteratotron", default=None)
    p.add_argument("--session-bug-burndown", default=None)
    p.add_argument(
        "--scan-harness",
        action="store_true",
        help="scan every .bug-burndown session whose manifest origin marks "
        "it harness-spawned (any origin ending "
        "in '-harness' such as vulnmapper-harness, or one named via "
        "--harness-origin) \u2014 harness-spawned sessions, not just CURRENT",
    )
    p.add_argument(
        "--harness-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="additional manifest origin value to treat as harness-spawned "
        "(repeatable); use for project-specific harness origins not matching "
        "the '-harness' suffix heuristic",
    )
    p.add_argument(
        "--all-sessions",
        action="store_true",
        help="scan every iteratotron and bug-burndown session directory "
        "regardless of origin or CURRENT (broadest backlog drain)",
    )
    p.add_argument(
        "--include-decided",
        action="store_true",
        help="also surface items from sessions that already have a "
        "non-empty human_decisions/ directory",
    )
    p.add_argument("--include-blocked", action="store_true")
    p.add_argument("--repo-root", default=".")
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        sys.stderr.write(f"repo root not found: {repo_root}\n")
        return 2
    os.chdir(repo_root)

    parked_set = PARKED_PLUS_BLOCKED if args.include_blocked else PARKED_STATUSES

    iter_root = Path(".iteratotron")
    bb_root = Path(".bug-burndown")

    # Build the list of (skill, session_id, session_dir, queue_name, normaliser)
    # tuples to scan. A session is keyed by its resolved directory so the
    # same session can't be enumerated twice when multiple flags select it.
    targets = {}

    def add_target(skill, session_id, session_dir, queue_name, normaliser):
        if not session_dir or not session_dir.is_dir():
            return
        key = str(session_dir.resolve())
        targets.setdefault(
            key, (skill, session_id, session_dir, queue_name, normaliser)
        )

    if args.all_sessions:
        # Broadest: every session dir under both roots.
        for sid, sdir in discover_sessions(iter_root, ITERATOTRON_QUEUE_NAME):
            add_target(
                "iteratotron", sid, sdir, ITERATOTRON_QUEUE_NAME,
                normalise_iteratotron,
            )
        for sid, sdir in discover_sessions(bb_root, BUG_BURNDOWN_QUEUE_NAME):
            add_target(
                "bug-burndown", sid, sdir, BUG_BURNDOWN_QUEUE_NAME,
                normalise_bug_burndown,
            )
    else:
        # CURRENT (or explicit override) sessions always considered.
        iter_session, iter_dir = session_for(iter_root, args.session_iteratotron)
        bb_session, bb_dir = session_for(bb_root, args.session_bug_burndown)
        add_target(
            "iteratotron", iter_session, iter_dir, ITERATOTRON_QUEUE_NAME,
            normalise_iteratotron,
        )
        add_target(
            "bug-burndown", bb_session, bb_dir, BUG_BURNDOWN_QUEUE_NAME,
            normalise_bug_burndown,
        )
        if args.scan_harness:
            # Every bug-burndown session whose manifest origin is the harness.
            extra_origins = set(args.harness_origin)
            for sid, sdir in discover_sessions(bb_root, BUG_BURNDOWN_QUEUE_NAME):
                origin, _ = read_manifest_meta(sdir)
                if is_harness_origin(origin, extra_origins):
                    add_target(
                        "bug-burndown", sid, sdir, BUG_BURNDOWN_QUEUE_NAME,
                        normalise_bug_burndown,
                    )

    all_items = []
    for skill, sid, sdir, queue_name, normaliser in targets.values():
        all_items.extend(
            collect(sdir, queue_name, normaliser, sid, parked_set,
                    include_decided=args.include_decided)
        )

    # Stable sort: source_skill, then priority (P0 < P1 < ... < P?), then item_id
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    severity_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }

    def sort_key(item):
        prio = item["priority"]
        prio_rank = priority_order.get(
            prio, severity_order.get(str(prio).lower(), 99)
        )
        return (item["source_skill"], prio_rank, item["item_id"])

    all_items.sort(key=sort_key)

    for item in all_items:
        sys.stdout.write(json.dumps(item, sort_keys=True) + "\n")

    sessions_with_items = len({i["session_id"] for i in all_items})
    extra_origins = set(args.harness_origin)
    harness_items = sum(
        1 for i in all_items if is_harness_origin(i.get("origin"), extra_origins)
    )
    if args.all_sessions:
        mode = "all-sessions"
    elif args.scan_harness:
        mode = "scan-harness"
    else:
        mode = "current"
    decided_note = "" if args.include_decided else " (items with an existing decision skipped; pass --include-decided to re-surface)"
    sys.stderr.write(
        f"collected {len(all_items)} parked item(s) across "
        f"{sessions_with_items} session(s) [mode={mode}, "
        f"{harness_items} from harness-spawned sessions]{decided_note}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
