#!/usr/bin/env bash
# shellcheck disable=SC2016  # single-quoted Python and Markdown with literal backticks are the point
# Tests scripts/post_review.py guardrails with a stubbed glab. No network, no real writes.
set -Eeuo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scripts="$here/../scripts"
fx="$here/fixtures/post_review"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
failures=0

ok() { echo "ok - $1"; }
fail() {
  echo "FAIL - $1"
  failures=$((failures + 1))
}
writes() { grep -Ec '^(POST|PUT|PATCH|DELETE) ' "$STUB_DIR/calls" || true; }

stub="$tmp/stub"
mkdir -p "$stub"
cp -R "$fx/responses" "$stub/responses"
cp "$fx/routes.tsv" "$stub/routes"
export STUB_DIR="$stub"
glab="$here/fixtures/glab-stub/glab"

# Existing MR notes: our summary note (id 555), a summary-looking note by
# someone else, one finding already posted, and one in a resolved thread.
python3 - "$scripts" "$fx/findings.json" "$stub/responses" << 'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
from lib import findings as F
doc = json.load(open(sys.argv[2]))
fp = dict((f["id"], F.fingerprint(f)) for f in doc["findings"])
pre = ":robot: AI-generated docs review"
disc = [
    {"id": "d-sum", "notes": [{"id": 555, "body": pre + "\n<!-- docs-review:summary -->\nold summary",
                               "author": {"username": "docs-reviewer"}, "resolvable": False}]},
    {"id": "d-spoof", "notes": [{"id": 556, "body": pre + "\n<!-- docs-review:summary -->\nnot ours",
                                 "author": {"username": "someone-else"}, "resolvable": False}]},
    {"id": "d-dup", "notes": [{"id": 600, "body": pre + "\n\nold\n\n<!-- docs-review:fp=%s -->" % fp["style.voice"],
                               "author": {"username": "docs-reviewer"}, "resolvable": True, "resolved": False}]},
    {"id": "d-res", "notes": [{"id": 601, "body": pre + "\n\nold\n\n<!-- docs-review:fp=%s -->" % fp["style.tense"],
                               "author": {"username": "docs-reviewer"}, "resolvable": True, "resolved": True}]},
]
json.dump(disc, open(sys.argv[3] + "/discussions.json", "w"))
json.dump([], open(sys.argv[3] + "/discussions-empty.json", "w"))
PY
cp "$stub/responses/discussions.json" "$stub/responses/discussions-full.json"

run_post() { # args...
  rc=0
  : > "$stub/calls"
  rm -rf "$stub/bodies"
  python3 "$scripts/post_review.py" "$fx/findings.json" --project example-org/example-docs --mr 42 \
    --glab "$glab" --tw tw-person "$@" > "$tmp/stdout" 2> "$tmp/stderr" || rc=$?
}
bodies_assert() { # NAME EXPR over `bodies` (list of dicts) and `calls` (list of "METHOD endpoint")
  if python3 - "$stub" "$2" << 'PY'; then ok "$1"; else fail "$1"; fi
import glob, json, os, re, sys
stub, expr = sys.argv[1], sys.argv[2]
bodies = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(stub, "bodies", "*.json")))]
calls = [l.strip() for l in open(os.path.join(stub, "calls")) if l.strip()]
sys.exit(0 if eval(expr) else 1)
PY
}

# 1. Dry-run: payloads and preview, zero write calls.
run_post --mode auto --dry-run --out "$tmp/dry"
if [ "$rc" -eq 1 ]; then ok "dry-run exits 1 because a blocker exists"; else fail "dry-run exit $rc: $(cat "$tmp/stderr")"; fi
if [ "$(writes)" -eq 0 ]; then ok "dry-run makes zero write calls"; else fail "dry-run wrote: $(cat "$stub/calls")"; fi
if [ -f "$tmp/dry/preview.md" ] && [ -f "$tmp/dry/payloads/001.json" ]; then
  ok "dry-run writes payload files and preview.md"
else
  fail "dry-run output files missing"
fi
if grep -q 'Summary note: update' "$tmp/dry/preview.md"; then ok "dry-run plans to update the existing summary"; else fail "preview summary action"; fi

# 2. Auto mode: updates our summary note (PUT), never creates a second one.
run_post --mode auto
bodies_assert "auto mode updates the existing summary note with PUT and creates no new note" \
  'sum(1 for c in calls if c.startswith("PUT ") and c.endswith("/notes/555")) == 1 and not any(c.startswith("POST ") and c.endswith("/notes") for c in calls)'
