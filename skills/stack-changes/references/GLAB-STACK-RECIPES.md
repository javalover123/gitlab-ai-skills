# glab stack recipes

Command sequences for executing the split and handing off sync.

## On-disk model

```
.git/stacked/<name>/
├── BASE_BRANCH                    # text: base branch name
└── <id>.json                      # one per diff; <id> is glab-internal, NOT a git SHA
```

Each JSON:

```json
{"prev":"<id|empty>","next":"<id|empty>","sha":"<id>","branch":"<prefix>-<name>-<id>","mr":"<WebURL after sync>","description":"<title>"}
```

`<prefix>` is the `branch_prefix` setting in `glab` config, falling back to local `$USER` — NOT the GitLab username.

Plus git config: `glab.currentstack=<name>`. Read JSONs directly — `glab stack list` has no machine-readable mode and is TTY-only.

## Stash excluded files (if user opted any out)

```bash
git stash push --include-untracked -m "stack-changes:excluded:$stack_name" -- <files>
```

## Save loop

```bash
glab stack create "$stack_name"        # idempotent
for group in plan.groups:
  git restore --staged .
  for f in group.files: git add -- "$f"
  expected=$(printf '%s\n' "${group_files[@]}" | sort -u)
  actual=$(git diff --cached --name-only --diff-filter=AMRD | sort -u)
  [ "$expected" = "$actual" ] || abort_and_print_recovery
  glab stack save -m "$group.title"    # single-line title only
  # HEAD is now on the new tip. Do NOT git checkout or glab stack navigate.
```

Notes:
- `glab stack save` errors cleanly if the index is empty.
- Titles must be single-line. `glab stack sync` splits description at first `\n` and has a latent title-truncation bug; single-line sidesteps it.

## Verify

Walk the linked list from root (`prev==""`) to tip (`next==""`); compare to plan.

```bash
root=$(grep -l '"prev":""' .git/stacked/$stack_name/*.json | head -1)
current="$root"; i=1
while [ -n "$current" ]; do
  desc=$(jq -r .description "$current")
  next_id=$(jq -r .next "$current")
  echo "[$i] $desc"
  [ -z "$next_id" ] && break
  current=".git/stacked/$stack_name/${next_id}.json"
  i=$((i+1))
done
```

Counts must match. Titles must match. If not, print recovery and stop.

## Sync handoff

Say to the user, verbatim:

> Running `glab stack sync` will: force-with-lease push every stack branch to origin; create one MR per diff (root targets `<base>`, others target the previous diff's branch); assign you as author; send notifications immediately. MRs are NOT drafts — `glab stack sync` has no draft flag. When MR #1 is merged, MR #2's target is NOT auto-updated — you retarget child MRs in the UI after each parent merge. Rebase conflicts during sync are unrecoverable and leave the working tree mid-rebase.

Then point them at "Post-sync drafting" below for converting MRs to drafts after they sync.

Source: [stack_sync.go](https://gitlab.com/gitlab-org/cli/-/blob/main/internal/commands/stack/sync/stack_sync.go).

## Post-sync drafting

After the user runs `glab stack sync`, the `mr` field of each `.git/stacked/<name>/*.json` holds the MR WebURL. Extract the IID (last numeric segment) and update:

```bash
for f in .git/stacked/$stack_name/*.json; do
  url=$(jq -r '.mr // empty' "$f"); [ -z "$url" ] && continue
  iid=$(printf '%s' "$url" | grep -oE '[0-9]+$')
  [ -n "$iid" ] && glab mr update "$iid" --draft
done
```

Don't use `glab mr list --source-branch` — `-s` matches only exact names, not patterns.

## Forbidden

- `glab stack sync` — out of scope; user's call.
- `glab stack amend` — leaves downstream branches inconsistent until next sync.
- `glab stack reorder` — TTY-only; errors from non-interactive context.
- `glab stack list` — TTY-only; walk `.git/stacked/<name>/*.json` instead (see [Verify](#verify)).
- `glab stack save -a` (misses untracked) or `glab stack save .` (picks up noise).
- `git checkout` / `git switch` between saves.
