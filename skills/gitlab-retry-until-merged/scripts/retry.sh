#!/usr/bin/env bash
# retry.sh - The only write this skill makes: re-run CI for an MR.
# Usage:
#   ./retry.sh --expect-sha <sha> <mr-url> pipeline <pipeline-id>
#       Retry the failed jobs of an existing MR pipeline (same commit).
#   ./retry.sh --expect-sha <sha> <mr-url> new-pipeline
#       Start a fresh MR pipeline (a merged-results pipeline picks up the
#       current target branch; the MR's source branch is untouched).
#
# Before writing, re-reads the MR and refuses (exit 3, nothing written) unless:
#   - the MR is still open,
#   - auto-merge is still set,
#   - the MR head SHA still equals --expect-sha (nobody pushed since triage),
#   - for `pipeline`: the pipeline belongs to this MR and is not a merge train
#     pipeline (GitLab cannot retry those; the MR has to be re-added).
#
# Exit codes: 0 retried, 2 usage error, 3 precondition failed (no write).
# Output: JSON describing what was done, or why it was refused.

set -Eeuo pipefail

error_handler() {
  echo "Error: Command failed at line $1 with exit code $2" >&2
}

trap 'error_handler $LINENO $?' ERR

usage() {
  echo "Usage: $0 --expect-sha <sha> <mr-url> pipeline <pipeline-id>" >&2
  echo "       $0 --expect-sha <sha> <mr-url> new-pipeline" >&2
  exit 2
}

refuse() {
  jq -n --arg reason "$1" '{retried: false, reason: $reason}'
  exit 3
}

EXPECT_SHA=""
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
  --expect-sha)
    [[ $# -ge 2 ]] || usage
    EXPECT_SHA="$2"
    shift 2
    ;;
  -*)
    usage
    ;;
  *)
    POSITIONAL+=("$1")
    shift
    ;;
  esac
done

[[ -n "$EXPECT_SHA" && ${#POSITIONAL[@]} -ge 2 ]] || usage

MR_URL="${POSITIONAL[0]}"
MODE="${POSITIONAL[1]}"
PIPELINE_ID="${POSITIONAL[2]:-}"

case "$MODE" in
pipeline)
  [[ "$PIPELINE_ID" =~ ^[0-9]+$ && ${#POSITIONAL[@]} -eq 3 ]] || usage
  ;;
new-pipeline)
  [[ ${#POSITIONAL[@]} -eq 2 ]] || usage
  ;;
*)
  usage
  ;;
esac

path="${MR_URL#https://gitlab.com/}"
PROJECT_PATH="${path%%/-/*}"
MR_IID="${MR_URL##*/}"
MR_IID="${MR_IID%%[?#]*}"
PROJECT_ENCODED="${PROJECT_PATH//\//%2F}"

# --- Preconditions (read-only) ---------------------------------------------
MR_JSON=$(glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}")
MR_STATE=$(echo "$MR_JSON" | jq -r '.state')
MR_SHA=$(echo "$MR_JSON" | jq -r '.sha')
AUTO_MERGE=$(echo "$MR_JSON" | jq -r '.merge_when_pipeline_succeeds == true')

[[ "$MR_STATE" == "opened" ]] || refuse "MR is ${MR_STATE}, not open"
[[ "$AUTO_MERGE" == "true" ]] || refuse "auto-merge is no longer set on the MR"
[[ "$MR_SHA" == "$EXPECT_SHA" ]] ||
  refuse "MR head moved from ${EXPECT_SHA} to ${MR_SHA}: new commits need review"

if [[ "$MODE" == "pipeline" ]]; then
  PIPELINE_REF=$(glab api --paginate "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/pipelines?per_page=100" |
    jq -rs --argjson id "$PIPELINE_ID" '[add // [] | .[] | select(.id == $id) | .ref] | first // empty')

  [[ -n "$PIPELINE_REF" ]] || refuse "pipeline ${PIPELINE_ID} is not a pipeline of this MR"
  if [[ "$PIPELINE_REF" =~ /train$ ]]; then
    refuse "pipeline ${PIPELINE_ID} is a merge train pipeline and cannot be retried"
  fi
fi

# --- Write -----------------------------------------------------------------
if [[ "$MODE" == "pipeline" ]]; then
  RESULT=$(glab api --method POST "projects/${PROJECT_ENCODED}/pipelines/${PIPELINE_ID}/retry")
else
  RESULT=$(glab api --method POST "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/pipelines")
fi

echo "$RESULT" | jq --arg mode "$MODE" '{
  retried: true,
  mode: $mode,
  pipeline_id: .id,
  status,
  web_url
}'
