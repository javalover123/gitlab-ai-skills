#!/usr/bin/env bash
# Fetch all notes (comments) on a group-level epic, handling pagination.
#
# Usage:
#   epic-notes.sh <group-path> <epic-iid> [page-size]
#
# Arguments:
#   group-path  Group fullPath, plain slashes: "gitlab-org" or "gitlab-org/foundations"
#   epic-iid    Epic display number (iid), e.g. 16428
#   page-size   Discussions per page (default: 100). Most epics fit in one page.
#
# Examples:
#   epic-notes.sh gitlab-org 16428
#   epic-notes.sh gitlab-org/foundations 15
#   epic-notes.sh gitlab-org 16428 20   # force pagination for testing
#
# Output: JSON array of all notes, one line per note:
#   {"id":"gid://...","body":"...","author":{"username":"..."},"createdAt":"..."}
#
# Requires: glab (authenticated), jq

set -euo pipefail

GROUP_PATH="${1:?Usage: epic-notes.sh <group-path> <epic-iid> [page-size]}"
EPIC_IID="${2:?Usage: epic-notes.sh <group-path> <epic-iid> [page-size]}"
PAGE_SIZE="${3:-100}"

# Resolve directory of this script to find the .graphql template
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATE="$SKILL_DIR/assets/graphql/epic-notes.graphql"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "ERROR: template not found at $TEMPLATE" >&2
  exit 1
fi

cursor=""
page=0
all_notes='[]'

while true; do
  page=$((page + 1))

  # Build the discussions argument: add after: cursor on pages > 1
  if [[ -z "$cursor" ]]; then
    discussions_arg="discussions(first: ${PAGE_SIZE})"
  else
    discussions_arg="discussions(first: ${PAGE_SIZE}, after: \"${cursor}\")"
  fi

  # Substitute placeholders in the template
  query=$(sed \
    -e "s|\\\$GROUP_PATH|${GROUP_PATH}|g" \
    -e "s|\\\$EPIC_IID|${EPIC_IID}|g" \
    -e "s|discussions(first: \\\$PAGE_SIZE)|${discussions_arg}|g" \
    "$TEMPLATE")

  response=$(glab api graphql -f "query=${query}" 2>&1)

  # Detect glab errors
  if echo "$response" | grep -q '^glab:'; then
    echo "ERROR from glab: $response" >&2
    exit 1
  fi

  # Extract notes from this page
  page_notes=$(echo "$response" | jq '
    [.data.group.workItem.widgets[]
      | select(.type == "NOTES")
      | .discussions.nodes[]
      | .notes.nodes[]
    ]')

  all_notes=$(jq -n --argjson acc "$all_notes" --argjson new "$page_notes" '$acc + $new')

  has_next=$(echo "$response" | jq -r '
    .data.group.workItem.widgets[]
    | select(.type == "NOTES")
    | .discussions.pageInfo.hasNextPage')

  cursor=$(echo "$response" | jq -r '
    .data.group.workItem.widgets[]
    | select(.type == "NOTES")
    | .discussions.pageInfo.endCursor // ""')

  if [[ "$has_next" != "true" ]]; then
    break
  fi
done

echo "$all_notes" | jq '.[]'
