---
name: smart-rebase
description: "Orchestrates intelligent git rebases by identifying the merge base between the current branch, its upstream tracking branch, and the default branch, then carefully reconciling all changes to produce a cleanly mergeable result. Use when rebasing a diverged feature branch onto an updated main/master, when preparing a branch for merge after the default branch has advanced, or when manual rebase conflicts risk clobbering default branch changes. Triggers: rebase, merge base, diverged branch, catch up with main, rebase onto main, reconcile branches, update feature branch."
version: 1.0.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: git
---

# Smart Rebase

Safely rebase a diverged feature branch onto an updated default branch without
clobbering changes on either side.

**The cardinal rule:** never silently discard a change from the default branch.
Every default-branch change must either be preserved as-is or explicitly
reworked to fit the current branch's architecture. If you're uncertain about a
change, flag it for the user — don't guess.

## When to use

- Rebasing a feature branch onto main/master after the default branch advanced.
- Preparing a long-lived branch for merge when significant divergence exists.
- Resolving complex rebase conflicts where you need full context of each side.
- Any situation where a naive `git rebase main` risks losing default-branch work.

## Workflow

Four phases. The exact commands for each live in
[references/commands.md](references/commands.md) — run them and present the
results as you go.

### 1. Discovery — map the topology

Identify the current branch, its upstream (may not exist), and the default
branch (from `origin/HEAD`, falling back to `main`/`master`). Fetch the default
branch, find the merge base, and measure divergence on each side. See
[references/commands.md](references/commands.md#discovery).

Present the topology to the user and **use the `question` tool** (opencode) /
`AskUserQuestion` (Claude Code) to confirm the merge base is correct before
proceeding. Don't continue until it's confirmed.

### 2. Analysis — categorize every change

This is the step that prevents accidental clobbering. Diff both sides against
the merge base and sort every file into a bucket:

| Category | Meaning | Action |
|---|---|---|
| Default-only | Changed only on default | Accept automatically |
| Current-only | Changed only on current | Keep as-is |
| Both-modified | Changed on BOTH | Careful conflict resolution |
| Default-added | New on default | Accept unless current has same path |
| Current-added | New on current | Keep as-is |
| Default-deleted | Deleted on default | Accept unless current modified it |

For every **Both-modified** file, show the user what each side changed (file
and commit level) before touching it. Commands:
[references/commands.md](references/commands.md#analysis).

### 3. Execution — rebase with context

Pre-flight: confirm a clean working tree (stash if dirty) and create a
timestamped `backup/` branch. Then rebase onto `origin/<default>`.

**Strategy — current-branch-wins, default-intent-preserved.** You're not asking
"which version is right?" but "how do I preserve the default branch's *intent*
within the current branch's structure?" If the default branch fixed a bug,
apply that fix within the current branch's architecture; if it added a feature,
port it to the current branch's patterns; if it refactored, decide whether the
refactor still applies.

For each conflict: read the markers, recall the Phase 2 analysis, resolve with
the strategy above, then `git add` and `git rebase --continue`. If a conflict is
too ambiguous, stop and present both sides to the user. If it goes sideways,
`git rebase --abort` — the backup branch is intact. Commands and conflict
patterns: [references/commands.md](references/commands.md#execution) and
[references/conflict-patterns.md](references/conflict-patterns.md).

### 4. Verification — confirm nothing was lost

After the rebase, verify every default-branch change is represented: check for
files present on `origin/<default>` but missing from the result, diff against
the pre-rebase backup, and walk each default-branch commit confirming its
changes survived. Flag any file that differs and explain why. See
[references/commands.md](references/commands.md#verification).

Only force-push with `--force-with-lease`, and **always ask the user first.**

## Edge cases

- **No upstream tracking branch** — skip upstream analysis; work with current
  and default only.
- **Merge base is default HEAD** — already up to date; no rebase needed.
- **Merge base is current HEAD** — behind with no new commits; fast-forward with
  `git merge --ff-only origin/<default>`.
- **Uncommitted changes** — stash before, pop after; warn about stash conflicts.
- **Large divergence (100+ commits)** — warn it'll be long; consider rebasing
  onto an intermediate commit first.
- **Submodules / generated files** — flag during analysis; regenerate generated
  files after rebase rather than resolving by hand.

## What this skill does NOT do

- Multi-level stacked-branch rebases (use the `stack-changes` skill for that).
- Merge-based workflows — this is rebase-only.
- Automatic test running (suggest it during verification, don't mandate it).
- Rewriting history beyond what rebase naturally does.
