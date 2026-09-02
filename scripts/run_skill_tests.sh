#!/usr/bin/env bash
# Run the self-contained test suites that skills ship alongside their helper
# scripts.
#
# Convention: a skill with non-trivial helper scripts under
# `skills/<name>/scripts/` may ship `skills/<name>/tests/test_*.sh`. Each such
# file must be runnable with no arguments, must not need network access or
# credentials (stub out anything that would), and must exit non-zero if any of
# its cases fail.
#
# Usage: scripts/run_skill_tests.sh

set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Null-delimited so any path works, read into an array portably (bash 3.2 on
# macOS as well as bash 5 on alpine).
tests=()
while IFS= read -r -d '' f; do
  tests+=("$f")
done < <(find skills -path '*/tests/test_*.sh' -type f -print0 | sort -z)

if [ ${#tests[@]} -eq 0 ]; then
  echo "No skill test suites found."
  exit 0
fi

echo "Running ${#tests[@]} skill test suite(s):"
printf '  %s\n' "${tests[@]}"
echo

failed=()
for t in "${tests[@]}"; do
  echo ">>> $t"
  if bash "$t"; then
    echo "PASS: $t"
  else
    echo "FAIL: $t"
    failed+=("$t")
  fi
  echo
done

if [ ${#failed[@]} -gt 0 ]; then
  echo "Failing skill test suite(s):"
  printf '  - %s\n' "${failed[@]}"
  exit 1
fi

echo "skill tests: all clean."
