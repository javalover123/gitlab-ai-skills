#!/usr/bin/env bash
# Wait until a docs preview answers HTTP 200, or fail as soon as its log shows
# a build error. Matches failure AND success: a monitor that waits only for
# success hangs forever when the build dies.
#
# Usage: wait-for-server.sh <url> <log file> [timeout seconds]
# Example: wait-for-server.sh http://localhost:1313/runner/ /tmp/docs-serve.log 900
# Exit: 0 server up, 1 build error in the log, 3 timeout, 2 usage error.
# Requires: python3 (no curl needed).
set -Eeuo pipefail
case "${1:-}" in -h | --help)
  sed -n '2,/^[^#]/{/^#/s/^# \{0,1\}//p;}' "$0"
  exit 0
  ;;
esac
trap 'echo "wait-for-server: error on line $LINENO" >&2' ERR

if [[ $# -lt 2 ]]; then
    sed -n '6,9p' "$0" >&2
    exit 2
fi
url=$1 log=$2
# The first `make view` installs Node packages and builds the frontend before
# Hugo starts; 15 minutes covers a cold run on a laptop.
timeout=${3:-900}
# Poll every 3 s: fast enough to notice a failure, slow enough to stay quiet.
interval=3

# Anchored patterns: a bare "error" also matches harmless WARN lines.
# Covers Hugo (ERROR, Error:), Yarn 1 (error ...), Yarn 4 (Failed with errors),
# mise (mise ERROR), git (fatal:), and make (make: ***).
fail_re='^ERROR|^Error: |^error |mise ERROR|fatal:|make: \*\*\*|Failed with errors'

status() {
    python3 - "$1" <<'PY'
import sys, urllib.request, urllib.error
try:
    with urllib.request.urlopen(sys.argv[1], timeout=5) as r:
        print(r.status)
except urllib.error.HTTPError as e:
    print(e.code)
except Exception:
    print(0)
PY
}

start=$(date +%s)
while :; do
    if [[ "$(status "$url")" == 200 ]]; then
        echo "wait-for-server: $url is up"
        exit 0
    fi
    if [[ -f $log ]] && grep -E "$fail_re" "$log" | grep -v 'releases.yml' >/dev/null; then
        echo "wait-for-server: build failed. Matching log lines:" >&2
        grep -nE "$fail_re" "$log" | grep -v 'releases.yml' | tail -20 >&2
        exit 1
    fi
    if (($(date +%s) - start >= timeout)); then
        echo "wait-for-server: no answer from $url after ${timeout}s. Last log lines:" >&2
        [[ -f $log ]] && tail -20 "$log" >&2
        exit 3
    fi
    sleep "$interval"
done