bodies_assert "posts 3 inline discussions (positioned findings minus duplicates)" \
  'sum(1 for c in calls if c.startswith("POST ") and c.endswith("/discussions")) == 3'
bodies_assert "every write is on the allowlist (no approve, merge, labels, state)" \
  'all(re.match(r"^(POST projects/[^/]+/merge_requests/42/(notes|discussions)|PUT projects/[^/]+/merge_requests/42/notes/555)$", c) for c in calls if not c.startswith("GET "))'
bodies_assert "every body starts with the AI-generated prefix" \
  'bodies and all(b["body"].startswith(":robot: AI-generated docs review") for b in bodies)'
bodies_assert "inline bodies carry a fingerprint marker" \
  'all(re.search(r"<!-- docs-review:fp=[0-9a-f]{40} -->$", b["body"]) for b in bodies if "position" in b)'
bodies_assert "skips findings already posted or in resolved threads" \
  'not any("Use active voice." == b["body"].split(": ", 1)[-1].split("\n")[0] or "present tense" in b["body"] for b in bodies if "position" in b)'
bodies_assert "inline position uses the latest MR version SHAs and new_line" \
  'all(b["position"]["head_sha"].startswith("ccc") and b["position"]["base_sha"].startswith("aaa") and b["position"]["start_sha"].startswith("bbb") and b["position"]["new_path"] == "doc/a.md" for b in bodies if "position" in b)'
bodies_assert "unchanged context line gets old_line too" \
  'any(b["position"]["new_line"] == 1 and b["position"].get("old_line") == 1 for b in bodies if "position" in b)'
bodies_assert "suggestion block uses the GitLab suggestion syntax" \
  'any("```suggestion:-0+0\nUse the new tool.\n```" in b["body"] for b in bodies)'
bodies_assert "mentions stay within 5 distinct people and skip the MR author" \
  'len(set(u for b in bodies for u in re.findall(r"(?<![\w`])@([A-Za-z0-9_.-]+)", b["body"]))) <= 5 and not any(re.search(r"(?<![\w`])@mr-author", b["body"]) for b in bodies)'
bodies_assert "at most 2 people mentioned per finding" \
  'all(len(re.findall(r"(?<![\w`])@sme-", b["body"])) <= 2 for b in bodies if "position" in b)'
bodies_assert "tier high names the technical writer in backticks, without a mention" \
  'any("human technical writer" in b["body"] and "`tw-person`" in b["body"] and "@tw-person" not in b["body"] for b in bodies if "position" not in b)'
# Without --tw, the writer comes from the triage record in findings.json.
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); d.setdefault("target", {}).update(tier="high", technical_writer="tw-from-triage"); json.dump(d, open(sys.argv[2], "w"))' "$fx/findings.json" "$tmp/tw-findings.json"
python3 "$scripts/post_review.py" "$tmp/tw-findings.json" --project example-org/example-docs --mr 42 \
  --glab "$glab" --dry-run --out "$tmp/tw-out" > /dev/null 2>&1 || true
if grep -rqF '`tw-from-triage`' "$tmp/tw-out"; then ok "without --tw, the triage writer is named"; else fail "triage writer not named"; fi
bodies_assert "finding text cannot mention people, run quick actions, or spoof markers" \
  'not any(re.search(r"(?<![\w`])@everyone", b["body"]) or re.search(r"(?m)^\s*/approve", b["body"]) or b["body"].count("<!-- docs-review:summary -->") > (0 if "position" in b else 1) for b in bodies)'
bodies_assert "preservation facts are collapsed in a details block" \
  'any("<details><summary>Facts this change must keep (1)</summary>" in b["body"] and "the job runs nightly" in b["body"] for b in bodies)'
bodies_assert "findings outside the diff go into the summary" \
  'any("descriptive page title" in b["body"] and "doc/other.md:7" in b["body"] for b in bodies if "position" not in b)'

# 3. No existing summary note: exactly one POST to notes.
cp "$stub/responses/discussions-empty.json" "$stub/responses/discussions.json"
run_post --mode auto
bodies_assert "creates exactly one summary note when none exists" \
  'sum(1 for c in calls if c.startswith("POST ") and c.endswith("/notes")) == 1 and not any(c.startswith("PUT ") for c in calls)'
cp "$stub/responses/discussions-full.json" "$stub/responses/discussions.json"

# 5. Interactive without --yes: preview only.
run_post
if [ "$(writes)" -eq 0 ] && grep -q 'rerun with --yes' "$tmp/stdout"; then
  ok "interactive mode without --yes posts nothing"
else
  fail "interactive preview wrote or missed the hint"
