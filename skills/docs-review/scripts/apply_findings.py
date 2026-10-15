#!/usr/bin/env python3
"""Apply docs-review findings: mechanical fixes here, the rest to writers.

Phase 6 of docs-review. Reviewers never edit files; this script and the
writer subagents do.

1. Findings with `fixable: auto` and a `suggestion` are applied here, when the
   quoted text still matches the file. Each file is edited from the bottom up,
   so earlier line numbers stay valid. Overlapping fixes are not applied; they
   go to a writer as conflicts.
2. Every other finding that the policy allows is written to disjoint file
   sets (`writer-<i>.json`), one per writer subagent. A file is never in two
   sets, so writers can run in parallel. Each set lists its findings in
   importance order (5 first), the order writers apply them in
   (references/writer.md). Findings without `importance` count as 2.

Python 3.9 or later, stdlib only.

Exit codes: 0 success, 2 usage or input error.
"""

import argparse
import difflib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from findings import fingerprint, needs_input, severity_rank  # noqa: E402
import importance as IMP  # noqa: E402

# Policies decide which findings reach writers.
# input: auto mode. Every finding about the change, except the ones that need
#        an answer from the author or an expert (findings.needs_input). Those
#        stay as comments.
# safe:  only `auto` findings and `suggest` with high confidence (silent mode).
# all:   every finding with a file, for interactive runs where a person reviews the diff.
# `auto` is the old name of `safe`.
POLICIES = ("input", "safe", "auto", "all")


