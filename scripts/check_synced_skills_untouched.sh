#!/usr/bin/env bash
# Block contributor edits to externally-synced skills on merge request pipelines.
#
# Skills listed in synced-skills.yml have their source of truth in another
# repository; this repo is only the destination. Direct edits here would be
# silently overwritten by the next scheduled sync, so we fail the MR pipeline
# and point the author at the source.
#
# The scheduled sync job is exempt: it runs as the project access token bot
# (GITLAB_USER_LOGIN matches project_<id>_bot_<hex> or the legacy
# project_<id>_bot<n>) and pushes from a sync/* branch, so its own MR is
# allowed to touch these paths.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO_ROOT/synced-skills.yml"

if [[ ! -f "$MANIFEST" ]]; then
  echo "No $MANIFEST found; nothing to guard."
  exit 0
fi

# Exempt the sync bot's own MR.
if [[ "${GITLAB_USER_LOGIN:-}" =~ ^project_[0-9]+_bot(_[0-9a-f]+|[0-9]*)$ ]]; then
  echo "Pipeline run by sync bot ($GITLAB_USER_LOGIN); skipping synced-skill guard."
  exit 0
fi
if [[ "${CI_COMMIT_REF_NAME:-}" == sync/* ]]; then
  echo "Sync branch (${CI_COMMIT_REF_NAME}); skipping synced-skill guard."
  exit 0
fi

# Collect the guarded skill directories from the manifest. The manifest is a
# flat two-level mapping under `skills:`; the skill names are the keys indented
# by exactly two spaces and ending in a colon.
guarded=()
in_skills=0
while IFS= read -r line; do
  # Strip trailing CR just in case.
  line="${line%$'\r'}"
  case "$line" in
    \#*) continue ;;
    "") continue ;;
  esac
  if [[ "$line" =~ ^[^[:space:]] ]]; then
    if [[ "$line" == "skills:" ]]; then in_skills=1; else in_skills=0; fi
    continue
  fi
  if [[ "$in_skills" -eq 1 && "$line" =~ ^"  "([A-Za-z0-9_-]+):[[:space:]]*$ ]]; then
    guarded+=("skills/${BASH_REMATCH[1]}/")
  fi
done < "$MANIFEST"

if [[ ${#guarded[@]} -eq 0 ]]; then
  echo "No synced skills listed; nothing to guard."
  exit 0
fi

# Determine the merge base to diff against.
BASE="${CI_MERGE_REQUEST_DIFF_BASE_SHA:-}"
if [[ -z "$BASE" ]]; then
  TARGET="${CI_MERGE_REQUEST_TARGET_BRANCH_NAME:-${CI_DEFAULT_BRANCH:-main}}"
  git fetch --depth=50 origin "$TARGET" >/dev/null 2>&1 || true
  BASE="$(git merge-base "origin/$TARGET" HEAD 2>/dev/null || echo "origin/$TARGET")"
fi

changed_files="$(git diff --name-only "$BASE"...HEAD)"

violations=()
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  for dir in "${guarded[@]}"; do
    if [[ "$file" == "$dir"* ]]; then
      violations+=("$file")
    fi
  done
done <<< "$changed_files"

if [[ ${#violations[@]} -gt 0 ]]; then
  echo "ERROR: This MR edits skills that are synced from another repository." >&2
  echo "These skills are read-only here; fix them at their source of truth" >&2
  echo "(see synced-skills.yml). Offending files:" >&2
  for v in "${violations[@]}"; do
    echo "  - $v" >&2
  done
  exit 1
fi

echo "No synced-skill files were modified."