fi
DOCS_REVIEW_MODE=auto run_post
if [ "$(writes)" -gt 0 ]; then ok "DOCS_REVIEW_MODE=auto selects auto mode"; else fail "env mode"; fi
run_post --yes
if [ "$(writes)" -gt 0 ]; then ok "interactive mode with --yes posts"; else fail "interactive --yes did not post"; fi

# 6. --summary-only posts no inline discussions.
run_post --mode auto --summary-only
bodies_assert "--summary-only posts only the summary" \
  'not any(c.endswith("/discussions") and c.startswith("POST ") for c in calls) and sum(1 for c in calls if c.startswith("PUT ")) == 1'

# 7. Merged MR: no posting in auto mode.
sed -e 's|responses/mr.json|responses/mr-merged.json|' "$fx/routes.tsv" > "$stub/routes"
run_post --mode auto
if [ "$(writes)" -eq 0 ]; then ok "does not post on a merged MR"; else fail "posted on a merged MR"; fi
cp "$fx/routes.tsv" "$stub/routes"

# 8. Reviewed head picks the MR diff version; same-position findings fold into
#    one comment; summary_only and deferred findings are never inline.
{
  printf 'GET\t^user$\tresponses/user.json\n'
  printf 'GET\t^projects/example-org%%2Fexample-docs/merge_requests/42$\tresponses/mr.json\n'
  printf 'GET\t^projects/example-org%%2Fexample-docs/merge_requests/42/versions(\\?.*)?$\tresponses/versions-two.json\n'
  printf 'GET\t^projects/example-org%%2Fexample-docs/merge_requests/42/versions/1$\tresponses/version-1.json\n'
  printf 'GET\t^projects/example-org%%2Fexample-docs/merge_requests/42/discussions\\?\tresponses/discussions-empty.json\n'
  printf 'POST\t^projects/example-org%%2Fexample-docs/merge_requests/42/discussions$\tresponses/created.json\n'
  printf 'POST\t^projects/example-org%%2Fexample-docs/merge_requests/42/notes$\tresponses/created.json\n'
} > "$stub/routes"
run_fold() { # args...
  rc=0
  : > "$stub/calls"
  rm -rf "$stub/bodies"
  python3 "$scripts/post_review.py" "$fx/findings-fold.json" --project example-org/example-docs --mr 42 \
    --glab "$glab" --mode auto "$@" > "$tmp/stdout" 2> "$tmp/stderr" || rc=$?
}
run_fold
bodies_assert "positions use the diff version whose head is the reviewed head (target.head)" \
  'any(c.endswith("/versions/1") for c in calls) and not any("/diffs" in c for c in calls) and all(b["position"]["head_sha"].startswith("ddd") and b["position"]["start_sha"].startswith("999") for b in bodies if "position" in b)'
bodies_assert "two findings on one line fold into one comment with one suggestion block" \
  'sum(1 for b in bodies if "position" in b and b["position"]["new_line"] == 2) == 1 and [b["body"].count("suggestion:-0+") for b in bodies if "position" in b and b["position"]["new_line"] == 2] == [1]'
bodies_assert "a folded comment carries every fingerprint in its marker" \
  'any(re.search(r"<!-- docs-review:fp=[0-9a-f]{40},[0-9a-f]{40} -->$", b["body"]) for b in bodies if "position" in b)'
bodies_assert "merge alternatives are one line each, not suggestions" \
  'any("- Alternative (`brevity.cut`): Cut the windup." in b["body"] and "Items:" not in b["body"] for b in bodies if "position" in b)'
bodies_assert "summary_only findings go to the summary, never inline" \
  'not any("brevity.long-intro" in b["body"] for b in bodies if "position" in b) and any("brevity.long-intro" in b["body"] for b in bodies if "position" not in b)'
bodies_assert "deferred findings are never posted" \
  'not any("style.deferred-only" in b["body"] for b in bodies) and any("- 1 finding(s) kept in the report." in b["body"] for b in bodies if "position" not in b)'
bodies_assert "the MR author is never mentioned as an SME" \
  'any(re.search(r"(?<![\w`])@sme-ok", b["body"]) for b in bodies) and not any(re.search(r"(?<![\w`])@mr-author", b["body"]) for b in bodies)'
run_fold --head-sha eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
bodies_assert "a reviewed head that is not an MR version posts nothing inline and says why" \
  'not any("position" in b for b in bodies) and any("is not a diff version of this MR" in b["body"] for b in bodies)'
