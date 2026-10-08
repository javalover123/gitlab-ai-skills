#!/usr/bin/env bash
# Flag bash 4+ and GNU-only constructs in skill helper scripts, so they keep
# working on macOS (bash 3.2, BSD userland). The rules mirror the traps table
# and "BSD vs GNU tools" list in
# skills/authoring-skills/references/scripts.md; add a rule only when that
# document backs it.
#
# Scope: skills/**/*.sh, minus skills synced in from elsewhere
# (synced-skills.yml; fix those at their source). The repo's own scripts/ are
# out of scope: they run in Linux CI containers, not on a user's laptop.
#
# Line-based and deliberately cheap: comment-only lines are skipped, and a
# trailing `# portability-ok` marker opts a single line out (use it for a use
# that is guarded, e.g. behind a version check or a fallback).
#
# Usage: scripts/lint_bash_portability.sh
# Env (for tests): PORTABILITY_ROOT overrides the repo root.

set -Eeuo pipefail

ROOT="${PORTABILITY_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

# Names of synced skills: 2-space-indented keys under the top-level `skills:`.
synced=""
if [ -f synced-skills.yml ]; then
  synced="$(awk '
    /^skills:/ { in_skills = 1; next }
    /^[^ #]/ { in_skills = 0 }
    in_skills && /^  [A-Za-z0-9_-]+:[ ]*$/ { sub(/^  /, ""); sub(/:.*/, ""); print }
  ' synced-skills.yml)"
fi

files=()
while IFS= read -r -d '' f; do
  skill="${f#skills/}"
  skill="${skill%%/*}"
  if [ -n "$synced" ] && printf '%s\n' "$synced" | grep -qxF -- "$skill"; then
    continue
  fi
  files+=("$f")
done < <(find skills -name '*.sh' -type f -print0 2>/dev/null | sort -z)

if [ ${#files[@]} -eq 0 ]; then
  echo "No skill shell scripts to check."
  exit 0
fi

# awk (POSIX ERE) is the same on BSD, mawk and gawk. Prints file:line: message.
findings="$(awk '
  function rule(re, msg) { n++; res[n] = re; msgs[n] = msg }
  BEGIN {
    w = "(^|[^A-Za-z0-9_])"
    rule(w "BASHPID", "$BASHPID is bash 4+ (use $$)")
    rule("(^|[;&|({[:space:]])(mapfile|readarray)([[:space:]]|$)", "mapfile/readarray is bash 4+ (use a while read loop)")
    rule("(declare|typeset|local|readonly)[[:space:]]+-[A-Za-z]*A", "associative arrays are bash 4+ (use parallel arrays or case)")
    rule("[$][{][A-Za-z_][A-Za-z_0-9]*(,,|\\^\\^)", "${v,,} / ${v^^} is bash 4+ (use tr)")
    rule("[$][{][A-Za-z_][A-Za-z_0-9]*\\[-[0-9]+\\]", "negative array index is bash 4.3+ (use ${a[${#a[@]}-1]})")
    rule("[$][{][A-Za-z_][A-Za-z_0-9]*@Q", "${v@Q} is bash 4.4+ (use printf %q)")
    rule("printf[[:space:]]+(-v[[:space:]]+[A-Za-z_0-9]+[[:space:]]+)?[\"'"'"']%[(]", "printf %(..)T is bash 4.2+ (use date)")
    rule(w "wait[[:space:]]+-[A-Za-z]*n", "wait -n is bash 4.3+ (wait on each PID)")
    rule(w "EPOCHSECONDS", "$EPOCHSECONDS is bash 5+ (use date +%s)")
    rule(w "sed[[:space:]]+(-[A-Za-z]+[[:space:]]+)*-i([[:space:]]|$)", "sed -i needs a suffix on BSD (use -i.bak and remove it)")
    rule(w "date[[:space:]]+(-[A-Za-z]+[[:space:]]+)*(-d|--date)([[:space:]=]|$)", "date -d is GNU only (BSD uses -v)")
    rule(w "readlink[[:space:]]+(-[A-Za-z]+[[:space:]]+)*-[A-Za-z]*f", "readlink -f is missing on older macOS")
    rule(w "grep[[:space:]]+(-[A-Za-z]+[[:space:]]+)*-[A-Za-z]*P", "grep -P is unavailable on macOS (use grep -E)")
    rule(w "stat[[:space:]]+(-[A-Za-z]+[[:space:]]+)*-c", "stat -c is GNU only (use wc -c < file)")
    rule(w "mktemp[[:space:]].*--suffix", "mktemp --suffix is GNU only (pass a template)")
    rule(w "find[[:space:]].*-printf", "find -printf is GNU only")
    rule(w "cp[[:space:]].*--parents", "cp --parents is GNU only")
  }
  FNR == 1 { fname = FILENAME }
  /^[[:space:]]*#/ { next }
  /#[[:space:]]*portability-ok/ { next }
  {
    for (i = 1; i <= n; i++)
      if ($0 ~ res[i]) { printf "%s:%d: %s\n", FILENAME, FNR, msgs[i]; bad = 1 }
  }
' "${files[@]}")"

if [ -n "$findings" ]; then
  printf '%s\n' "$findings"
  echo "bash-portability: found bash 4+/GNU-only constructs." >&2
  echo "See skills/authoring-skills/references/scripts.md; append '# portability-ok' to a guarded line." >&2
  exit 1
fi
echo "bash-portability: ${#files[@]} script(s) clean."
