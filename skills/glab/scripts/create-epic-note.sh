#!/usr/bin/env bash
# Post a comment on a group-level epic.
#
# Usage:
#   create-epic-note.sh <group-id> <epic-iid> "comment body"
#
# Arguments:
#   group-id    Numeric group ID (get with: glab api "groups/my-group%2Fpath" | jq '.id')
#   epic-iid    Epic display number (iid), e.g. 16428
#   body        Comment text (quoted)
#
# Examples:
#   create-epic-note.sh 9970 16428 "This needs more context before we proceed."
#   create-epic-note.sh 12627982 15 "Fifth week kickoff looks good!"
#
# Output: JSON with the created note's id, body, author, and createdAt
#
# Requires: glab (authenticated), jq

set -euo pipefail

GROUP_ID="${1:?Usage: create-epic-note.sh <group-id> <epic-iid> \"body\"}"
EPIC_IID="${2:?Usage: create-epic-note.sh <group-id> <epic-iid> \"body\"}"
BODY="${3:?Usage: create-epic-note.sh <group-id> <epic-iid> \"body\"}"

# Resolve directory of this script to find the .graphql template
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATE="$SKILL_DIR/assets/graphql/create-note.graphql"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "ERROR: template not found at $TEMPLATE" >&2
  exit 1
fi

# Get the epic's internal (global) ID — the createNote mutation requires it
EPIC_DATA=$(glab api "groups/${GROUP_ID}/epics/${EPIC_IID}" 2>&1)
if echo "$EPIC_DATA" | grep -q '^glab:'; then
  echo "ERROR fetching epic: $EPIC_DATA" >&2
  exit 1
fi

EPIC_INTERNAL_ID=$(echo "$EPIC_DATA" | jq -r '.id')
NOTEABLE_ID="gid://gitlab/Epic/${EPIC_INTERNAL_ID}"

# Escape the body for safe embedding in the GraphQL string:
# backslash → \\, double-quote → \", newline → \n
ESCAPED_BODY=$(printf '%s' "$BODY" \
  | sed 's/\\/\\\\/g' \
  | sed 's/"/\\"/g' \
  | awk '{printf "%s\\n", $0}' \
  | sed 's/\\n$//')

# Substitute placeholders in the template
query=$(sed \
  -e "s|\\\$NOTEABLE_ID|${NOTEABLE_ID}|g" \
  -e "s|\\\$BODY|${ESCAPED_BODY}|g" \
  "$TEMPLATE")

response=$(glab api graphql -f "query=${query}" 2>&1)

# Detect glab errors
if echo "$response" | grep -q '^glab:'; then
  echo "ERROR from glab: $response" >&2
  exit 1
fi

# Check for GraphQL errors
errors=$(echo "$response" | jq -r '.data.createNote.errors // [] | .[]' 2>/dev/null || true)
if [[ -n "$errors" ]]; then
  echo "ERROR from GraphQL: $errors" >&2
  exit 1
fi

echo "$response" | jq '.data.createNote.note'