# Repeats of one rule post as one comment with "Also on lines"; a location
# group (merge `spot`) shares one comment; conflicts are noted; an
# alternative's multi-line suggestion is never posted.
python3 - "$tmp/groups.json" << 'PY'
import json, sys
def mk(rid, line, sugg=None, **kw):
    f = {"id": rid, "reviewer": rid.split(".")[0], "severity": "minor", "confidence": "high", "file": "doc/a.md",
         "line": line, "end_line": line, "quote": "q%d %s" % (line, rid), "message": "Message for %s." % rid,
         "suggestion": sugg, "fixable": "suggest" if sugg else "manual", "source": "https://docs.gitlab.com/s",
         "deterministic": False}
    f.update(kw)
    f["fingerprint"] = ("%s%d" % (rid.replace(".", ""), line)).encode().hex()[:40].ljust(40, "0")
    return f
bold = [mk("style.bold", n, "plain %d" % n, group="g1", group_size=3) for n in (1, 3, 4)]
bold[0]["spot"] = bold[0]["fingerprint"][:12]
cut = mk("brevity.cut", 2, "", severity="major", alternatives=[
    {"id": "style.rewrite", "reviewer": "style", "message": "Rewrite it.", "suggestion": "first line\n  indented\nlast"}])
keep = mk("style.acronyms", 2)
cut["spot"] = keep["spot"] = cut["fingerprint"][:12]
cut["conflicts_with"] = [keep["fingerprint"]]
keep["conflicts_with"] = [cut["fingerprint"]]
json.dump({"version": 1, "target": {"project": "example-org/example-docs", "mr": 42, "tier": "medium",
                                    "head": "d" * 40}, "findings": bold + [cut, keep], "deferred": []},
          open(sys.argv[1], "w"))
PY
rc=0
: > "$stub/calls"
rm -rf "$stub/bodies"
python3 "$scripts/post_review.py" "$tmp/groups.json" --project example-org/example-docs --mr 42 --glab "$glab" --mode auto \
  > "$tmp/stdout" 2> "$tmp/stderr" || rc=$?
bodies_assert "repeats of one rule post as one comment on the first line, with Also on lines" \
  'sum(1 for b in bodies if "position" in b and "style.bold" in b["body"]) == 1 and any(b["position"]["new_line"] == 1 and "Also on lines 3, 4." in b["body"] for b in bodies if "position" in b)'
bodies_assert "a repeat comment carries every fingerprint of the group" \
  'any(len(re.search(r"docs-review:fp=([0-9a-f,]+)", b["body"]).group(1).split(",")) == 3 for b in bodies if "position" in b and "style.bold" in b["body"])'
bodies_assert "a location group shares one comment and notes the conflict" \
  '[b["position"]["new_line"] for b in bodies if "position" in b and "brevity.cut" in b["body"]] == [2] and any("style.acronyms" in b["body"] and "Conflict: `brevity.cut` and `style.acronyms` (in this comment)" in b["body"] for b in bodies if "position" in b)'
bodies_assert "an alternative with a multi-line suggestion is one line, without its text" \
  'any("- Alternative (`style.rewrite`): Rewrite it." in b["body"] and "first line" not in b["body"] for b in bodies if "position" in b)'

# A rerun finds both fingerprints of a folded comment.
python3 - "$scripts" "$fx/findings-fold.json" "$stub/responses" << 'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
from lib import findings as F
doc = json.load(open(sys.argv[2]))
fps = ",".join(F.fingerprint(f) for f in doc["findings"][:2])
body = ":robot: AI-generated docs review\n\nold\n\n<!-- docs-review:fp=%s -->" % fps
json.dump([{"id": "d1", "notes": [{"id": 700, "body": body, "author": {"username": "docs-reviewer"},
                                   "resolvable": True, "resolved": False}]}],
          open(sys.argv[3] + "/discussions-folded.json", "w"))
PY
sed -e 's|responses/discussions-empty.json|responses/discussions-folded.json|' "$stub/routes" > "$stub/routes.new"
mv "$stub/routes.new" "$stub/routes"
run_fold --dry-run --out "$tmp/fold"
if grep -qF 'Skipped (already posted): 2' "$tmp/fold/preview.md"; then
  ok "a rerun skips every finding in an earlier folded comment"
else
  fail "folded fingerprints not recognized: $(cat "$tmp/fold/preview.md")"
fi
cp "$fx/routes.tsv" "$stub/routes"

# 8b. Round 2: severe tier mentions the writer; versions are paginated; purged
#     version diffs are rebuilt from repository/compare, and a failed rebuild
#     exits 2 loudly instead of moving findings to the summary.
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); d["target"]["tier"]="severe"; json.dump(d, open(sys.argv[2], "w"))' "$fx/findings.json" "$tmp/severe.json"
python3 "$scripts/post_review.py" "$tmp/severe.json" --project example-org/example-docs --mr 42 \
  --glab "$glab" --tw tw-person --mode auto --dry-run --out "$tmp/severe" > /dev/null 2>&1 || true
