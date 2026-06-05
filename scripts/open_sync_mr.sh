#!/usr/bin/env bash
# Run the inbound skill sync and, if it produced changes, push a branch and
# open (or update) an MR. Intended to run from the scheduled `sync-skills` CI
# job as the project access token bot.
#
# All the content mirroring lives in scripts/sync_external_skills.py; this
# script only adds the git/MR ceremony so that logic stays testable in
# isolation.
#
# Required environment (set by the CI job):
#   CI_DEFAULT_BRANCH, CI_COMMIT_SHORT_SHA  - GitLab CI predefined vars
# Optional:
#   SYNC_MR_LABELS  - comma-separated labels to apply to the MR
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TARGET_BRANCH="${CI_DEFAULT_BRANCH:-main}"
SHORT_SHA="${CI_COMMIT_SHORT_SHA:-manual}"
BRANCH="sync/skills-${SHORT_SHA}"
TITLE="chore: sync externally-managed skills"

# 1. Mirror upstream into the working tree (no auto-fix yet — we want to know
#    whether anything actually changed before regenerating artifacts).
python3 scripts/sync_external_skills.py --no-auto-fix --debug

if git diff --quiet && git diff --cached --quiet; then
  echo "No changes from sync; nothing to do."
  exit 0
fi

# 2. Regenerate distribution artifacts (README, ToC, catalog, plugin version
#    manifests). Prefer lefthook's auto-fix when available; otherwise run the
#    same steps directly so the job works in images without lefthook (e.g. the
#    glab CLI image). Keep this list in sync with lefthook.yml's auto-fix hook.
if command -v lefthook >/dev/null 2>&1; then
  lefthook run auto-fix
else
  echo "lefthook not found; running auto-fix steps directly." >&2
  python3 scripts/update_skills_list.py
  python3 scripts/update_toc.py
  python3 scripts/generate_catalog.py
  python3 scripts/update_claudecode_readme.py
  bin/sync-skill
fi

# 3. Commit on a fresh branch.
git checkout -b "$BRANCH"
git add -A
git commit \
  -m "$TITLE" \
  -m "Automated by the sync-skills scheduled pipeline."
git push -u origin "$BRANCH"

# 4. Open the MR. Skip if one already exists for this branch.
existing="$(glab mr list --source-branch "$BRANCH" --output json 2>/dev/null || echo '[]')"
if [ "$(echo "$existing" | jq 'length')" -gt 0 ]; then
  echo "MR already exists for $BRANCH; nothing to open."
  exit 0
fi

label_args=()
if [ -n "${SYNC_MR_LABELS:-}" ]; then
  IFS=',' read -ra _labels <<< "$SYNC_MR_LABELS"
  for l in "${_labels[@]}"; do
    label_args+=(--label "$l")
  done
fi

description="Automated sync of skills whose source of truth lives in another repository (see \`synced-skills.yml\`).

Review the diff to confirm it matches the upstream change, then merge."

glab mr create \
  --source-branch "$BRANCH" \
  --target-branch "$TARGET_BRANCH" \
  --title "$TITLE" \
  --remove-source-branch \
  --yes \
  "${label_args[@]}" \
  --description "$description"
