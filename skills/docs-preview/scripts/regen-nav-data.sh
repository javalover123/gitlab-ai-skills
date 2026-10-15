#!/usr/bin/env bash
# Regenerate docs-gitlab-com data files (page-metadata.json nav trails) after
# navigation.yaml changes. The side nav renders only for pages with a trail,
# and Hugo live reload does NOT regenerate page-metadata.json.
#
# Usage: regen-nav-data.sh <docs-gitlab-com dir>
# Example: regen-nav-data.sh ~/src/docs-gitlab-com
# Exit: make's exit status; 2 on usage error.
# Requires: make and Go (docs-gitlab-com mise.toml installs Go); mise is used when present.
set -Eeuo pipefail
case "${1:-}" in -h | --help)
  sed -n '2,/^[^#]/{/^#/s/^# \{0,1\}//p;}' "$0"
  exit 0
  ;;
esac
trap 'echo "regen-nav-data: error on line $LINENO" >&2' ERR

dgc=${1:-}
if [[ -z $dgc || ! -f $dgc/Makefile || ! -d $dgc/data ]]; then
    echo "Usage: regen-nav-data.sh <docs-gitlab-com dir> (got '${dgc}')" >&2
    exit 2
fi
dgc=$(CDPATH='' cd -- "$dgc" && pwd)
parent=$(dirname "$dgc")
log=$(mktemp "${TMPDIR:-/tmp}/regen-nav-data.XXXXXX")
trap 'rm -f "$log"' EXIT

rc=0
cd "$dgc"
if command -v mise >/dev/null 2>&1; then
    # Trust only this checkout and stop mise from walking up into a parent
    # project's mise.toml (which may pin a whole other toolchain).
    MISE_CEILING_PATHS=$parent MISE_TRUSTED_CONFIG_PATHS=$dgc mise exec -- make build-data >"$log" 2>&1 || rc=$?
else
    make build-data >"$log" 2>&1 || rc=$?
fi
# The releases.yml warning is optional data from www-gitlab-com; ignore it.
grep -E 'INFO|WARN|ERROR|error' "$log" | grep -v 'releases.yml' || true
if [[ $rc -ne 0 ]]; then
    echo "regen-nav-data: make build-data failed (exit $rc). Full log:" >&2
    cat "$log" >&2
fi
exit "$rc"
