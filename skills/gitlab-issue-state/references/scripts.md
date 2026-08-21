# Script Reference

All scripts live in `skills/gitlab-issue-state/scripts/` and accept an issue reference as either a
full URL or an IID plus `-R owner/repo`. `lib.sh` is a shared helper library (not executable on its
own) sourced by the other four scripts.

## `start-issue.sh` — start implementing

Assigns the issue to the current user, sets the active milestone (the project/ancestor milestone
whose date range contains today), and sets the status to *In dev*.

```bash
skills/gitlab-issue-state/scripts/start-issue.sh <issue-url>
skills/gitlab-issue-state/scripts/start-issue.sh 123 -R gitlab-org/gitlab
skills/gitlab-issue-state/scripts/start-issue.sh <issue-url> --status "In progress"  # override start status
skills/gitlab-issue-state/scripts/start-issue.sh <issue-url> --no-milestone          # skip milestone
```

Milestone selection considers active milestones (including ancestor/group milestones) and picks
the one whose `start_date..due_date` window contains today. If none matches, milestone assignment
is skipped with a warning; the status change still proceeds.

## `sync-issue-state.sh` — track progress

Inspects the issue's related and closing MRs and applies the progression rules from the main
`SKILL.md`. Skips closed issues and issues with no related MRs.

```bash
skills/gitlab-issue-state/scripts/sync-issue-state.sh <issue-url>
skills/gitlab-issue-state/scripts/sync-issue-state.sh <issue-url> --dry-run   # show decision only
skills/gitlab-issue-state/scripts/sync-issue-state.sh <issue-url> --force     # allow overwriting a terminal status
```

Decision logic:

- Issue already closed → leave as-is (Status is usually auto-set to a done category on close).
- Current status in a terminal category (`done`, `canceled`) → leave as-is unless `--force`.
- Any related MR still an open draft/WIP → `In dev`.
- Otherwise, at least one MR still open (in review) → `In review`.
- All related MRs merged/closed (none open) → `In review` (merge/close handles `Complete`).
- No related MRs at all → leave as-is.

### What does *not* trigger a status change

- **Pushing more commits** to an MR that is already in review. Only the MR's `draft`/
  `work_in_progress` flag distinguishes *In dev* from *In review*, so re-running the script after a
  round of review fixes correctly leaves the issue at *In review*. Convert the MR back to a Draft if
  you want it to read *In dev* again.
- **Review comments or approvals** — not inspected at all.
- **A status that already matches** the target: `set-issue-status.sh` skips the `workItemUpdate`
  entirely, so repeated runs don't pile up "changed status" system notes on the issue.

### Terminal statuses and closing

An issue can be **open yet already `Complete`** — GitLab's close automation only fires when the MR
description carries a closing pattern (`Closes #123`), so merging without one sets the status but
leaves the issue open. Re-deriving status from MR state would drag it back to *In review*, so any
status in a `done` or `canceled` category is left untouched unless `--force` is given.

When every related MR is merged but the issue is still open, the script prints a note and defers:

```
note: all 2 MR(s) merged but the issue is still open - no closing pattern took effect.
      ask the user whether to close it (and set a done status); this script will not decide.
```

It deliberately does **not** close the issue. Follow-up work often remains after the MRs land, so
that call belongs to the user — ask, don't assume. Note the check requires *all* MRs to be `merged`:
a mix of merged and closed-unmerged stays silent, since a closed MR may signal abandoned work.

## `set-issue-status.sh` — set a status by name

Low-level setter used by the other scripts. Resolves the status name against the project's
lifecycle and applies it via the `workItemUpdate` GraphQL mutation.

```bash
skills/gitlab-issue-state/scripts/set-issue-status.sh <issue-url> "In review"
```

## `resolve-statuses.sh` — inspect the lifecycle

Lists the statuses available to an issue (name, id, category), or resolves a single name to its
global ID with `--name`.

```bash
skills/gitlab-issue-state/scripts/resolve-statuses.sh <issue-url>
skills/gitlab-issue-state/scripts/resolve-statuses.sh <issue-url> --name "In dev"
```

Without `--name`: prints a JSON array of `{id, name, category}` for every allowed status.
With `--name`: prints the single global ID whose name matches (case-insensitive), or exits 1 if
no status in the lifecycle matches.

## `glab` invocation

Scripts call `glab` directly, expecting it authenticated on `PATH`. If your `glab` is wrapped (for
example behind a 1Password shell plugin, so the interactive alias isn't visible to scripts), set
`GLAB_CMD` before invoking any script in this skill:

```bash
export GLAB_CMD="op plugin run -- glab"
```
