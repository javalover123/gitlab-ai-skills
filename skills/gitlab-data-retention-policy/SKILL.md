---
name: gitlab-data-retention-policy
description: "Guide a GitLab engineer through declaring a data retention policy (`db/docs/data_retention/<table>.yml`) for one table from their team's retention tracking issue: pick the table, walk the decision tree, create the justification work item and the yml, and open the MR. Use when asked for a data retention policy, a retention yml, or the next table of a retention tracking issue."
version: 1.0.0
category: Database
license: MIT
compatibility: opencode
argument-hint: <tracking-issue-url> [table]
metadata:
  audience: developers
  workflow: gitlab
---

# Data retention policy for one table

Handle one table per run.

## Arguments

- First argument: the URL of the team's retention tracking issue, for example `https://gitlab.com/gitlab-org/gitlab/-/work_items/629743`. Get the project path and the IID from the URL. The URL can contain `/-/issues/` or `/-/work_items/`. If the argument is missing, ask for it. Do not guess.
- Second argument (optional): a table name. If it is there, skip the suggestion in Phase 1. Still show its status.

Below, `<project>` is the project path and `<tracking_iid>` is the IID of the tracking issue. `<scratchpad>` is a temporary directory for draft files, outside the checkout.

## Before you start

1. Load the `glab` skill. Use `glab` for every GitLab read and write.
2. Find the GitLab checkout. Use the current directory if it contains `lib/gitlab/database/retention_policy.rb`. If not, ask the user for the path. Run every command below in that checkout.
3. Read these files in the checkout. The schema still changes, so do not rely on memory or on this skill for the field rules:
   - `doc/development/database/database_growth_control/data_retention_policy.md` (decision tree, field meanings)
   - `lib/gitlab/database/retention_policy.rb` (the rules the CI spec applies)
   - `.ai/git.md` and `.ai/merge-requests.md`
4. If the doc and the validator disagree, the validator wins. Tell the user about the difference.
5. Read the team settings from the tracking issue. The work item and the MR use them later.
   ```shell
   glab api "projects/$(printf %s '<project>' | jq -sRr @uri)/issues/<tracking_iid>" \
     | jq '{labels, confidential, epic: (.epic // null | if . then {id, iid, group_id} else null end)}'
   ```
   - Team labels: keep the `group::`, `devops::`, and `section::` labels, and any `category:` label. If a label is missing, ask the user for it.
   - Parent epic: keep the epic `id` (not the IID). If the issue has no epic, ask the user for a parent epic or continue without one.
   - Epic confidentiality: `glab api groups/<group_id>/epics/<epic_iid> | jq .confidential`. If the epic is confidential, the work item must be confidential, because GitLab refuses a non-confidential child.
6. Show the settings you found and ask the user to confirm them.

## Rules for every phase

- End each phase with a gate: ask the user with your question tool (for example `AskUserQuestion` in Claude Code). Do not start the next phase without a yes.
- Show evidence with each question (file paths, code, sizes) and give a suggested answer. The user decides.
- Ask one question at a time.
- Check whether each related issue is confidential. The commit and MR are public. In them, and in the work item, you can link to a confidential issue, but do not repeat its title or its content.
- Before you post any text that relates to a confidential issue, show the text and name the issue. Get an explicit approval for that text in its own question. A general approval of a draft is not enough.

## Phases

Do the phases in order. Read the reference file for a phase when you start it.

1. [Suggest a table](references/suggest-table.md): read the table list from the tracking issue, find which tables are done or in progress, and suggest the next one.
2. [Decision tree](references/decision-tree.md): collect the facts about the table, then walk the decision tree one question at a time and set the other fields.
3. [Work item and yml](references/work-item-and-yml.md): create the justification work item, the branch, and the yml, remove the table from the allowlist, and validate.
4. [Commit, push, and MR](references/commit-and-mr.md): commit, push, open a non-draft MR, and add the MR link to the tracking issue.
