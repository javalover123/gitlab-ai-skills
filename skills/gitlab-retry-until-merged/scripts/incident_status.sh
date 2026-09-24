#!/usr/bin/env bash
# incident_status.sh - Snapshot of GitLab.com incident signals
# Usage: ./incident_status.sh [--hours N] [--all-severities]
#   --hours N          Only report master-broken incidents opened in the last
#                      N hours (default 12). The tracker keeps many stale ones.
#   --all-severities   Include severity::3/4 production incidents (default:
#                      severity::1 and severity::2 only; S3/S4 are routine).
# Output: JSON with three signals. A signal that cannot be fetched reports
#         {"error": ...} instead of failing the whole snapshot.
#
# Never writes anything: every call is a GET.

set -Eeuo pipefail

error_handler() {
  echo "Error: Command failed at line $1 with exit code $2" >&2
}

trap 'error_handler $LINENO $?' ERR

HOURS=12
ALL_SEVERITIES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
  --hours)
    if [[ $# -lt 2 ]]; then
      echo "--hours needs a value" >&2
      exit 2
    fi
    HOURS="$2"
    shift 2
    ;;
  --all-severities)
    ALL_SEVERITIES=true
    shift
    ;;
  *)
    echo "Usage: $0 [--hours N] [--all-severities]" >&2
    exit 2
    ;;
  esac
done

if ! [[ "$HOURS" =~ ^[0-9]+$ ]]; then
  echo "--hours must be a whole number" >&2
  exit 2
fi

# status.gitlab.com is a Status.io page; this is its public page ID.
STATUS_PAGE_ID="5b36dc6502d06804c08349f7"
STATUS_URL="https://status.gitlab.com/1.0/status/${STATUS_PAGE_ID}"
PRODUCTION_PROJECT="gitlab-com%2Fgl-infra%2Fproduction"
MASTER_BROKEN_PROJECT="gitlab-org%2Fquality%2Fengineering-productivity%2Fmaster-broken-incidents"

SINCE=$(jq -nr --argjson h "$HOURS" '(now - ($h * 3600)) | todate')

# 1. Public status page: overall status, degraded components, open incidents.
# Each fetch swallows its own failure (`|| true`) so an unreachable signal is
# reported as an error field rather than aborting, and the ERR trap stays quiet.
is_json() { [[ -n "$1" ]] && echo "$1" | jq -e . >/dev/null 2>&1; }

STATUS_RAW=$(curl -fsS --max-time 15 "$STATUS_URL" 2>/dev/null || true)
if is_json "$STATUS_RAW"; then
  STATUS_PAGE=$(echo "$STATUS_RAW" | jq --arg page "$STATUS_PAGE_ID" '.result | {
    overall: .status_overall.status,
    operational: (.status_overall.status_code == 100),
    degraded_components: [.status[] | select(.status_code != 100) | {name, status}],
    active_incidents: [(.incidents // [])[] | {
      name,
      url: ("https://status.gitlab.com/pages/incident/" + $page + "/" + ._id)
    }]
  }')
else
  STATUS_PAGE='{"error": "could not fetch status.gitlab.com"}'
fi

# 2. Active production incidents (infrastructure-wide problems).
PROD_RAW=$(glab api -X GET "projects/${PRODUCTION_PROJECT}/issues" \
  -f "state=opened" \
  -f "labels=incident,Incident::Active" \
  -f "per_page=50" 2>/dev/null || true)
if is_json "$PROD_RAW"; then
  PRODUCTION=$(echo "$PROD_RAW" | jq --argjson all "$ALL_SEVERITIES" '[.[] |
    {
      iid,
      title,
      severity: ([.labels[] | select(startswith("severity::")) | ltrimstr("severity::")] | first // "unknown"),
      labels: [.labels[] | select(test("^(Service|incident-type)::"))],
      created_at,
      web_url
    } |
    select($all or .severity == "1" or .severity == "2")
  ]')
else
  PRODUCTION='{"error": "could not fetch production incidents"}'
fi

# 3. Recent master-broken incidents (default branch broken for everyone).
MB_RAW=$(glab api -X GET "projects/${MASTER_BROKEN_PROJECT}/issues" \
  -f "state=opened" \
  -f "created_after=${SINCE}" \
  -f "per_page=50" 2>/dev/null || true)
if is_json "$MB_RAW"; then
  MASTER_BROKEN=$(echo "$MB_RAW" | jq '[.[] | {
    iid,
    title,
    labels: [.labels[] | select(startswith("master-broken::") or startswith("master:"))],
    created_at,
    web_url
  }]')
else
  MASTER_BROKEN='{"error": "could not fetch master-broken incidents"}'
fi

jq -n \
  --arg checked_at "$(jq -nr 'now | todate')" \
  --arg since "$SINCE" \
  --argjson status_page "$STATUS_PAGE" \
  --argjson production "$PRODUCTION" \
  --argjson master_broken "$MASTER_BROKEN" \
  '{
    checked_at: $checked_at,
    status_page: $status_page,
    production_incidents: $production,
    master_broken_since: $since,
    master_broken_incidents: $master_broken
  }'
