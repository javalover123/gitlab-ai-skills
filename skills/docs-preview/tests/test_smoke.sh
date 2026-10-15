#!/usr/bin/env bash
# Smoke test for docs-preview: every script parses and prints its usage. No
# network, no docs site. The full tests live in gabrielengel_gl/docs-skills-lab.
set -Eeuo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scripts="$here/../scripts"
failures=0
ok() { echo "ok - $1"; }
fail() {
  echo "FAIL - $1"
  failures=$((failures + 1))
}

for s in "$scripts"/*.sh; do
  if bash -n "$s" && bash "$s" --help | grep -q 'Usage:'; then ok "$(basename "$s") --help"; else fail "$(basename "$s") --help"; fi
done
for s in "$scripts"/*.py; do
  if python3 "$s" --help > /dev/null; then ok "$(basename "$s") --help"; else fail "$(basename "$s") --help"; fi
done

if [ "$failures" -gt 0 ]; then
  echo "$failures failure(s)"
  exit 1
fi
echo "docs-preview smoke test passed"
