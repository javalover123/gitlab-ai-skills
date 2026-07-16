# Smart Rebase — commands

The exact git commands for each phase. Run them and present the results to the
user as described in the main `SKILL.md`.

## Discovery

Map the branch topology:

```bash
# Current branch
CURRENT=$(git rev-parse --abbrev-ref HEAD)

# Upstream tracking branch (may not exist)
UPSTREAM=$(git rev-parse --abbrev-ref "@{upstream}" 2>/dev/null || echo "none")

# Default branch — check remote HEAD, fall back to main/master detection
DEFAULT=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
if [ -z "$DEFAULT" ]; then
  for candidate in main master; do
    git show-ref --verify --quiet "refs/remotes/origin/$candidate" && DEFAULT=$candidate && break
  done
fi

# Bail out if the default branch couldn't be detected — otherwise the
# commands below silently operate on the bare ref "origin/".
if [ -z "$DEFAULT" ]; then
  echo "ERROR: could not detect the default branch. Set it manually, e.g. DEFAULT=main." >&2
  exit 1
fi

# Fetch latest state from remote
git fetch origin "$DEFAULT" --quiet

# Merge base
MERGE_BASE=$(git merge-base HEAD "origin/$DEFAULT")

# Divergence
DEFAULT_COMMITS=$(git rev-list --count "$MERGE_BASE..origin/$DEFAULT")
CURRENT_COMMITS=$(git rev-list --count "$MERGE_BASE..HEAD")
if [ "$UPSTREAM" != "none" ]; then
  UPSTREAM_COMMITS=$(git rev-list --count "$MERGE_BASE..$UPSTREAM")
fi
```

Present the topology to the user:

```
Branch topology:
  Default branch:  origin/{DEFAULT}  ({DEFAULT_COMMITS} commits ahead of merge base)
  Current branch:  {CURRENT}         ({CURRENT_COMMITS} commits ahead of merge base)
  Upstream:        {UPSTREAM}         ({UPSTREAM_COMMITS} commits ahead of merge base)
  Merge base:      {MERGE_BASE_SHORT}

  origin/{DEFAULT}:  A---B---C---D---E  (new work on default branch)
                    /
  merge base:  ----X
                    \
  {CURRENT}:        F---G---H---I      (your feature work)
```

## Analysis

```bash
# Files changed on default branch since merge base
git diff --name-status "$MERGE_BASE" "origin/$DEFAULT"

# Files changed on current branch since merge base
git diff --name-status "$MERGE_BASE" HEAD
```

For every **Both-modified** file, show both sides at file and commit level:

```bash
git diff "$MERGE_BASE" "origin/$DEFAULT" -- path/to/file   # default side
git diff "$MERGE_BASE" HEAD             -- path/to/file     # current side

git log --oneline "$MERGE_BASE..origin/$DEFAULT" -- path/to/file
git log --oneline "$MERGE_BASE..HEAD"            -- path/to/file
```

Present this as a structured summary before the rebase begins. Better to
over-explain than to miss a critical conflict pattern.

## Execution

Pre-flight:

```bash
git status --porcelain                                        # must be clean
git stash push -m "smart-rebase: pre-rebase stash"            # if dirty
git branch "backup/${CURRENT}-pre-rebase-$(date +%Y%m%d-%H%M%S)"  # safety net
```

Rebase and resolve:

```bash
git rebase "origin/$DEFAULT"

# For each conflicted file, after resolving:
git add path/to/resolved/file
git rebase --continue

# If it goes sideways — the backup branch is intact:
git rebase --abort
```

## Verification

```bash
# Files that exist on default but are missing from the rebased branch
git diff --name-only "origin/$DEFAULT" HEAD --diff-filter=D

# Diff against the pre-rebase backup. The backup branch is a git ref, not a
# filesystem path, so a shell glob won't expand it — resolve the name via
# `git branch --list` first.
BACKUP_BRANCH=$(git branch --list "backup/${CURRENT}-pre-rebase-*" | tr -d ' ' | tail -1)
git diff "$BACKUP_BRANCH" HEAD --stat

# Your feature commits should all be represented
git log --oneline "origin/$DEFAULT..HEAD"
```

Key safety check — walk each default-branch commit and confirm its changes
weren't lost during conflict resolution. Comparing `HEAD` against
`origin/$DEFAULT` directly is wrong: every file the feature branch
intentionally changed differs, so it flags the whole branch. Instead compare
the file at three points — the merge base, the default branch, and `HEAD` — and
only flag a file the default branch changed (`default != base`) whose default
change isn't reflected at `HEAD` (`head == base`), which means the change was
dropped:

```bash
for commit in $(git rev-list "$MERGE_BASE..origin/$DEFAULT"); do
  files=$(git diff-tree --no-commit-id --name-only -r "$commit")
  for file in $files; do
    base=$(git show "$MERGE_BASE:$file" 2>/dev/null || true)
    default=$(git show "origin/$DEFAULT:$file" 2>/dev/null || true)
    head=$(git show "HEAD:$file" 2>/dev/null || true)
    # Default changed this file, but HEAD still matches the merge base:
    # the default-branch change was lost. (If the feature branch also
    # changed the file, head != base and it's not flagged here — inspect
    # those in the both-modified bucket from Phase 2.)
    if [ "$default" != "$base" ] && [ "$head" = "$base" ]; then
      echo "REVIEW: default-branch change to $file may be lost (commit: $(git log --oneline -1 "$commit"))"
    fi
  done
done
```

Final step (only after user confirmation):

```bash
git push --force-with-lease origin "$CURRENT"
```