if grep -qF '@tw-person' "$tmp/severe/payloads/"*.json; then ok "tier severe mentions the technical writer"; else fail "severe TW mention"; fi
fold_routes() { # versions-file version-file [compare-file compare-exit]
  {
    printf 'GET\t^user$\tresponses/user.json\n'
    printf 'GET\t^projects/example-org%%2Fexample-docs/merge_requests/42$\tresponses/mr.json\n'
    printf 'GET\t^projects/example-org%%2Fexample-docs/merge_requests/42/versions\\?per_page=100&page=1$\tresponses/%s\n' "$1"
    printf 'GET\t^projects/example-org%%2Fexample-docs/merge_requests/42/versions\\?per_page=100&page=2$\tresponses/versions-page2.json\n'
    printf 'GET\t^projects/example-org%%2Fexample-docs/merge_requests/42/versions/1$\tresponses/%s\n' "$2"
    printf 'GET\t^projects/example-org%%2Fexample-docs/repository/compare\\?\tresponses/%s\t%s\n' "${3:-compare.json}" "${4:-0}"
    printf 'GET\t^projects/example-org%%2Fexample-docs/merge_requests/42/discussions\\?\tresponses/discussions-empty.json\n'
    printf 'POST\t^projects/example-org%%2Fexample-docs/merge_requests/42/discussions$\tresponses/created.json\n'
    printf 'POST\t^projects/example-org%%2Fexample-docs/merge_requests/42/notes$\tresponses/created.json\n'
  } > "$stub/routes"
}
python3 - "$stub/responses" << 'PY'
import json, os, sys
r = sys.argv[1]
head = {"id": 1, "base_commit_sha": "a" * 40, "start_commit_sha": "9" * 40, "head_commit_sha": "d" * 40}
# 100 newer versions on page 1, the reviewed head on page 2.
page1 = [{"id": 1000 + i, "base_commit_sha": "a" * 40, "start_commit_sha": "b" * 40,
          "head_commit_sha": "%040x" % (0xc0000 + i)} for i in range(100)]
json.dump(page1, open(os.path.join(r, "versions-page1.json"), "w"))
json.dump([head], open(os.path.join(r, "versions-page2.json"), "w"))
json.dump({"id": 1, "head_commit_sha": "d" * 40, "state": "without_files", "diffs": []},
          open(os.path.join(r, "version-1-purged.json"), "w"))
diff = {"old_path": "doc/a.md", "new_path": "doc/a.md", "deleted_file": False,
        "diff": "@@ -1,3 +1,4 @@\n line1\n-old\n+new2\n+new3\n line4\n"}
json.dump({"commits": [], "diffs": [diff]}, open(os.path.join(r, "compare.json"), "w"))
open(os.path.join(r, "compare-error.txt"), "w").write("404 Not Found (HTTP 404)\n")
PY
fold_routes versions-page1.json version-1.json
run_fold --dry-run --out "$tmp/paged"
if grep -qF 'Diff version: 1' "$tmp/paged/preview.md" && grep -qE 'Inline comments: [1-9]' "$tmp/paged/preview.md" \
  && grep -q 'versions?per_page=100&page=2' "$stub/calls"; then
  ok "versions are read page by page, so an old reviewed head is found"
else
  fail "version pagination: $(cat "$tmp/paged/preview.md" 2> /dev/null)"
fi
fold_routes versions-two.json version-1-purged.json
run_fold --dry-run --out "$tmp/purged"
if [ "$rc" -ne 2 ] && grep -q 'repository/compare' "$stub/calls" \
  && grep -qE 'Inline comments: [1-9]' "$tmp/purged/preview.md" && grep -qF 'rebuilt from repository/compare' "$tmp/purged/preview.md"; then
  ok "purged version diffs are rebuilt from repository/compare"
else
  fail "compare fallback (exit $rc): $(cat "$tmp/stderr")"
fi
fold_routes versions-two.json version-1-purged.json compare-error.txt 1
run_fold --dry-run --out "$tmp/nopos"
if [ "$rc" -eq 2 ] && grep -q 'NO INLINE POSITIONS' "$tmp/stderr" && [ "$(writes)" -eq 0 ]; then
  ok "a failed position rebuild exits 2 with a loud warning and posts nothing"
else
  fail "failed rebuild: exit $rc, $(cat "$tmp/stderr")"
