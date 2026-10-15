#!/usr/bin/env bash
# Tests for scripts/apply_findings.py. No network, no credentials.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../scripts/apply_findings.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail=0

check() {
    # check <description> <python expression over the report `r`>
    if python3 -c "import json,sys; r=json.load(open(sys.argv[1])); sys.exit(0 if ($2) else 1)" "$TMP/out/apply-report.json"; then
        echo "ok - $1"
    else
        echo "not ok - $1" >&2
        fail=1
    fi
}

mkdir -p "$TMP/repo/doc"
cat >"$TMP/repo/doc/page.md" <<'EOF'
# Example

In order to create a project, select **New project**.

You can utilize the API.
Second line of a paragraph.

Unchanged line.
EOF
cp "$TMP/repo/doc/page.md" "$TMP/original.md"
printf 'Other page.\n' >"$TMP/repo/doc/other.md"

cat >"$TMP/findings.json" <<'EOF'
{"version": 1, "findings": [
  {"id": "lint.in-order-to", "reviewer": "lint", "severity": "minor", "confidence": "high",
   "file": "doc/page.md", "line": 3, "end_line": 3, "quote": "In order to create",
   "message": "Use 'To' instead of 'In order to'.", "fixable": "auto",
   "suggestion": "To create a project, select **New project**.", "source": "https://docs.gitlab.com/x", "deterministic": true},
  {"id": "word-list.utilize", "reviewer": "lint", "severity": "major", "confidence": "high",
   "file": "doc/page.md", "line": 5, "end_line": 5, "quote": "utilize",
   "message": "Use 'use' instead.", "fixable": "auto",
   "suggestion": "You can use the API.", "source": "https://docs.gitlab.com/x", "deterministic": true},
  {"id": "brevity.merge-lines", "reviewer": "brevity", "severity": "major", "confidence": "high",
   "file": "doc/page.md", "line": 5, "end_line": 6, "quote": "Second line",
   "message": "Overlaps the word-list fix.", "fixable": "auto",
   "suggestion": "You can use the API in one line.", "source": "https://docs.gitlab.com/x", "deterministic": false},
  {"id": "lint.stale", "reviewer": "lint", "severity": "minor", "confidence": "high",
   "file": "doc/page.md", "line": 8, "end_line": 8, "quote": "text that is not there",
   "message": "Quote does not match.", "fixable": "auto",
   "suggestion": "Changed.", "source": "https://docs.gitlab.com/x", "deterministic": true},
  {"id": "style.rewrite", "reviewer": "style", "severity": "major", "confidence": "high",
   "file": "doc/other.md", "line": 1, "end_line": 1, "quote": "Other page.",
   "message": "Rewrite.", "fixable": "suggest", "suggestion": "Another page.", "source": "https://docs.gitlab.com/x", "deterministic": false},
  {"id": "structure.move", "reviewer": "structure", "severity": "minor", "confidence": "medium",
   "file": "doc/other.md", "line": 1, "end_line": 1, "quote": "Other page.",
   "message": "Move this section.", "fixable": "manual", "source": "https://docs.gitlab.com/x", "deterministic": false}
]}
EOF

# Dry run: no file changes, a patch is written.
python3 "$SCRIPT" --findings "$TMP/findings.json" --repo "$TMP/repo" --out "$TMP/out" --dry-run >/dev/null
if cmp -s "$TMP/repo/doc/page.md" "$TMP/original.md"; then echo "ok - dry run leaves files unchanged"; else echo "not ok - dry run changed a file" >&2; fail=1; fi
check "dry run writes a patch" "__import__('os').path.getsize(sys.argv[1].replace('apply-report.json','apply.patch')) > 0"

# Real run.
rm -rf "$TMP/out"
python3 "$SCRIPT" --findings "$TMP/findings.json" --repo "$TMP/repo" --out "$TMP/out" >/dev/null
check "two mechanical fixes applied" "len(r['applied']) == 2"
check "overlapping fix becomes a conflict" "any('overlaps' in c['reason'] for c in r['conflicts'])"
check "stale quote becomes a conflict" "any('no longer matches' in c['reason'] for c in r['conflicts'])"
check "manual finding with medium confidence is skipped under the auto policy" "len(r['skipped']) == 1"
check "conflicts and the suggest finding go to writers" "sum(s['findings'] for s in r['writer_sets']) == 3"
check "a file is in only one writer set" "len([f for s in r['writer_sets'] for f in s['files']]) == len({f for s in r['writer_sets'] for f in s['files']})"

