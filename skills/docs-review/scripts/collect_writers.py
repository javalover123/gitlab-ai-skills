#!/usr/bin/env python3
"""Collect a fix cycle: what the writers applied, and what is left to post.

Auto mode runs a writer step after every review: apply_findings.py applies
the mechanical fixes and splits the rest into writer sets, the writers apply
their sets, and the orchestrator commits the result. This script then reads
the writers' return contracts and splits the findings:

- `applied.json`: every finding that is now fixed in `--head`, the commit
  with the fixes. post_review.py lists them in the summary and resolves our
  earlier threads that they fix. Applied findings are never posted inline.
- `remaining.json`: a findings document with only what still needs a
  person, moved to `--head`, so comments land on the latest diff version:
  - findings that need input (lib/findings.needs_input), and findings a
    writer could not apply because they need a decision or conflict: inline;
  - importance 1 and 2 findings a writer skipped on purpose: summary only;
  - findings whose quote is gone from `--head`: dropped, and listed in the
    report, because the text they were about changed.

Usage:
  collect_writers.py --findings out/findings.json --apply-dir out/apply \\
      --repo . --head <sha> --out-dir out/cycle-1

Python 3.9 or later, stdlib only. Exit codes: 0 success, 2 usage error.
"""

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib import findings as F  # noqa: E402
from lib import gitdiff  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def writer_results(apply_dir):
    """{fingerprint: result} from every writer-<i>-result.json, plus the
    mechanical fixes apply_findings.py made itself."""
    out = {}
    report_path = os.path.join(apply_dir, "apply-report.json")
    if os.path.isfile(report_path):
        for a in load(report_path).get("applied") or []:
            out[a["fingerprint"]] = {"status": "applied", "reason": "mechanical fix"}
    for path in sorted(glob.glob(os.path.join(apply_dir, "writer-*-result.json"))):
        try:
            doc = load(path)
        except (OSError, ValueError) as exc:
            raise ValueError("cannot read {}: {}".format(path, exc))
        for r in doc.get("results") or []:
            if isinstance(r, dict) and r.get("fingerprint"):
                out[r["fingerprint"]] = r
    return out


def remap(f, text):
    """Move a finding to the line its quote is on in `text`, nearest its old
    line. False when the quote is gone."""
    quote = f.get("quote") or ""
    if not quote or text is None:
        return False
    starts, i = [], text.find(quote)
    while i != -1:
        starts.append(text.count("\n", 0, i) + 1)
        i = text.find(quote, i + 1)
    if not starts:
        return False
    old = f.get("line") or 1
    line = min(starts, key=lambda n: abs(n - old))
    span = (f.get("end_line") or old) - old
    f["line"], f["end_line"] = line, line + max(span, quote.count("\n"))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--findings", required=True, help="findings.json from combine_findings.py")
    ap.add_argument("--apply-dir", required=True, help="apply_findings.py --out directory with writer results")
    ap.add_argument("--repo", default=".", help="repository with --head")
    ap.add_argument("--head", required=True, help="the commit with the fixes")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    try:
        doc = F.load_doc(args.findings)
        results = writer_results(args.apply_dir)
    except (OSError, ValueError) as exc:
        sys.stderr.write("collect_writers: {}\n".format(exc))
        return 2
    head = gitdiff.run(args.repo, ["rev-parse", "--verify", args.head + "^{commit}"], check=False).stdout.strip()
    if not head:
        sys.stderr.write("collect_writers: {} is not a commit in {}\n".format(args.head, args.repo))
        return 2

    cache = {}

    def text_at(path):
        if path not in cache:
            res = gitdiff.run(args.repo, ["show", "{}:{}".format(head, path)], check=False)
            cache[path] = res.stdout if res.returncode == 0 else None
        return cache[path]

    applied, remaining, dropped, invalid = [], [], [], []
    capped = [f for f in doc.get("deferred") or [] if f.get("deferred_reason") == "safety-cap"]
    for f in doc["findings"] + capped:
        fp = f.get("fingerprint") or F.fingerprint(f)
        r = results.get(fp) or {}
        status = r.get("status")
        if status == "applied":
            applied.append({"fingerprint": fp, "id": f["id"], "file": f["file"], "line": f.get("line"),
                            "message": f.get("message"), "importance": f.get("importance")})
            continue
        g = dict(f)
        g.pop("deferred_reason", None)  # a capped finding is a finding again; post_review applies its own cap
        reason = str(r.get("reason") or "")
        if status == "invalid":
            invalid.append({"fingerprint": fp, "id": f["id"], "file": f["file"], "line": f.get("line"),
                            "reason": reason})
            continue
        if status == "generated":
            g["summary_only"], g["summary_reason"] = True, "generated"
            g["message"] = "{} Fix it in the source of the generated block.".format(f["message"].rstrip())
        if status == "skipped" and reason.startswith("low importance"):
            g["summary_only"], g["summary_reason"] = True, "polish"
        elif status in ("skipped", "conflict") and not F.needs_input(f) and reason \
                and not reason.startswith("quote not found"):
            # A writer needs a decision: say why it was not applied.
            g["needs_input"] = True
            g["message"] = "{} Not applied automatically: {}".format(f["message"].rstrip(), reason.rstrip("."))
        if not remap(g, text_at(g["file"])):
            if F.needs_input(g) and not g.get("summary_only"):
                g["summary_only"], g["summary_reason"] = True, "moved"
            else:
                dropped.append({"fingerprint": fp, "id": f["id"], "file": f["file"], "line": f.get("line"),
                                "reason": "the quoted text changed in {}".format(head[:12])})
                continue
        remaining.append(g)

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "applied.json"), "w", encoding="utf-8") as fh:
        json.dump({"head": head, "applied": applied, "dropped": dropped, "invalid": invalid}, fh, indent=2)
    target = dict(doc.get("target") or {}, head=head)
    out = dict(doc, target=target, findings=remaining,
               deferred=[f for f in doc.get("deferred") or [] if f.get("deferred_reason") != "safety-cap"])
    F.dump(out, os.path.join(args.out_dir, "remaining.json"))
    sys.stdout.write("applied {}, left {} ({} need input), dropped {} (text changed), {} wrong; fixes in {}\n".format(
        len(applied), len(remaining), sum(1 for g in remaining if F.needs_input(g) and not g.get("summary_only")),
        len(dropped), len(invalid), head[:12]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:  # a one-line error, not a traceback
        if os.environ.get("DOCS_REVIEW_DEBUG"):
            raise
        sys.stderr.write("{}: error: {}\n".format(sys.argv[0].rsplit("/", 1)[-1], exc))
        sys.exit(2)