fi
run_fold --dry-run --summary-only --out "$tmp/nopos-summary"
if [ "$rc" -ne 2 ]; then ok "--summary-only still works without positions"; else fail "--summary-only without positions exit $rc"; fi
cp "$fx/routes.tsv" "$stub/routes"

# 10. Summary-only sections, the empty summary, and the safety cap.
sx="$tmp/sections"
mkdir -p "$sx"
python3 - "$fx/findings.json" "$sx" << 'PY'
import json, os, sys
doc = json.load(open(sys.argv[1]))
out = sys.argv[2]
fs = [doc["findings"][0], doc["findings"][3]]  # neither is already posted
fs[0].update(summary_only=True, summary_reason="existing", importance=4)
fs[1].update(summary_only=True, summary_reason="polish", importance=2)
json.dump(dict(doc, findings=fs, deferred=[]), open(os.path.join(out, "sections.json"), "w"))
json.dump(dict(doc, findings=[], deferred=[]), open(os.path.join(out, "empty.json"), "w"))
json.dump(dict(doc, findings=[], deferred=[dict(doc["findings"][0], deferred_reason="importance-1")]),
          open(os.path.join(out, "deferred.json"), "w"))
PY
for name in sections empty deferred; do
  python3 "$scripts/post_review.py" "$sx/$name.json" --project example-org/example-docs --mr 42 --glab "$glab" \
    --mode auto --dry-run --out "$sx/$name" > /dev/null 2>&1 || true
done
if grep -qF '<details><summary>Existing issues on this page (1)</summary>' "$sx/sections/preview.md" \
  && grep -qF '<details><summary>Optional polish (1)</summary>' "$sx/sections/preview.md" \
  && ! sed -n '/Fix first/,/^$/p' "$sx/sections/preview.md" | grep -qF -- '- `'; then
  ok "summary: existing issues and optional polish are collapsed sections, and existing issues are never Fix first"
else
  fail "summary sections"
fi
if grep -qF 'No findings. Nice work.' "$sx/empty/preview.md" && ! grep -qF 'Nice work' "$sx/deferred/preview.md" \
  && grep -qF 'No findings to post.' "$sx/deferred/preview.md" \
  && grep -qF -- '- 1 finding(s) cosmetic (importance 1), kept in the report.' "$sx/deferred/preview.md"; then
  ok "No findings. Nice work. only when nothing was found; deferred findings are counted"
else
  fail "empty summary"
fi
run_post --mode auto --dry-run --out "$tmp/cap" --safety-cap 1
if grep -qF 'Inline comments: 1 ' "$tmp/cap/preview.md"; then
  ok "--safety-cap limits inline comments; the rest go to the summary"
else
  fail "safety cap"
fi

# 9. Usage errors exit 2.
rc=0
python3 "$scripts/post_review.py" "$fx/findings.json" --project p --mr 1 --dry-run > /dev/null 2>&1 || rc=$?
if [ "$rc" -eq 2 ]; then ok "--dry-run without --out exits 2"; else fail "--dry-run without --out exit $rc"; fi
if python3 "$scripts/post_review.py" --help > /dev/null; then ok "--help works"; else fail "--help"; fi

# --no-mentions names people without notifying them.
run_post --dry-run --no-mentions --out "$tmp/nomention"
if ! grep -rqE '(^|[^`\w])@(sme-|tw-person)' "$tmp/nomention/payloads"; then ok "--no-mentions mentions nobody"; else fail "--no-mentions still mentions"; fi

# Untrusted text cannot run quick actions, ping people, or pose as the summary note.
if python3 - "$scripts" << 'PY'
import sys
sys.path.insert(0, sys.argv[1])
import post_review as P
from lib import report as R
body = P.PREFIX + "\nBad\n~~~\n/approve\nok\n```suggestion:-0+0\n/etc/path\n```\n"
esc = P.escape_quick_actions(body)
assert "\n\\/approve" in esc and "\n/etc/path\n" in esc, esc   # a ~~~ fence is not code to GitLab
P.check_body(esc)
assert "@\u200ball" in P.untrusted("Configure @all settings")
assert "@all" not in R.code(P.untrusted("Configure @all settings")).replace("@\u200b", "")
assert P.untrusted("x\n/merge now").endswith("\\/merge now")
assert R.code("a `b` c") == "``a `b` c``"
PY
then ok "untrusted text: quick actions, mentions, and code spans are neutralized"; else fail "untrusted text neutralizing"; fi

