---
name: gitlab-todos
description: Interactively triage GitLab to-do items using glab todo commands. Summarizes recent TODOs, identifies stale items on closed/merged MRs, prompts before marking items done, and prioritizes by milestone. Use when the user wants to review, triage, clean up, or prioritize their GitLab to-do list.
version: 1.0.0
license: MIT
compatibility: opencode
metadata:
  audience: developers
  author: erran
  keywords: todos, triage, glab, prioritize, milestones
  workflow: productivity
---

# GitLab TODOs Triage Skill

Interactively triage the user's GitLab to-do list using `glab todo list` and `glab todo done`.

## Prerequisites

The `glab todo` subcommand requires glab with TODO support (see [MR !3074](https://gitlab.com/gitlab-org/cli/-/merge_requests/3074)).
Verify availability before starting:

```bash
glab todo list --per-page 1
```

If the command fails, inform the user that `glab todo` is not available in their glab version and suggest upgrading.

## Workflow

### 1. Fetch recent TODOs

```bash
glab todo list --per-page 10 --output json | jq -f scripts/parse-todos.jq
```

The bundled jq filter `scripts/parse-todos.jq` extracts these fields from each TODO:

| Field | Description |
|---|---|
| `id` | TODO ID (used with `glab todo done <id>`) |
| `action_name` | `assigned`, `mentioned`, `approval_required`, `directly_addressed`, `marked`, `build_failed` |
| `target_type` | `MergeRequest`, `Issue` |
| `title` | Title of the MR or issue |
| `iid` | IID of the target |
| `target_state` | `opened`, `closed`, `merged` |
| `project` | Project path with namespace |
| `state` | `pending` or `done` |
| `created_at` | Timestamp |

To get the raw JSON (without the jq filter):
```bash
glab todo list --per-page 10 --output json
```

### 2. Present a summary

Show a concise table of the 10 most recent TODOs including:
- TODO ID, action, target type, title, project, and age
- Highlight any TODOs whose target is in a terminal state (`closed` or `merged`)

Then show a separate section listing which TODOs belong to closed/merged MRs or closed issues, e.g.:

```
TODOs on closed/merged items:
  - #42 "Fix the bug" (MergeRequest, merged) in group/project
  - #99 "Old feature" (Issue, closed) in group/project
```

### 3. Identify stale TODOs and prompt before marking done

For TODOs where `target.state` is `merged` or `closed`, suggest marking them as done.
**Always ask the user for confirmation before running `glab todo done`.**

Example prompt:
> Found 3 TODOs on merged/closed items. Mark them as done?
> - TODO 42: "Fix the bug" (MergeRequest, merged)
> - TODO 99: "Old feature" (Issue, closed)
> - TODO 107: "Stale request" (MergeRequest, closed)
>
> Mark all 3 as done, select specific ones, or skip?

Based on the user's response:

```bash
# Mark a single TODO as done
glab todo done <id>

# Mark all pending TODOs as done (only if user explicitly requests)
glab todo done --all
```

### 4. Prioritize by milestone

For remaining open TODOs, fetch milestone information to help the user prioritize.

Use the bundled `scripts/fetch-milestone.sh` script to look up milestone and label data:

```bash
scripts/fetch-milestone.sh <project_path> <target_type> <iid>
```

For example:
```bash
scripts/fetch-milestone.sh gitlab-org/gitlab MergeRequest 232618
scripts/fetch-milestone.sh gitlab-org/gitlab Issue 593780
```

The script handles URL-encoding of the project path and returns:
```json
{
  "milestone": "19.0",
  "milestone_due": "2026-05-15",
  "labels": ["Category:Duo Chat", "backend", ...]
}
```

Deduplicate by project+target_type+iid (the same MR/issue may have multiple TODOs).
Run multiple invocations in parallel (one per TODO) using concurrent tool calls to batch the API calls.

Present prioritization advice:
1. **Overdue milestones** — items whose milestone `due_date` is in the past need immediate attention
2. **Current milestone** — items in the nearest upcoming milestone should be next
3. **Future milestones** — items in later milestones can wait
4. **No milestone** — lowest scheduling priority (but may still be important based on action type)

Within each milestone tier, suggest ordering by:
- `approval_required` and `directly_addressed` actions first (someone is waiting on the user)
- `assigned` actions next
- `mentioned` and `marked` actions last

### 5. Paginate if needed

If the user wants to see more TODOs:

```bash
glab todo list --page 2 --per-page 10 --output json
```

Use `--state pending` (default) for active triage. Use `--state done` or `--state all` only when the user asks.

## Bundled Scripts

Scripts are in `scripts/`.

| Script | Purpose |
|---|---|
| `scripts/parse-todos.jq` | jq filter that extracts summary fields (id, action, title, state, project, etc.) from `glab todo list --output json` |
| `scripts/fetch-milestone.sh` | Fetches milestone title, due date, and labels for a MergeRequest or Issue via `glab api`. Accepts `<project_path> <target_type> <iid>` arguments and handles URL-encoding. |

## Command Reference

```bash
# List pending TODOs (default)
glab todo list
glab todo list --per-page 10 --output json

# Filter by state
glab todo list --state pending
glab todo list --state done
glab todo list --state all

# Filter by action
glab todo list --action assigned
glab todo list --action approval_required
glab todo list --action mentioned
glab todo list --action build_failed
glab todo list --action marked
glab todo list --action directly_addressed

# Filter by target type
glab todo list --type MergeRequest
glab todo list --type Issue

# Paginate
glab todo list --page 2 --per-page 30

# Mark single TODO as done
glab todo done <id>

# Mark all pending TODOs as done
glab todo done --all
```

## Agent Guidelines

1. **Always fetch with `--output json`** — structured data is required for triage logic; never parse table output
2. **Never mark TODOs as done without asking** — always present the list and get explicit user confirmation
3. **URL-encode project paths** — use `%2F` for `/` in API calls: `projects/group%2Fproject/merge_requests/123`
4. **Batch API calls** — when fetching milestone info for multiple TODOs, run API calls in parallel where possible
5. **Respect pagination** — `glab todo list` defaults to 30 per page; use `--per-page` and `--page` to control
6. **No `--jq` flag** — glab has no `--jq`; pipe through `| jq '...'`
7. **Summarize before acting** — always show the user a summary of what you found before suggesting actions
8. **Handle missing milestones gracefully** — not all items have milestones; group them as "No milestone" in priority output
9. **Check target state from JSON** — the `target.state` field in TODO JSON tells you if an MR/issue is open, merged, or closed
10. **Prefer `glab todo done <id>` over `--all`** — only suggest `--all` when the user explicitly wants to clear everything
11. **Run fetch-milestone.sh calls in parallel** — use concurrent bash tool calls (one per unique project+type+iid) rather than sequential execution
12. **Use the skill base directory for script paths** — run scripts via the skill's base directory path (shown in the skill loader output), not via `cd` into the working directory
