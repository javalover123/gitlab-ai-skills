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
```

Decision logic:

- Issue already closed → leave as-is (Status is usually auto-set to a done category on close).
- Any related MR still an open draft/WIP → `In dev`.
- Otherwise, at least one MR still open (in review) → `In review`.
- All related MRs merged/closed (none open) → `In review` (merge/close handles `Complete`).
- No related MRs at all → leave as-is.

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
