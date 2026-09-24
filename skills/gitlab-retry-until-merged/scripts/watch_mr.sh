#!/usr/bin/env bash
# watch_mr.sh - Block until an auto-merge MR needs attention, then print why
# Usage: ./watch_mr.sh --expect-sha <sha> [options] <mr-url>
#   --expect-sha SHA   MR head SHA recorded at preflight (required)
#   --seen IDS         Comma-separated failed job/bridge IDs already triaged
#   --grace N          Ignore a terminal pipeline status for the first N
#                      seconds (use after a retry, while the retried pipeline
#                      may still read as failed). Default 0.
#   --mr-only          Ignore the pipeline entirely; watch only the MR itself
#                      (merge, close, push, auto-merge). For waiting out an
#                      incident while the pipeline sits failed.
#   --interval N       Seconds between polls (default 60)
#   --timeout N        Give up after N seconds and emit TIMEOUT (default 480,
#                      leaving headroom under a 10-minute tool-call limit).
#                      Always polls once.
# Output: the final mr_state.sh snapshot plus an "event" field, one of:
#   MERGED          the MR merged; done
#   CLOSED          the MR was closed without merging
#   SHA_CHANGED     new commits were pushed; the approval premise is gone
#   AUTO_MERGE_OFF  auto-merge was canceled (by a person, or a merge train drop)
#   NEW_FAILURE     a blocking job failed while the pipeline is still running
#   PIPELINE_FAILED / PIPELINE_CANCELED / PIPELINE_SKIPPED / PIPELINE_MANUAL
#   NO_PIPELINE     the MR has no pipeline
#   API_ERROR       3 polls in a row failed (GitLab API erroring or
#                   unreachable); carries the last good snapshot, if any
#   TIMEOUT         nothing actionable yet; not a failure, just run again
#
# Never writes anything.

set -Eeuo pipefail

error_handler() {
  echo "Error: Command failed at line $1 with exit code $2" >&2
}

trap 'error_handler $LINENO $?' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

EXPECT_SHA=""
SEEN=""
GRACE=0
MR_ONLY=false
INTERVAL=60
TIMEOUT=480
MR_URL=""

need_value() {
  if [[ $# -lt 2 || -z "$2" ]]; then
    echo "$1 needs a value" >&2
    exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --expect-sha) need_value "$@"; EXPECT_SHA="$2"; shift 2 ;;
  --seen) need_value "$@"; SEEN="$2"; shift 2 ;;
  --grace) need_value "$@"; GRACE="$2"; shift 2 ;;
  --interval) need_value "$@"; INTERVAL="$2"; shift 2 ;;
  --timeout) need_value "$@"; TIMEOUT="$2"; shift 2 ;;
  --mr-only) MR_ONLY=true; shift ;;
  -*)
    echo "Unknown option: $1" >&2
    exit 2
    ;;
  *)
    MR_URL="$1"
    shift
    ;;
  esac
done

if [[ -z "$EXPECT_SHA" || -z "$MR_URL" ]]; then
  echo "Usage: $0 --expect-sha <sha> [--seen IDS] [--grace N] [--mr-only] [--interval N] [--timeout N] <mr-url>" >&2
  exit 2
fi

for n in "$GRACE" "$INTERVAL" "$TIMEOUT"; do
  if ! [[ "$n" =~ ^[0-9]+$ ]]; then
    echo "--grace, --interval and --timeout take whole seconds" >&2
    exit 2
  fi
done

SEEN_JSON=$(jq -cn --arg s "$SEEN" '$s | split(",") | map(select(length > 0) | tonumber)')

STATE='{}'

emit() {
  echo "$STATE" | jq --arg event "$1" '. + {event: $event}'
  exit 0
}

START=$SECONDS
API_FAILURES=0

while true; do
  # A failed poll (API 5xx, network) is not fatal: GitLab erroring is exactly
  # what happens during an incident. Keep the last good snapshot.
  POLL=$(bash "$SCRIPT_DIR/mr_state.sh" "$MR_URL" 2>/dev/null || true)
  ELAPSED=$((SECONDS - START))

  if [[ -z "$POLL" ]] || ! echo "$POLL" | jq -e '.state' >/dev/null 2>&1; then
    API_FAILURES=$((API_FAILURES + 1))
    if ((API_FAILURES >= 3 || ELAPSED + INTERVAL > TIMEOUT)); then
      STATE=$(echo "$STATE" | jq --argjson n "$API_FAILURES" \
        '. + {api_error: "mr_state.sh failed \($n) poll(s) in a row; the GitLab API may be erroring"}')
      emit API_ERROR
    fi
    sleep "$INTERVAL"
    continue
  fi
  API_FAILURES=0
  STATE="$POLL"

  MR_STATE=$(echo "$STATE" | jq -r '.state')
  PIPELINE_STATUS=$(echo "$STATE" | jq -r '.pipeline.status // "none"')

  [[ "$MR_STATE" == "merged" ]] && emit MERGED
  [[ "$MR_STATE" == "closed" ]] && emit CLOSED
  [[ "$(echo "$STATE" | jq -r '.sha')" != "$EXPECT_SHA" ]] && emit SHA_CHANGED
  [[ "$(echo "$STATE" | jq -r '.auto_merge')" != "true" ]] && emit AUTO_MERGE_OFF

  if [[ "$MR_ONLY" != true ]]; then
    [[ "$PIPELINE_STATUS" == "none" ]] && emit NO_PIPELINE

    case "$PIPELINE_STATUS" in
    failed | canceled | skipped | manual)
      if ((ELAPSED >= GRACE)); then
        emit "PIPELINE_$(echo "$PIPELINE_STATUS" | tr '[:lower:]' '[:upper:]')"
      fi
      ;;
    success)
      # Auto-merge acts on success; keep polling until MERGED or TIMEOUT.
      ;;
    *)
      NEW=$(echo "$STATE" | jq --argjson seen "$SEEN_JSON" \
        '[(.failed_jobs + .failed_bridges)[] | select(.id as $id | $seen | index($id) | not)] | length')
      ((NEW > 0)) && emit NEW_FAILURE
      ;;
    esac
  fi

  if ((ELAPSED + INTERVAL > TIMEOUT)); then
    emit TIMEOUT
  fi
  sleep "$INTERVAL"
done
