#!/usr/bin/env bash
# Run shellcheck over the Bash helper scripts shipped inside skills/ and the
# repo's own scripts/ helpers.
#
# Rationale: reviewers repeatedly caught Bash footguns in skill helper scripts
# (!37, !39) — e.g. `[ -f .eslintrc* ]` which silently never matches (SC2144),
# missing strict mode, unquoted expansions. shellcheck catches these
# mechanically so they don't recur. All current scripts pass clean, so this
# lands green and only fires on regressions.
#
# Usage: scripts/lint_shell.sh
# Requires: shellcheck

set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v shellcheck >/dev/null 2>&1; then
  echo "ERROR: shellcheck not found on PATH." >&2
  exit 1
fi

# Collect Bash scripts under skills/ and scripts/. Null-delimited to handle any
# path, and read into an array portably (works on bash 3.2 / macOS and
# bash 5 / alpine).
scripts=()
while IFS= read -r -d '' f; do
  scripts+=("$f")
done < <(find skills scripts -name '*.sh' -type f -print0)

if [ ${#scripts[@]} -eq 0 ]; then
  echo "No shell scripts to check."
  exit 0
fi

echo "Running shellcheck on ${#scripts[@]} script(s):"
printf '  %s\n' "${scripts[@]}"

shellcheck "${scripts[@]}"
echo "shellcheck: all clean."
