#!/usr/bin/env bash
# Replace one top-level section of a docs-gitlab-com navigation.yaml with the
# entries from a project-owned navigation file, so a local preview shows the
# project's new side nav before the docs-gitlab-com MR merges.
#
# A section starts at a header comment in column 0 (for example `# GITLAB RUNNER`)
# and ends at the next `# ` header in column 0. The swap keeps the header,
# inserts the non-comment lines of the section file, and drops the old entries.
# Running it twice changes nothing.
#
# Usage: swap-nav.sh [--check] <navigation.yaml> <header line> <section file>
#   --check  do not write; exit 0 if the section already matches, 1 if it differs
# Example:
#   swap-nav.sh ~/src/docs-gitlab-com/data/en-us/navigation.yaml '# GITLAB RUNNER' docs/navigation.yaml
# Exit: 0 done (or already current), 1 differs (--check), 2 usage error or header not found.
#
# This edits a docs-gitlab-com checkout. Never commit the result there from a
# preview: production nav changes go in their own docs-gitlab-com MR.
set -Eeuo pipefail
case "${1:-}" in -h | --help)
  sed -n '2,/^[^#]/{/^#/s/^# \{0,1\}//p;}' "$0"
  exit 0
  ;;
esac
trap 'echo "swap-nav: error on line $LINENO" >&2' ERR

check=0
if [[ ${1:-} == "--check" ]]; then check=1; shift; fi
if [[ $# -ne 3 ]]; then
    sed -n '11,15p' "$0" >&2
    exit 2
fi
nav=$1 header=$2 section=$3
[[ -f $nav ]] || { echo "ERROR: navigation file not found: $nav" >&2; exit 2; }
[[ -f $section ]] || { echo "ERROR: section file not found: $section" >&2; exit 2; }
if ! grep -qxF -- "$header" "$nav"; then
    echo "ERROR: '$header' is not a line in $nav. List the headers with: grep -n '^# ' $nav" >&2
    exit 2
fi

tmp=$(mktemp "${TMPDIR:-/tmp}/swap-nav.XXXXXX")
trap 'rm -f "$tmp"' EXIT

# ENVIRON instead of awk -v, so backslashes in paths or headers stay literal.
HEADER=$header SECTION=$section awk '
    BEGIN { header = ENVIRON["HEADER"]; section = ENVIRON["SECTION"] }
    $0 == header {
        print; print ""
        while ((getline line < section) > 0) if (line !~ /^#/) print line
        print ""; skip = 1; next
    }
    skip && /^# / { skip = 0 }
    !skip
' "$nav" >"$tmp"

if cmp -s "$nav" "$tmp"; then
    echo "swap-nav: '$header' already matches $section"
    exit 0
fi
if [[ $check -eq 1 ]]; then
    echo "swap-nav: '$header' in $nav differs from $section"
    exit 1
fi
cat "$tmp" >"$nav"
echo "swap-nav: replaced '$header' in $nav with $section. Run regen-nav-data.sh next."