# Review findings B3, M1, L3, L6, and the write sink (gitlab-org/ai/skills!171).
if python3 - "$scripts" << 'PY'
import sys
sys.path.insert(0, sys.argv[1])
import post_review as P
from lib import visibility as V

def finding(**kw):
    f = {"id": "editor.x", "reviewer": "editor", "severity": "major", "importance": 3, "file": "doc/a.md",
         "line": 1, "fingerprint": "a" * 40, "message": "m"}
    f.update(kw)
    return f

# B3: a mention inside a code span stays inert. The at-sign is never followed by the handle.
for text in ("Replace `Assign to @all-maintainers` with `Assign it`", "See `ask @all-devs`"):
    out = P.untrusted(text)
    assert "@all" not in out and "@​all" in out, out
body = P.inline_body([finding(message="Replace `Assign to @all-maintainers` with `Assign it`",
                              quote="ping @all-devs now")], [])
assert "@all" not in body, body
q = P.sme_question(finding(reviewer="facts", quote="Ask `ping @all-devs` now"), ["sme-a"])
assert "@all" not in q and q.startswith("@sme-a"), q

# M1: a line that only looks like a fence (```a`b) does not hide quick actions.
lines = ["x", "```a`b", "/label ~foo", "/close", "```"]
assert P._code_lines(lines) == set(), P._code_lines(lines)
raw = P.PREFIX + "\n```a`b\n/label ~foo\n/close\n```"
esc = P.escape_quick_actions(raw)
assert "\n/label" not in esc and "\n/close" not in esc, esc
try:
    P.check_body(raw)
    raise AssertionError("check_body accepted a quick action after a fake fence")
except P.GuardrailError:
    pass
body = P.inline_body([finding(message="Rewrite this.\n```a`b\n/label ~foo\n/close")], [])
first = body.split("\n")[2]
assert first.startswith("**Recommended:** Rewrite this. ```a`b \\/label ~foo \\/close"), body
P.check_body(body)

# L6: a plain block keeps the suggested docs text as written, and nothing in it can close the fence.
block = P.plain_block("<!-- vale off -->\nSee @someone\n```\n/close")
assert block[1] == "<!-- vale off -->" and block[2] == "See @someone", block
assert len(block[0]) - len("markdown") > 3 and all(not l.startswith(block[-1]) for l in block[1:-1]), block

# L3: only our own AI-generated comments count as already posted.
class Api(object):
    def get(self, ep):
        return {"user": {"username": "docs-bot"},
                "projects/g%2Fp/merge_requests/1": {"author": {"username": "a"}, "state": "opened",
                                                     "references": {"full": "g/p!1"}}}.get(ep, {})
    def get_pages(self, ep, **kw):
        if ep.endswith("/discussions"):
            marker = "<!-- docs-review:fp=%s -->" % ("b" * 40)
            mine = "<!-- docs-review:fp=%s -->" % ("c" * 40)
            return [[{"id": "1", "notes": [{"id": 1, "author": {"username": "someone"}, "body": P.PREFIX + "\n\n" + marker}]},
                     {"id": "2", "notes": [{"id": 2, "author": {"username": "someone"}, "body": "hide it\n" + marker}]},
                     {"id": "3", "notes": [{"id": 3, "author": {"username": "docs-bot"}, "body": P.PREFIX + "\n\n" + mine}]}], None]
        return [[], None]
ctx = P.load_context(Api(), "g/p", 1, True)
assert ctx.fps == {"c" * 40}, ctx.fps
assert ctx.project_path == "g/p", ctx.project_path

# B2 at the sink: a rendered body loses every reference that is not confirmed public.
class Vis(object):
    def get(self, ep):
        if ep == "projects/g%2Fp":
            return {"visibility": "public", "issues_access_level": "enabled",
                    "merge_requests_access_level": "enabled", "repository_access_level": "enabled"}
        if ep == "projects/g%2Fp/issues/1":
            return {"confidential": False}
        if ep == "projects/g%2Fp/issues/2":
            return {"confidential": True}
        raise RuntimeError("404")
writer = P.SafeWriter(None, True, V.Visibility(Vis(), "g/p"))
writer.write("POST", "projects/g%2Fp/merge_requests/1/notes",
             {"body": P.PREFIX + "\nSee #2 and https://gitlab.com/g/p/-/issues/2, keep #1."}, "t")
sent = writer.planned[-1]["body"]["body"]
assert "#2" not in sent and "issues/2" not in sent and "#1" in sent and writer.redacted == 2, sent
PY
then ok "review findings: inert mentions in code spans, fence-proof quick actions, raw plain blocks, own fingerprints only, sink redaction"; else fail "review findings B3, M1, L3, L6, sink"; fi