if grep -q '^To create a project' "$TMP/repo/doc/page.md" && grep -q '^You can use the API.$' "$TMP/repo/doc/page.md" && grep -q '^Unchanged line.$' "$TMP/repo/doc/page.md"; then
    echo "ok - file content is correct after apply"
else
    echo "not ok - file content after apply:" >&2
    cat "$TMP/repo/doc/page.md" >&2
    fail=1
fi

# Policy all: the manual finding reaches a writer too.
rm -rf "$TMP/out"
cp "$TMP/original.md" "$TMP/repo/doc/page.md"
python3 "$SCRIPT" --findings "$TMP/findings.json" --repo "$TMP/repo" --out "$TMP/out" --policy all --partition 1 >/dev/null
check "policy all sends the manual finding to a writer" "sum(s['findings'] for s in r['writer_sets']) == 4 and len(r['writer_sets']) == 1"

# Usage error.
if python3 "$SCRIPT" --findings "$TMP/findings.json" --partition 0 >/dev/null 2>&1; then
    echo "not ok - --partition 0 should fail" >&2; fail=1
else
    echo "ok - --partition 0 is a usage error"
fi

# A CRLF file keeps its line endings after a fix.
crlf="$(mktemp -d)"
printf 'Line one.\r\nUse utilize here.\r\nEnd.\r\n' > "$crlf/a.md"
cat > "$crlf/f.json" << 'JSON'
{"findings": [{"id": "lint.word-list.utilize", "reviewer": "lint", "severity": "minor", "confidence": "high", "file": "a.md", "line": 2, "quote": "Use utilize here.", "message": "m", "fixable": "auto", "suggestion": "Use use here.", "deterministic": true, "importance": 2, "source": "x"}]}
JSON
python3 "$SCRIPT" --findings "$crlf/f.json" --repo "$crlf" --out "$crlf/out" > /dev/null 2>&1 || true
if [ "$(cat "$crlf/a.md")" = "$(printf 'Line one.\r\nUse use here.\r\nEnd.\r')" ]; then
    echo "ok - a fix keeps CRLF line endings"
else
    echo "FAIL - a fix keeps CRLF line endings"; fail=1
fi
rm -rf "$crlf"

# A finding cannot write outside the repo, and one with no quote is never applied mechanically.
esc="$(mktemp -d)"
mkdir -p "$esc/repo"
printf 'keep me\n' > "$esc/victim.txt"
printf 'Line.\n' > "$esc/repo/a.md"
cat > "$esc/f.json" << 'JSON'
{"findings": [
 {"id": "lint.x", "reviewer": "lint", "severity": "minor", "confidence": "high", "file": "../victim.txt", "line": 1, "quote": "keep me", "message": "m", "fixable": "auto", "suggestion": "owned", "deterministic": true, "importance": 2, "source": "x"},
 {"id": "lint.y", "reviewer": "lint", "severity": "minor", "confidence": "high", "file": "a.md", "line": 1, "quote": "", "message": "m", "fixable": "auto", "suggestion": "Changed.", "deterministic": true, "importance": 2, "source": "x"}]}
JSON
python3 "$SCRIPT" --findings "$esc/f.json" --repo "$esc/repo" --out "$esc/out" > /dev/null 2>&1 || true
if [ "$(cat "$esc/victim.txt")" = "keep me" ] && [ "$(cat "$esc/repo/a.md")" = "Line." ] \
  && grep -q 'file outside the repo' "$esc/out/apply-report.json"; then
    echo "ok - a file outside the repo and a finding with no quote are not applied"
else
    echo "FAIL - a file outside the repo and a finding with no quote are not applied"; fail=1
fi
rm -rf "$esc"

exit "$fail"
