#!/usr/bin/env bash
# Smoke test for docs-review: every script starts, and one small review runs
# end to end through combine_findings.py. No network. The full test suite and
# the eval live in gabrielengel_gl/docs-skills-lab.
set -Eeuo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scripts="$here/../scripts"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=false
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.com GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.com
failures=0
ok() { echo "ok - $1"; }
fail() {
  echo "FAIL - $1"
  failures=$((failures + 1))
}

for s in "$scripts"/*.py; do
  if python3 "$s" --help > /dev/null; then ok "$(basename "$s") --help"; else fail "$(basename "$s") --help"; fi
done

# A two-commit repo: the change rewrites one sentence. Needs git.
if ! command -v git > /dev/null; then
  echo "skip - combine end to end (git not installed)"
else
repo="$tmp/repo"
mkdir -p "$repo/doc"
git -C "$repo" init -q
printf '# Widgets\n\nOld intro.\n\nThe flag is off by default.\n' > "$repo/doc/a.md"
git -C "$repo" add -A && git -C "$repo" commit -qm base
printf '# Widgets\n\nThis page explains how widgets work.\n\nThe flag is off by default.\n' > "$repo/doc/a.md"
git -C "$repo" add -A && git -C "$repo" commit -qm head
cat > "$tmp/editor.json" << 'EOF'
{"reviewer": "editor", "status": "complete", "findings": [
 {"id": "editor.brevity.windup", "reviewer": "editor", "severity": "minor", "confidence": "high", "importance": 3,
  "file": "doc/a.md", "line": 3, "quote": "This page explains how widgets work.",
  "message": "Start with what the reader can do.", "source": "https://docs.gitlab.com/development/documentation/styleguide/#language",
  "fixable": "suggest", "suggestion": "Widgets group related settings."},
 {"id": "editor.style.old", "reviewer": "editor", "severity": "minor", "confidence": "high", "importance": 3,
  "file": "doc/a.md", "line": 5, "quote": "The flag is off by default.",
  "message": "An unchanged line.", "source": "https://docs.gitlab.com/development/documentation/styleguide/#language",
  "fixable": "manual"}
]}
EOF
python3 "$scripts/combine_findings.py" "$tmp/editor.json" --repo "$repo" --diff HEAD~1..HEAD --out-dir "$tmp/out" \
  > /dev/null 2> "$tmp/err" || true
if python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); ids=[f["id"] for f in d["findings"] if not f.get("summary_only")]; sys.exit(0 if ids == ["editor.brevity.windup"] else 1)' "$tmp/out/findings.json"; then
  ok "combine keeps the finding on the changed line and drops the one on an unchanged line"
else
  fail "combine output: $(cat "$tmp/err")"
fi
if [ -s "$tmp/out/report.md" ]; then ok "combine writes report.md"; else fail "no report.md"; fi
fi

# The visibility gate withholds a reference it cannot confirm as public.
if python3 - "$scripts" << 'PY'
import sys
sys.path.insert(0, sys.argv[1])
from lib import visibility as V
g, n = V.gate({"id": "facts.behavior", "message": "See example-org/private-repo#2.", "suggestion": "x",
               "evidence": []}, V.Visibility(None))
sys.exit(0 if n == 1 and g["message"] == V.NEUTRAL and g["suggestion"] is None else 1)
PY
then ok "visibility gate withholds an unconfirmed reference"; else fail "visibility gate"; fi

if [ "$failures" -gt 0 ]; then
  echo "$failures failure(s)"
  exit 1
fi
echo "docs-review smoke test passed"
