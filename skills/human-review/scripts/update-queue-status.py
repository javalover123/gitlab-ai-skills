#!/usr/bin/env python3
"""
Atomically rewrite a JSONL queue file produced by iteratotron or
bug-burndown, mutating a single entry's `status` and attaching a
`human_decision` field that points at a decision record.

Atomic semantics: read all entries → modify the matched one → write
to a temp file in the same directory → fsync → rename over the
original. Keeps a `.bak` next to the original so a botched mutation
can be recovered by hand.

Usage:
  update-queue-status.py --queue <path> --item-id <id>
                         --new-status <status>
                         --decision-record <path>
                         [--reason <free text>]
                         [--dry-run]

Exit codes:
  0 — entry updated, queue rewritten
  1 — invalid arguments
  2 — queue file not found or unreadable
  3 — item id not found in queue
  4 — entry already had a protected terminal-not-needs_human status; refused
  5 — entry's current status isn't in the human-review-eligible set; refused
      (preserves the prior fix/blocked/skipped decision)
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_NEW_STATUSES = {
    "queued",
    "re-evaluate",
    "blocked",
    "skipped",
    "skipped_recently_complete",
    "requires_human_review",
}

# Statuses that should NEVER be overwritten. If we encounter one of these
# on the matched entry, refuse — the entry already reached an actionable
# terminal state and human-review should not retroactively edit history.
PROTECTED_STATUSES = {
    "complete",
    "fixed",
    "introduced_regression",
}

# Statuses that are valid inputs (i.e. the entry MUST currently be in one
# of these for the mutation to apply).
VALID_CURRENT_STATUSES = {
    "needs_human",
    "requires_human_review",
    "blocked",
}


def read_queue(path):
    entries = []
    raw_lines = path.read_text().splitlines()
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            entries.append(None)  # preserve blank lines
            continue
        entries.append(json.loads(stripped))
    return entries


def find_entry_index(entries, item_id, fingerprint=None, skip_statuses=None):
    """Index of the queue entry matching item_id.

    When item_id is duplicated across entries (e.g. several observations
    sharing one bug_id but distinct fingerprints), pass `fingerprint` to
    disambiguate, and/or `skip_statuses` to ignore entries already moved to
    a given status on a prior call.
    """
    for i, entry in enumerate(entries):
        if entry is None:
            continue
        candidate = (
            entry.get("scope_id")
            or entry.get("bug_id")
            or entry.get("id")
        )
        if candidate != item_id:
            continue
        if skip_statuses and entry.get("status") in skip_statuses:
            continue
        if fingerprint is not None:
            entry_fp = entry.get("fingerprint")
            entry_fps = entry.get("fingerprints") or []
            if fingerprint != entry_fp and fingerprint not in entry_fps:
                continue
        return i
    return None


def atomic_write(path, entries):
    fd, tmp_path = tempfile.mkstemp(
        prefix=".queue-update-",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            for entry in entries:
                if entry is None:
                    fp.write("\n")
                else:
                    fp.write(json.dumps(entry, sort_keys=True) + "\n")
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp_path, str(path))
    except Exception:
        # Best-effort cleanup of the temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queue", required=True)
    p.add_argument("--item-id", required=True)
    p.add_argument(
        "--fingerprint",
        default=None,
        help="disambiguate when several entries share one item-id; matches "
        "the entry whose 'fingerprint' equals this value or whose "
        "'fingerprints' list contains it",
    )
    p.add_argument("--new-status", required=True)
    p.add_argument("--decision-record", required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)

    if args.new_status not in ALLOWED_NEW_STATUSES:
        sys.stderr.write(
            f"new-status '{args.new_status}' not in allowed set: "
            f"{sorted(ALLOWED_NEW_STATUSES)}\n"
        )
        return 1

    queue_path = Path(args.queue)
    if not queue_path.is_file():
        sys.stderr.write(f"queue file not found: {queue_path}\n")
        return 2

    try:
        entries = read_queue(queue_path)
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(f"failed to read queue: {exc}\n")
        return 2

    idx = find_entry_index(entries, args.item_id, fingerprint=args.fingerprint)
    if idx is None:
        suffix = (
            f" with fingerprint '{args.fingerprint}'" if args.fingerprint else ""
        )
        sys.stderr.write(
            f"item id '{args.item_id}'{suffix} not found in {queue_path}\n"
        )
        return 3

    entry = entries[idx]
    current_status = entry.get("status", "unknown")

    if current_status in PROTECTED_STATUSES:
        sys.stderr.write(
            f"refusing to overwrite protected status '{current_status}' "
            f"on item '{args.item_id}'. Decision records can be appended "
            f"manually if needed.\n"
        )
        return 4

    if current_status not in VALID_CURRENT_STATUSES:
        sys.stderr.write(
            f"item '{args.item_id}' has status '{current_status}', which is "
            f"not in the human-review-eligible set "
            f"{sorted(VALID_CURRENT_STATUSES)}. Refusing.\n"
        )
        return 5

    decision_record = Path(args.decision_record)
    if not decision_record.is_file():
        sys.stderr.write(
            f"decision record missing: {decision_record}. "
            f"Write the markdown record BEFORE mutating the queue.\n"
        )
        return 1

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    entry["status"] = args.new_status
    entry["prior_status"] = current_status
    entry["human_decision"] = {
        "decided_at": now,
        "record_path": str(decision_record.resolve()),
        "reason": args.reason,
        "transition": f"{current_status} -> {args.new_status}",
    }

    if args.dry_run:
        sys.stdout.write(json.dumps(entry, sort_keys=True, indent=2) + "\n")
        sys.stderr.write("dry-run — no file written\n")
        return 0

    bak_path = queue_path.with_suffix(queue_path.suffix + ".bak")
    shutil.copy2(str(queue_path), str(bak_path))

    atomic_write(queue_path, entries)

    sys.stderr.write(
        f"updated {args.item_id}: {current_status} -> {args.new_status} "
        f"(backup at {bak_path})\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
