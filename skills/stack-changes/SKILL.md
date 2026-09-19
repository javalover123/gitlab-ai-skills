---
name: stack-changes
description: Splits a large local change (uncommitted or committed) into a stacked-MR chain. Use when the user asks to split an MR they find too big to review, wants stacked diffs, has sprawling AI-mode work to publish, or types /stack-changes.
version: 0.1.1
category: Development Workflow
license: MIT
metadata:
  audience: developers
  author: gitlab
  workflow: gitlab
  slash-command: enabled
---

Split a large local change into a 2-4 layer `glab stack`. Operate locally — never run `glab stack sync`.

**vs. `gitlab-stacked-mrs`:** this skill only does the one-shot split and
handoff. Once MRs are open, use `gitlab-stacked-mrs` for the ongoing
lifecycle — opening MRs, feedback triage, re-syncing after merges, merging.

## 1. Refuse if any of these fail

- `git` and `glab` present; `glab auth status` OK.
- Inside a git repo; `origin` URL contains `gitlab`.
- HEAD is a branch (not detached).
- Current branch is not `main`/`master`/`develop`/`trunk` and does not match `^release[/-].*`.
- `git config --get glab.currentstack` exits non-zero (no active stack — else print [recovery](#recovery)).

State the specific failure; do not proceed.

## 2. Detect base and mode

```bash
base=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|origin/||')
[ -n "$base" ] || base=main
git show-ref --verify --quiet "refs/remotes/origin/$base" || ask_user "which base branch?"
ahead=$(git rev-list --count "origin/$base..HEAD")
dirty=$( [ -n "$(git status --porcelain)" ] && echo 1 || echo 0 )
```

| dirty | ahead | mode | action |
|---|---|---|---|
| 1 | 0 | uncommitted | proceed to §3 |
| 0 | ≥1 | committed | see below |
| 1 | ≥1 | mixed | refuse: have user commit or stash first |
| 0 | 0 | empty | refuse: nothing to split |

**Committed mode.** Show `git log --oneline origin/$base..HEAD`. If `ahead==1`, `split_from`=that commit. Else ask the user which commit (inclusive) starts the work; record as `split_from`.

## 3. Backup (always, before any destructive op)

```bash
backup_tag="$(git symbolic-ref --short HEAD)-pre-stack-$(date +%Y%m%dT%H%M%S)"
git tag -a "$backup_tag" -m "stack-changes" HEAD
```

Surface `$backup_tag` in every user-facing message from here on. **Now**, in committed mode, run `git reset --soft "$split_from^"` — the diff moves into the index, the backup tag still points at the original HEAD.

## 4. Capture the diff

```bash
git diff --cached --numstat                # committed mode: post-reset, staged
git diff --numstat                          # uncommitted mode: unstaged
git ls-files --others --exclude-standard    # untracked (both modes)
```

Ask the user which files (if any) to exclude from the split (.env, scratch, drive-by). Record them.

## 5. Plan

Plan per [references/GROUPING-HEURISTICS.md](references/GROUPING-HEURISTICS.md): build the JSON in its schema, self-check against its hard rules, revise until all pass.

## 6. Approve

Render the plan as a readable summary (per group: order, title, files with line counts, rationale). Ask: "Proceed with this split?". Accept only an explicit affirmative. Otherwise ask what to change, revise, repeat. Never partially execute.

## 7. Execute

Follow [references/GLAB-STACK-RECIPES.md](references/GLAB-STACK-RECIPES.md). Critical:

> Between `glab stack save` calls, do not move HEAD — no `git checkout`/`switch`, no `glab stack` navigation. A move makes the next save create a sibling, silently breaking the stack (no warning).

On any failure: stop, print [recovery](#recovery), exit. Never auto-recover.

## 8. Hand off sync (never run it)

Print the stack list — re-use the [Verify](references/GLAB-STACK-RECIPES.md#verify) walk; `glab stack list` is TTY-only. Then do the [Sync handoff](references/GLAB-STACK-RECIPES.md#sync-handoff): say its verbatim message.

If the user asks to sync: refuse and re-print the handoff. Sync is theirs to run.

## Recovery

Print verbatim, interpolating `$STACK_NAME`, `$ORIGINAL_BRANCH`, `$BACKUP_TAG`. Never auto-run.

```bash
git config --unset glab.currentstack
rm -rf .git/stacked/$STACK_NAME
git branch | awk '{print $NF}' | grep -E "^.+-$STACK_NAME-[a-f0-9]{8}$" | xargs -r git branch -D
git checkout $ORIGINAL_BRANCH
git reset --hard $BACKUP_TAG
# If excluded files were stashed: git stash list | grep stack-changes:excluded:$STACK_NAME; git stash pop <ref>
# When you're sure: git tag -d $BACKUP_TAG
```

## Forbidden

- `glab stack sync`, `glab stack amend`, `glab stack reorder`.
- `glab stack list` (TTY-only — walk `.git/stacked/<name>/*.json` instead).
- `glab stack save -a` (misses untracked), `glab stack save .` (picks up noise).
- `git checkout` or `git switch` between `glab stack save` calls.
- Splitting a single file across groups (file-level granularity only).
- Operating without `origin` or with a non-GitLab origin.
