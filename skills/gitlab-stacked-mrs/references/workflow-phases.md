# Workflow Phases: Commands and Templates

Detailed commands, templates, and tables for each phase of the
`gitlab-stacked-mrs` skill. See [SKILL.md](../SKILL.md) for the overview.

## Phase 1: Decompose

### Map the feature branch

```bash
DEFAULT=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||' || echo main)
git fetch origin "$DEFAULT" --quiet
BASE=$(git merge-base HEAD "origin/$DEFAULT")

git diff --stat "$BASE"..HEAD
git log --oneline "$BASE"..HEAD
```

Present the file list and commit log before suggesting splits — don't guess at
boundaries.

### Decomposition priority order

Apply in order; stop at the first axis that produces a clean boundary:

1. **Def-use independence** — hunks with no shared symbol references are
   candidate MRs (see [git-recipes.md](git-recipes.md) for splitting mechanics)
2. **Machine-generated code** — formatters, mass renames, generated files;
   cap is waived, flag as a codemod in the MR title
3. **Pure refactor before behaviour change** — "make the change easy, then
   make the easy change"; compile-time dependency
4. **Layer order** — schema → model → service → API → UI; types/traits/
   interfaces before implementations
5. **Module/package/crate boundary** — one MR per package, computable from
   the dependency graph
6. **One bugfix or one feature atom** — if the above don't split it, split
   by intent
7. **Test-only MRs** — only for validating *pre-existing* code; new tests
   stay with the new logic

**Hard constraint:** never create an MR that isn't an independently reviewable
change. Don't split to inflate MR count — escape rate tracks alongside MR
rate, and a false split won't help either metric.

### Sizing gate

```bash
git diff --stat "$BASE".."$SPLIT_TIP" -- \
  ':!*.lock' ':!vendor/' ':!generated/' ':!*.pb.go' ':!*_generated*' \
  | tail -1
```

| Threshold | Action |
|---|---|
| ≤200 LOC | Good |
| 201–300 LOC | Warn; consider splitting further |
| 301–400 LOC | Strongly recommend splitting |
| >400 LOC | Refuse unless it's a codemod — flag the exception explicitly |

### Create the stack

With `glab stack` (preferred when available):

```bash
glab stack create
glab stack save --message "feat(scope): description [part N of M]"
```

Pure-git fallback:

```bash
git checkout -b "stack/feature-01-foundation" "$BASE"
# ... stage hunks for this entry ...
git commit -m "feat(scope): description [part 1 of N]"

git checkout -b "stack/feature-02-model" stack/feature-01-foundation
# ... and so on
```

After creating all branches, verify parity:

```bash
git diff stack/feature-top..feature-branch  # must be empty
git range-diff origin/"$DEFAULT"..stack/feature-top origin/"$DEFAULT"..feature-branch
```

## Phase 2: Open MRs

With `glab stack sync` (check `glab stack sync --help` first — the
experimental CLI changes):

```bash
glab stack sync  # chains MRs bottom-to-top automatically
```

With the GitLab MCP or `glab mr create` as a fallback: each MR targets the
branch below it (not the default branch); the bottom MR targets the default
branch. Title as `feat(scope): description [part N of M]`.

Standard description block — paste into every MR:

```markdown
## Stack context

This is part N of M in the `<feature-name>` stack.

| # | Title | MR |
|---|---|---|
| 1 | Foundation | !NNN |
| 2 | This MR | — |
| 3 | Consumer | !NNN |

**Parity:** `git diff stack/feature-02-model..feature-branch` is empty as of
this MR's head SHA.

## Suppression ledger entries introduced here

| Suppression | File | Line | Cleared by |
|---|---|---|---|
| `#[allow(dead_code)]` | `src/model.rs` | 42 | part 3 |
```

Add dependency gates (Premium tier only, ≤10 per MR):

```bash
# MR N+1 must not merge before MR N
glab api "projects/:fullpath/merge_requests/$CHILD_IID/blocks" \
  --method POST \
  --field blocking_merge_request_id="$PARENT_IID"
```

Never create a cycle — check existing blocks before adding any edge:

```bash
glab api "projects/:fullpath/merge_requests/$IID/blocks"
```

## Phase 3: Handle Feedback

Enumerate open discussions (GitLab MCP: fetch the MR with discussions/notes
included) and classify each item:

| Category | Action |
|---|---|
| Blocking correctness | Fix in owning entry; `--fixup` + `git absorb` if earlier in stack |
| Style / nit | Fix in place; batch |
| Scope creep | New stacked MR; link it |
| "Too big" | Split further; check the 20-MR cap |
| Test coverage | Same entry for new logic; separate entry only for validating pre-existing code |
| Docs | Same entry, or a docs-only entry at the end of the stack |
| Design disagreement | Use `AskUserQuestion` to surface it — never auto-resolve |
| Duo false positive | Reply with rationale via the MCP review-reply tool, then resolve |

After fixing: re-run the parity check, re-verify the suppression ledger, push.

## Phase 4: Re-sync After Merges

GitLab auto-retargets only the 4 MRs immediately below the merged one and
doesn't rebase. Don't trust it beyond that depth.

```bash
DEFAULT=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||' || echo main)
git fetch origin --prune

# Re-sync every remaining branch from the bottom up.
# glab stack list output format is unverified — check it before relying on the grep.
for branch in $(glab stack list 2>/dev/null | grep -v merged || git branch -l 'stack/*' | sort); do
  # Check the exit status before pushing — the --update-refs fallback also
  # fires on a real conflict, which leaves the repo mid-rebase. Pushing that
  # state with --force-with-lease would corrupt the branch and let the loop
  # carry the corruption into every branch stacked on top of it.
  if git rebase --update-refs origin/"$DEFAULT" "$branch" 2>/dev/null || \
     git rebase origin/"$DEFAULT" "$branch"; then
    git push origin "$branch" --force-with-lease
  else
    echo "Rebase failed for $branch — resolve conflicts manually, then re-run" >&2
    git rebase --abort 2>/dev/null
    break
  fi
done

glab stack sync 2>/dev/null || true
```

After every re-sync:

1. Verify parity: `git diff <stack-tip>..<feature-branch>` is empty
2. Update "part N of M" counts in every remaining MR description
3. Verify the suppression ledger — any cleared suppressions must be removed
4. Check that CI is green on every updated branch before continuing
5. If the loop stopped early on a conflict, finish resolving that branch by
   hand before re-running the re-sync for the rest of the stack

**Squash hazard:** if a merged MR was squashed, child branches diverge at the
squash SHA. Always rebase children after a squash merge, never just retarget.

## Phase 5: Merge

Merge bottom-up, one at a time, re-syncing after each:

```bash
glab mr merge $IID --auto-merge --remove-source-branch
```

Or via the GitLab MCP's merge tool with `strategy: merge_when_checks_pass` to
arm auto-merge. After the last MR merges: delete the feature branch, archive
`STACK.md`.
</content>