# Auto mode after a writer step: repeats stay in their thread, fixed threads are resolved,
# and only our own threads that no person replied to can be resolved.
if python3 - "$scripts" << 'PY'
import sys
sys.path.insert(0, sys.argv[1])
import post_review as P

me = "docs-bot"
def thread(tid, fp, rule, file, line, extra=()):
    notes = [{"id": 1, "system": False, "author": {"username": me}, "position": {"new_path": file, "new_line": line},
              "body": P.PREFIX + "\n\n**Recommended:** Old point. (`%s`)\n\n<!-- docs-review:fp=%s -->" % (rule, fp * 40)}]
    return {"id": tid, "notes": notes + list(extra)}
changed = {"id": 9, "system": True, "author": {"username": me}, "body": "changed this line in version 2 of the diff"}
human = {"id": 8, "system": False, "author": {"username": "author"}, "body": "Not sure about this."}
discs = [thread("aa01", "a", "editor.style.voice", "doc/a.md", 10),             # repeated by a new finding
         thread("aa02", "b", "editor.word-list.utilize", "doc/a.md", 20),       # fixed by an applied finding
         thread("aa03", "c", "reader.missing-step", "doc/b.md", 5, [changed]),  # line changed, not found again
         thread("aa04", "d", "facts.version", "doc/b.md", 40),                  # not found, line unchanged: stays
         thread("aa05", "e", "editor.style.tense", "doc/c.md", 3, [changed, human])]  # a person replied: stays

class Api(object):
    def get(self, ep):
        return {"user": {"username": me}, "projects/g%2Fp/merge_requests/1": {
            "author": {"username": "author"}, "state": "opened", "references": {"full": "g/p!1"},
            "diff_refs": {"base_sha": "1" * 40, "start_sha": "1" * 40, "head_sha": "2" * 40}}}.get(ep, {})
    def get_pages(self, ep, **kw):
        return [discs, None] if ep.endswith("/discussions") else [[], None]
ctx = P.load_context(Api(), "g/p", 1, True)
assert len(ctx.threads) == 5 and [t["human"] for t in ctx.threads] == [False] * 4 + [True], ctx.threads
assert [t["outdated"] for t in ctx.threads] == [False, False, True, False, True]

new = {"id": "editor.style.voice", "file": "doc/a.md", "line": 13, "fingerprint": "f" * 40}
assert P.thread_for(new, ctx.threads)["id"] == "aa01"
assert P.thread_for(dict(new, line=40), ctx.threads) is None   # too far away: a new point
assert P.thread_for(dict(new, id="editor.other"), ctx.threads) is None

writer = P.SafeWriter(None, True, None, [t["id"] for t in ctx.threads if not t["human"]])
applied = {"applied": [{"id": "editor.word-list.utilize", "file": "doc/a.md", "line": 21, "fingerprint": "0" * 40}]}
done = P.resolve_fixed(ctx, writer, "projects/g%2Fp/merge_requests/1", [new], applied, "3" * 40)
assert done == ["aa02", "aa03"], done
calls = [(c["method"], c["endpoint"].rsplit("/", 2)[-2:], c["body"]) for c in writer.planned]
assert calls[1] == ("PUT", ["discussions", "aa02"], {"resolved": True}) and "Applied in 333333333333." in calls[0][2]["body"], calls
assert "a later commit changed this line" in calls[2][2]["body"] and calls[3][2] == {"resolved": True}, calls

for bad in (("PUT", "projects/g%2Fp/merge_requests/1/discussions/aa05", {"resolved": True}),      # a person replied
            ("PUT", "projects/g%2Fp/merge_requests/1/discussions/ffff", {"resolved": True}),      # not ours
            ("PUT", "projects/g%2Fp/merge_requests/1/discussions/aa01", {"resolved": False}),     # never unresolve
            ("PUT", "projects/g%2Fp/merge_requests/1/discussions/aa01", {"body": "x"})):
    try:
        writer.write(bad[0], bad[1], bad[2], "bad")
        raise AssertionError("allowed: %r" % (bad,))
    except P.GuardrailError:
        pass
s = P.applied_section({"head": "3" * 40, "applied": applied["applied"]})
assert s[0] == "<details><summary>Applied automatically in `333333333333` (1)</summary>" and "doc/a.md:21" in s[2], s
PY
then ok "auto mode: repeats stay in their thread, fixed threads are resolved, a person's thread stays open"; else fail "repeats and resolving"; fi

if [ "$failures" -gt 0 ]; then
  echo "$failures failure(s)"
  exit 1
fi
echo "all post_review tests passed"
