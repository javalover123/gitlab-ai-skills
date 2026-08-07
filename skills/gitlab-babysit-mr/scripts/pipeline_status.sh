#!/usr/bin/env bash
# pipeline_status.sh - Get MR pipeline status with failed jobs
# Usage: ./pipeline_status.sh [--blocking-only] <mr-url>
# Output: JSON with pipeline status, failed jobs, and counts

set -Eeuo pipefail

error_handler() {
  echo "Error: Command failed at line $1 with exit code $2" >&2
}

trap 'error_handler $LINENO $?' ERR

BLOCKING_ONLY=false
MR_URL=""

for arg in "$@"; do
  case "$arg" in
  --blocking-only)
    BLOCKING_ONLY=true
    ;;
  -*)
    echo "Unknown option: $arg" >&2
    exit 1
    ;;
  *)
    if [[ -n "$MR_URL" ]]; then
      echo "Only one MR URL may be provided." >&2
      exit 1
    fi

    MR_URL="$arg"
    ;;
  esac
done

if [[ -z "$MR_URL" ]]; then
  echo '{"error": "Usage: pipeline_status.sh [--blocking-only] <mr-url>"}' >&2
  exit 1
fi

# Parse URL: https://gitlab.com/group/[subgroup/]project/-/merge_requests/123
path="${MR_URL#https://gitlab.com/}"
PROJECT_PATH="${path%%/-/*}"
MR_IID="${MR_URL##*/}"
PROJECT_ENCODED="${PROJECT_PATH//\//%2F}"

# Get latest pipeline for this MR
echo "Fetching pipeline for MR ${MR_IID}..." >&2
PIPELINES_JSON=$(glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/pipelines?per_page=1" 2>/dev/null)

PIPELINE_ID=$(echo "$PIPELINES_JSON" | jq -r '.[0].id // empty')
if [[ -z "$PIPELINE_ID" ]]; then
  jq -n \
    --arg project "$PROJECT_PATH" \
    --arg mr_iid "$MR_IID" \
    '{"error": "No pipeline found for this MR", "project": $project, "mr_iid": $mr_iid}'
  exit 0
fi

PIPELINE_STATUS=$(echo "$PIPELINES_JSON" | jq -r '.[0].status')
PIPELINE_URL=$(echo "$PIPELINES_JSON" | jq -r '.[0].web_url')
PIPELINE_SHA=$(echo "$PIPELINES_JSON" | jq -r '.[0].sha[0:8]')

# Fetch only failed jobs while polling, avoiding pagination over every job in a
# large pipeline. The full mode still fetches all jobs for its status summary.
if [[ "$BLOCKING_ONLY" == true ]]; then
  echo "Fetching failed jobs for pipeline ${PIPELINE_ID}..." >&2
  ALL_JOBS=$(glab api --paginate "projects/${PROJECT_ENCODED}/pipelines/${PIPELINE_ID}/jobs?scope[]=failed&per_page=100" 2>/dev/null | jq -s 'add // []')
else
  echo "Fetching jobs for pipeline ${PIPELINE_ID}..." >&2
  ALL_JOBS=$(glab api --paginate "projects/${PROJECT_ENCODED}/pipelines/${PIPELINE_ID}/jobs?per_page=100" 2>/dev/null | jq -s 'add // []')
fi

# Extract current failed jobs (exclude jobs that were retried, i.e. superseded)
FAILED_JOBS=$(echo "$ALL_JOBS" | jq '[
  .[] |
  select(.status == "failed" and .retried != true) |
  {
    id,
    name,
    stage,
    status,
    failure_reason,
    web_url,
    allow_failure,
    retried
  }
]')

# Keep non-blocking failures in the full report, but do not expose them as
# candidates to the early-action polling mode.
BLOCKING_FAILED_JOBS=$(echo "$FAILED_JOBS" | jq '[.[] | select(.allow_failure != true)]')
BLOCKING_FAILURES=$(echo "$BLOCKING_FAILED_JOBS" | jq 'length')

if [[ "$BLOCKING_ONLY" == true ]]; then
  OUTPUT_FAILED_JOBS="$BLOCKING_FAILED_JOBS"
else
  OUTPUT_FAILED_JOBS="$FAILED_JOBS"
fi

OUTPUT=$(
  jq -n \
    --arg project "$PROJECT_PATH" \
    --arg project_encoded "$PROJECT_ENCODED" \
    --arg mr_iid "$MR_IID" \
    --arg pipeline_id "$PIPELINE_ID" \
    --arg pipeline_status "$PIPELINE_STATUS" \
    --arg pipeline_url "$PIPELINE_URL" \
    --arg pipeline_sha "$PIPELINE_SHA" \
    --argjson failed_jobs "$OUTPUT_FAILED_JOBS" \
    --argjson blocking_failures "$BLOCKING_FAILURES" \
    '{
    project: $project,
    project_encoded: $project_encoded,
    mr_iid: $mr_iid,
    pipeline_id: $pipeline_id,
    pipeline_status: $pipeline_status,
    pipeline_url: $pipeline_url,
    pipeline_sha: $pipeline_sha,
    failed_jobs: $failed_jobs,
    blocking_failure_count: $blocking_failures
  }'
)

if [[ "$BLOCKING_ONLY" == true ]]; then
  echo "$OUTPUT" | jq '. + {mode: "blocking_only"}'
else
  STATUS_SUMMARY=$(echo "$ALL_JOBS" | jq '
    group_by(.status) |
    map({key: .[0].status, value: length}) |
    from_entries
  ')
  echo "$OUTPUT" | jq --argjson status_summary "$STATUS_SUMMARY" '. + {status_summary: $status_summary}'
fi
