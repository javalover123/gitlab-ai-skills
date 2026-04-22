#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <project_path> <target_type> <iid>" >&2
  echo "  project_path  e.g. gitlab-org/gitlab" >&2
  echo "  target_type   MergeRequest or Issue" >&2
  echo "  iid           target IID" >&2
  exit 1
}

[[ $# -eq 3 ]] || usage

project_path="$1"
target_type="$2"
iid="$3"

encoded_project="${project_path//\//%2F}"

case "$target_type" in
  MergeRequest) endpoint="projects/${encoded_project}/merge_requests/${iid}" ;;
  Issue)        endpoint="projects/${encoded_project}/issues/${iid}" ;;
  *)            echo "Unknown target_type: $target_type" >&2; exit 1 ;;
esac

glab api "$endpoint" | jq '{
  milestone: .milestone.title,
  milestone_due: .milestone.due_date,
  labels: .labels
}'