def load_findings(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.stderr.write("error: cannot read findings file {}: {}\n".format(path, exc))
        raise SystemExit(2)
    findings = data.get("findings") if isinstance(data, dict) else data
    if not isinstance(findings, list):
        sys.stderr.write("error: {} has no `findings` list\n".format(path))
        raise SystemExit(2)
    for f in findings:
        if isinstance(f, dict) and not f.get("fingerprint"):
            f["fingerprint"] = fingerprint(f)
    return [f for f in findings if isinstance(f, dict)]


def span(f):
    start = f.get("line")
    if not isinstance(start, int) or start < 1:
        return None
    end = f.get("end_line")
    if not isinstance(end, int) or end < start:
        end = start
    return (start, end)


def is_mechanical(f):
    # No quote means no check that the lines still say what was reviewed: a writer handles it.
    return f.get("fixable") == "auto" and isinstance(f.get("suggestion"), str) and span(f) and bool(f.get("quote"))


def writer_allowed(f, policy):
    if not f.get("file"):
        return False
    if policy == "all":
        return True
    if policy == "input":
        # Old text is not this MR's to fix; questions wait for an answer.
        return f.get("summary_reason") != "existing" and not needs_input(f)
    if f.get("fixable") == "auto":
        return True
    return f.get("fixable") == "suggest" and f.get("confidence") == "high"


def apply_file(path, items):
    """Apply mechanical findings to one file. Return (new_text, applied, rejected)."""
    with open(path, encoding="utf-8") as fh:
        original = fh.read()
    trailing_newline = original.endswith("\n")
    lines = original.split("\n")
    if trailing_newline:
        lines = lines[:-1]

    applied, rejected = [], []
    taken = []  # spans already changed in this file
    # Bottom-up, and the more important (then more severe) finding first when two start on the same line.
    for f in sorted(items, key=lambda x: (-span(x)[0], -IMP.level(x), severity_rank(x.get("severity")))):
        start, end = span(f)
        if end > len(lines):
            rejected.append((f, "lines {}-{} are past the end of the file".format(start, end)))
            continue
        if any(not (end < a or start > b) for a, b in taken):
            rejected.append((f, "overlaps another fix in this run"))
            continue
        current = "\n".join(lines[start - 1:end])
        quote = f.get("quote") or ""
        if quote and quote not in current:
            rejected.append((f, "quoted text no longer matches lines {}-{}".format(start, end)))
            continue
        replacement = f["suggestion"].split("\n")
        lines[start - 1:end] = replacement
        taken.append((start, start + len(replacement) - 1))
        applied.append(f)

    new_text = "\n".join(lines) + ("\n" if trailing_newline else "")
    return original, new_text, applied, rejected


def partition(findings, n):
    """Group findings by file, then balance the files across n writer sets."""
    by_file = {}
    for f in findings:
        by_file.setdefault(f["file"], []).append(f)
    sets = [{"files": [], "findings": []} for _ in range(max(1, n))]
    # Largest files first, each to the set with the fewest findings so far.
    for path in sorted(by_file, key=lambda p: (-len(by_file[p]), p)):
        target = min(sets, key=lambda s: len(s["findings"]))
        target["files"].append(path)
        target["findings"].extend(by_file[path])
    for s in sets:
        s["findings"].sort(key=lambda f: (-IMP.level(f), f["file"], f.get("line") or 0))
    return [s for s in sets if s["files"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--findings", required=True, help="combined findings JSON from combine_findings.py")
    ap.add_argument("--repo", default=".", help="repository root the finding paths are relative to")
    ap.add_argument("--out", default="docs-review-out", help="output directory")
    ap.add_argument("--partition", type=int, default=5, help="maximum number of writer sets (default 5)")
    ap.add_argument("--policy", choices=POLICIES, default="auto",
                    help="which findings reach writers: input (auto mode: all but questions), safe or auto "
                         "(default: auto findings and high-confidence suggestions), or all")
    ap.add_argument("--dry-run", action="store_true", help="write a patch instead of editing files")
    args = ap.parse_args()

    if args.partition < 1:
        print("error: --partition must be 1 or more", file=sys.stderr)
        return 2
    findings = load_findings(args.findings)
    os.makedirs(args.out, exist_ok=True)

    report = {"applied": [], "skipped": [], "conflicts": [], "writer_sets": []}
    to_writers = []
    by_file = {}
    for f in findings:
        if is_mechanical(f):
            by_file.setdefault(f["file"], []).append(f)
        elif writer_allowed(f, args.policy):
            to_writers.append(f)
        elif args.policy == "input":
            report["skipped"].append({"fingerprint": f["fingerprint"], "needs_input": needs_input(f),
                                      "reason": "needs input from the author or an expert" if needs_input(f)
                                      else "old text, not changed by this MR"})
        else:
            report["skipped"].append({"fingerprint": f["fingerprint"],
                                      "reason": "policy {} does not apply {} findings with {} confidence".format(
                                          args.policy, f.get("fixable"), f.get("confidence"))})

    patches = []
    root = os.path.realpath(args.repo)
    for rel, items in sorted(by_file.items()):
        path = os.path.join(args.repo, rel)
        real = os.path.realpath(path)
        if os.path.isabs(rel) or os.path.commonpath([root, real]) != root:
            for f in items:
                report["skipped"].append({"fingerprint": f["fingerprint"], "reason": "file outside the repo: " + rel})
            continue
        if not os.path.isfile(path):
            for f in items:
                report["skipped"].append({"fingerprint": f["fingerprint"], "reason": "file not found: " + rel})
            continue
        original, new_text, applied, rejected = apply_file(path, items)
        for f in applied:
            report["applied"].append({"fingerprint": f["fingerprint"], "file": rel, "line": f["line"]})
        for f, reason in rejected:
            report["conflicts"].append({"fingerprint": f["fingerprint"], "file": rel, "reason": reason})
            to_writers.append(f)  # a writer can resolve it by reading the current text
        if applied:
            patches.extend(difflib.unified_diff(
                original.splitlines(True), new_text.splitlines(True),
                fromfile="a/" + rel, tofile="b/" + rel))
            if not args.dry_run:
                with open(path, "rb") as fh:  # keep the file's own line endings
                    eol = "\r\n" if b"\r\n" in fh.read() else "\n"
                with open(path, "w", encoding="utf-8", newline=eol) as fh:
                    fh.write(new_text)

    for i, s in enumerate(partition(to_writers, args.partition), 1):
        name = "writer-{}.json".format(i)
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "writer": i, "files": s["files"], "findings": s["findings"]}, fh, indent=2)
        report["writer_sets"].append({"file": name, "files": s["files"], "findings": len(s["findings"])})

    if patches:
        with open(os.path.join(args.out, "apply.patch"), "w", encoding="utf-8") as fh:
            fh.writelines(patches)
    report["dry_run"] = args.dry_run
    with open(os.path.join(args.out, "apply-report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:  # a one-line error, not a traceback
        if os.environ.get("DOCS_REVIEW_DEBUG"):
            raise
        sys.stderr.write("{}: error: {}\n".format(sys.argv[0].rsplit("/", 1)[-1], exc))
        sys.exit(2)
