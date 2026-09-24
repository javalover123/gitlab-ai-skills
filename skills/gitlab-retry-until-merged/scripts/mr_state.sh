#!/usr/bin/env bash
# mr_state.sh - Read-only snapshot of an MR's merge state and latest pipeline
# Usage: ./mr_state.sh [--files] <mr-url>
# Output: JSON with MR state, auto-merge flag, head SHA, latest pipeline, and
#         its blocking failed jobs and bridges. --files adds the MR's changed
#         file paths (for correlating failures with the MR's changes).
#
# Never writes anything: every call is a GET.

set -Eeuo pipefail

error_handler() {
  echo "Error: Command failed at line $1 with exit code $2" >&2
}

trap 'error_handler $LINENO $?' ERR

WITH_FILES=false
MR_URL=""

for arg in "$@"; do
  case "$arg" in
  --files)
    WITH_FILES=true
    ;;
  -*)
    echo "Unknown option: $arg" >&2
    exit 2
    ;;
  *)
    if [[ -n "$MR_URL" ]]; then
      echo "Only one MR URL may be provided." >&2
      exit 2
    fi
    MR_URL="$arg"
    ;;
  esac
done

if [[ -z "$MR_URL" ]]; then
  echo "Usage: $0 [--files] <mr-url>" >&2
  exit 2
fi

# Parse URL: https://gitlab.com/group/[subgroup/]project/-/merge_requests/123
path="${MR_URL#https://gitlab.com/}"
PROJECT_PATH="${path%%/-/*}"
MR_IID="${MR_URL##*/}"
MR_IID="${MR_IID%%[?#]*}"
PROJECT_ENCODED="${PROJECT_PATH//\//%2F}"

MR_JSON=$(glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}")

# The MR pipelines list, not head_pipeline: head_pipeline can be null while
# GitLab is still checking mergeability.
PIPELINES_JSON=$(glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/pipelines?per_page=1")
PIPELINE_ID=$(echo "$PIPELINES_JSON" | jq -r '.[0].id // empty')

PIPELINE='null'
FAILED_JOBS='[]'
FAILED_BRIDGES='[]'

if [[ -n "$PIPELINE_ID" ]]; then
  PIPELINE=$(echo "$PIPELINES_JSON" | jq '.[0] | {
    id,
    status,
    ref,
    sha,
    web_url,
    source,
    kind: (
      if (.ref | test("^refs/merge-requests/[0-9]+/train$")) then "merge_train"
      elif (.ref | test("^refs/merge-requests/[0-9]+/merge$")) then "merged_result"
      elif (.ref | test("^refs/merge-requests/[0-9]+/head$")) then "detached"
      else "branch" end
    )
  }')

  # Failed, not superseded by a retry, and blocking (allow_failure jobs cannot
  # stop the merge).
  FAILED_JOBS=$(glab api --paginate "projects/${PROJECT_ENCODED}/pipelines/${PIPELINE_ID}/jobs?scope[]=failed&per_page=100" |
    jq -s '[add // [] | .[] | select(.status == "failed" and .retried != true and .allow_failure != true) | {
      id,
      name,
      stage,
      failure_reason,
      web_url
    }]')

  # Trigger jobs for child/downstream pipelines. Their failures hide inside the
  # downstream pipeline, so surface where to look.
  FAILED_BRIDGES=$(glab api --paginate "projects/${PROJECT_ENCODED}/pipelines/${PIPELINE_ID}/bridges?scope[]=failed&per_page=100" |
    jq -s '[add // [] | .[] | select(.status == "failed" and .retried != true and .allow_failure != true) | {
      id,
      name,
      stage,
      failure_reason,
      downstream_project_id: .downstream_pipeline.project_id,
      downstream_pipeline_id: .downstream_pipeline.id,
      downstream_web_url: .downstream_pipeline.web_url
    }]')
fi

OUTPUT=$(echo "$MR_JSON" | jq \
  --arg project "$PROJECT_PATH" \
  --arg project_encoded "$PROJECT_ENCODED" \
  --argjson pipeline "$PIPELINE" \
  --argjson failed_jobs "$FAILED_JOBS" \
  --argjson failed_bridges "$FAILED_BRIDGES" \
  '{
    project: $project,
    project_encoded: $project_encoded,
    mr_iid: (.iid | tostring),
    web_url,
    title,
    author: .author.username,
    state,
    sha,
    source_branch,
    target_branch,
    auto_merge: (.merge_when_pipeline_succeeds == true),
    merge_user: .merge_user.username,
    detailed_merge_status,
    merge_error,
    pipeline: $pipeline,
    failed_jobs: $failed_jobs,
    failed_bridges: $failed_bridges,
    blocking_failure_count: (($failed_jobs | length) + ($failed_bridges | length))
  }')

if [[ "$WITH_FILES" == true ]]; then
  CHANGED_FILES=$(glab api --paginate "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/diffs?per_page=100" |
    jq -s '[add // [] | .[] | .new_path, .old_path] | unique')
  echo "$OUTPUT" | jq --argjson files "$CHANGED_FILES" '. + {changed_files: $files}'
else
  echo "$OUTPUT"
fi
