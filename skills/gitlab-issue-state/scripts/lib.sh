#!/usr/bin/env bash
# Shared helpers for the gitlab-issue-state skill.
# Not executable on its own; sourced by the other scripts.

set -Eeuo pipefail

# Scripts call `glab` directly, expecting it authenticated on PATH. If your
# glab is wrapped (e.g. a 1Password shell plugin, so the interactive alias
# isn't visible to scripts), set GLAB_CMD to the wrapper before invoking any
# script in this skill, e.g.:
#   export GLAB_CMD="op plugin run -- glab"
glab() {
  if [[ -n "${GLAB_CMD:-}" ]]; then
    # shellcheck disable=SC2086
    ${GLAB_CMD} "$@"
  elif command -v glab >/dev/null 2>&1; then
    command glab "$@"
  else
    echo "error: glab not found on PATH (set GLAB_CMD if it needs a wrapper)" >&2
    return 127
  fi
}

die() {
  echo "error: $*" >&2
  exit 1
}

# Parse an issue/work-item reference into PROJECT_PATH and ISSUE_IID.
# Accepts either:
#   - a full URL: https://gitlab.com/group/sub/project/-/issues/123
#                 https://gitlab.com/group/sub/project/-/work_items/123
#   - an IID plus -R/--repo <owner/repo>: 123 -R group/project
# Exports: PROJECT_PATH (raw, unencoded) and ISSUE_IID.
parse_issue_ref() {
  local ref="${1:-}"
  shift || true
  local repo=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -R | --repo)
        repo="$2"
        shift 2
        ;;
      *) shift ;;
    esac
  done

  [[ -n "$ref" ]] || die "missing issue reference (URL or IID)"

  if [[ "$ref" == http*://* ]]; then
    # Strip scheme+host, then split on /-/issues|work_items/
    local path="${ref#*://}"
    path="${path#*/}" # drop host
    if [[ "$path" =~ ^(.+)/-/(issues|work_items)/([0-9]+) ]]; then
      PROJECT_PATH="${BASH_REMATCH[1]}"
      ISSUE_IID="${BASH_REMATCH[3]}"
    else
      die "could not parse project/iid from URL: $ref"
    fi
  else
    [[ "$ref" =~ ^[0-9]+$ ]] || die "expected numeric IID or a URL, got: $ref"
    [[ -n "$repo" ]] || die "IID given without -R <owner/repo>"
    ISSUE_IID="$ref"
    PROJECT_PATH="$repo"
  fi

  export PROJECT_PATH ISSUE_IID
}

# URL-encode a project path for REST calls (/ -> %2F).
enc_path() {
  printf '%s' "$1" | sed 's#/#%2F#g'
}

# Resolve the GraphQL global ID for an issue (work item).
# Requires PROJECT_PATH and ISSUE_IID to be set.
work_item_gid() {
  glab api graphql -f query="
{
  project(fullPath: \"${PROJECT_PATH}\") {
    workItems(first: 1, iid: \"${ISSUE_IID}\") { nodes { id } }
  }
}" | jq -r '.data.project.workItems.nodes[0].id // empty'
}

# Statuses in these lifecycle categories are terminal: something (usually the
# close automation, or a human) has already decided the outcome. Don't move an
# issue out of them just because its MRs look a certain way.
# shellcheck disable=SC2034  # consumed by sourcing scripts (sync-issue-state.sh)
TERMINAL_STATUS_CATEGORIES='["done","canceled"]'

# Print the issue's current status as compact JSON: {"name":...,"category":...}
# Prints nothing if the work item has no status set or no STATUS widget.
# Requires PROJECT_PATH and ISSUE_IID to be set.
current_status_json() {
  glab api graphql -f query="
{
  project(fullPath: \"${PROJECT_PATH}\") {
    workItems(first: 1, iid: \"${ISSUE_IID}\") {
      nodes {
        widgets { ... on WorkItemWidgetStatus { status { name category } } }
      }
    }
  }
}" | jq -c '[.data.project.workItems.nodes[0].widgets[]?
             | select(.status != null) | .status] | .[0] // empty'
}
