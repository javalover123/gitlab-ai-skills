---
name: data-retention-policy
description: Guide a GitLab engineer through declaring a data retention policy (db/docs/data_retention/<table>.yml) for one table from their team's retention tracking issue. Takes the tracking issue URL as the first argument and an optional table name. Four gated phases - suggest the next table (status from the repo and open ~data-retention MRs), walk the retention decision tree one question at a time, create the justification work item and the yml, then commit, push, open a non-draft MR, and add the MR link to the tracking issue. Use for "data retention policy", "retention yml", "next retention table", "retention tracking issue", or `/data-retention-policy <tracking-issue-url> [table]`.
argument-hint: <tracking-issue-url> [table]
---

# Data retention policy for one table

Handle one table per run.

## Arguments

- First argument: the URL of the team's retention tracking issue, for example `https://gitlab.com/gitlab-org/gitlab/-/work_items/629743`. Get the project path and the IID from the URL. The URL can contain `/-/issues/` or `/-/work_items/`. If the argument is missing, ask for it. Do not guess.
- Second argument (optional): a table name. If it is there, skip the suggestion in Phase 1. Still show its status.

Below, `<project>` is the project path and `<tracking_iid>` is the IID of the tracking issue.

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

- End each phase with an `AskUserQuestion` gate. Do not start the next phase without a yes.
- Show evidence with each question (file paths, code, sizes) and give a suggested answer. The user decides.
- Ask one question at a time.
- Check whether each related issue is confidential. The commit and MR are public. In them, and in the work item, you can link to a confidential issue, but do not repeat its title or its content.
- Before you post any text that relates to a confidential issue, show the text and name the issue. Get an explicit approval for that text in its own `AskUserQuestion`. A general approval of a draft is not enough.

## Phase 1: Suggest a table

1. Get the table list from the tracking issue:
   `glab issue view <tracking_iid> -R <project>`
   Find the markdown table that lists the tables, usually with a size and a class column, for example `| [<table>](...) | <size> | <class> | ... |`. Keep the issue order. If you cannot read the list, show what you found and ask the user.
2. Find the done tables on master, not in the local checkout:
   `git fetch origin master && git ls-tree --name-only origin/master db/docs/data_retention/`
3. Find the in-progress tables in open MRs by anyone:
   ```shell
   for i in $(glab mr list -R gitlab-org/gitlab --label data-retention -P 100 -F json | jq -r '.[].iid'); do
     glab mr diff "$i" -R gitlab-org/gitlab --raw | grep '^+++ b/db/docs/data_retention/' | sed "s|.*/data_retention/\(.*\)\.yml|!$i \1|"
   done
   ```
4. Show a short status: counts of done, in progress (with MR links), and to do.
5. Suggest the next to-do table. If the tracking issue gives an order or a size threshold (for example "tables over 50 GB first"), follow it. If not, suggest the largest. Offer the next three to-do tables as other options. The user can also type any table name.

Gate: the user picks the table.

## Phase 2: Decision tree

### Collect the facts first

- Dictionary entry: `db/docs/<table>.yml` (description, classes, feature categories, gitlab_schema).
- Partitioned now or not: `grep -A3 "CREATE TABLE <table> (" db/structure.sql | grep "PARTITION BY"`. Note the partition key if there is one.
- Size and class: from the tracking issue row.
- Lifecycle: find the model classes from the dictionary. Search `app/`, `ee/app/`, `lib/`, and `ee/lib/` for code that deletes rows. Look for workers, `delete_all`, `destroy`, `dependent:` on associations, and event store subscriptions. Check `db/structure.sql` for foreign keys with `ON DELETE CASCADE`.
- Existing analysis: search the comments on the tracking issue and its linked work items for notes about this table.

### Team context

- Read the comments on the tracking issue for team decisions, for example from the product manager about which data must stay. Show the decisions that apply to this table, with a link to the comment.
- For every lifecycle-based answer, ask: "What happens if the parent record stays forever?" For example, an MR that stays open forever. If some rows never leave, the lifecycle alone is not enough.
- A non-excluded policy removes data from the database. The team can still keep a copy in long-term storage.

### Questions, in the order of the decision tree

1. Is the data naturally deleted by the feature lifecycle?
   - Yes: the result is `transient_data`. Check that every path removes the rows (for example: completed, closed, open forever, parent deleted). If one path keeps rows forever, say so and continue to question 2.
   - For a leftover table from a partitioning swap (for example `<name>_archived`), the planned table drop is the lifecycle, so the result is `transient_data`. In the question, say clearly that the question is about the old table that will be dropped, and name the live table. The user can mix up the two tables.
2. Can the data be deleted without archival?
   - No: the result is `exclude.reason: needs_archival`.
   - If the table is a core entity that does not build up rows over time, offer `exclude.reason: indefinite_retention` instead. Show the doc's definition of each reason so the user can choose.
3. Is the table larger than 50 GB? Do not ask. State the answer from the size in the tracking issue.
4. Is partitioning possible? Show the current partition state. Date range and sliding list partitioning both support retention.
   - Over 50 GB: yes gives `drop_partition`. No gives `exclude.reason: technical_complexity`. The work item must name the technical reason. Team capacity is not a valid reason.
   - 50 GB or less: yes gives `drop_partition`. No gives `delete_rows`. The doc calls `delete_rows` a last resort, so ask for the reason.

### Then the other fields

- `retention_window`: `-1` only when `exclude` is set. In all other cases ask for a positive number of days. For `transient_data`, ask for the longest time a row can stay (for example 30 days for stale rows). When the window depends on planned work, such as a table drop, suggest a window that leaves room for that work to slip.
- `enforcing`: default `false`. Use `true` only when the enforcement runs in production now.
- `pause_mechanism`: `type` is `none`, `application_setting`, or `feature_flag`. Ask for `name` when `type` is not `none`. Use the nested form below, not the `pause_mechanism::name` form in the doc example.

Gate: show all answers and the resulting values. The user confirms.

## Phase 3: Work item and yml

### Justification work item

1. Draft the work item:
   - Title: Data retention policy for `<table>`, with the table name in backticks.
   - Put every table name in backticks, in the work item and in the MR.
   - Body: what the table is, what happens to its data, and the enforcement plan. If there is no enforcement, say why. Link to the tracking issue and the related issues.
   - Write it like a person explaining the table to a colleague. Use short paragraphs under a few headings.
   - Do not quote the yml values (`transient_data`, `enforcing: false`, `pause_mechanism: none`, and so on). The MR shows the yml. Say the same thing in plain words, for example "We'll drop the whole table".
   - Do not structure the body as a walk through the decision tree questions.
   - If the user has a skill for their writing voice, use it for the prose.
2. Gate: show the draft. The user confirms or edits it.
3. Create it. Do not assign anyone, and do not set a milestone.
   ```shell
   glab issue create -R <project> \
     --title 'Data retention policy for `<table>`' \
     --description-file <scratchpad>/work_item.md \
     --label "data-retention,database,backend,type::ignore,<team labels>" \
     --linked-issues <tracking_iid> --link-type relates_to \
     --epic <epic_id> --confidential --yes
   ```
   Keep the URL it returns. Add `--epic` only when there is a parent epic. It takes the epic ID, not the IID. Add `--confidential` only when the parent epic is confidential, or when the user asks for it.

### Branch and files

1. Create the branch from an updated master:
   ```shell
   git checkout master && git pull origin master
   git checkout -b <prefix>$(date +%Y-%m-%d)-data-retention-<table>
   ```
   For `<prefix>`, look at the user's local branches (`git branch --format='%(refname:short)'`). If most of them start with the same `<x>/`, use it. If not, use no prefix. If the working tree is not clean, stop and ask the user.
2. Write `db/docs/data_retention/<table>.yml`. Use this key order. Add no comments. End the file with a newline.
   ```yaml
   ---
   exclude:            # only when excluded
     reason: needs_archival
   retention_window: -1
   enforcement_strategy: none
   enforcing: false
   pause_mechanism:
     type: none
   work_item: https://gitlab.com/gitlab-org/gitlab/-/work_items/<iid>
   ```
   Without `exclude`, give `retention_window` a positive number and `enforcement_strategy` a real strategy. Add `name:` under `pause_mechanism` when `type` is not `none`.
3. Remove the line `- <table>` from `spec/support/database/retention-policy-missing-allowlist.yml`. The spec fails on stale entries if you keep it.
4. Validate with the repo's own class. This needs no Rails and no bundle:
   ```shell
   ruby -ryaml -e 'class Object; def blank? = respond_to?(:empty?) ? empty? : !self; def present? = !blank?; end
     require "./lib/gitlab/database/retention_policy"
     ARGV.each { |f| e = Gitlab::Database::RetentionPolicy.from_file(f).validation_errors
       puts(e.empty? ? "OK #{f}" : "INVALID #{f}: #{e.join("; ")}") }' db/docs/data_retention/<table>.yml
   ```
   Fix every error before you continue. Also check that the table no longer appears in the allowlist: `grep -x -- "- <table>" spec/support/database/retention-policy-missing-allowlist.yml` must print nothing.

Gate: show the yml, `git diff` of the allowlist, and the work item URL. The user confirms.

## Phase 4: Commit, push, and MR

1. Commit:
   ```shell
   git add db/docs/data_retention/<table>.yml spec/support/database/retention-policy-missing-allowlist.yml
   git commit -m "Add data retention policy for <table>" -m "<one line: the result and why>" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
   ```
   Use the model name from the session's attribution reminder in the trailer, if there is one. Keep each body line at 72 characters or fewer, or the commit lint hook fails.
2. Push: `git push -u origin HEAD`. If a pre-push hook fails with `Bundler::GemNotFound`, run `bundle install` and push again. Do not skip the hooks.
3. Write the MR description from `.gitlab/merge_request_templates/Default.md`. Keep every section. Remove the HTML comments.
   - What does this MR do and why: one sentence plus the decision (strategy or exclude reason).
   - References: the new work item and the tracking issue.
   - How to set up and validate locally: "Check the file against the schema in https://docs.gitlab.com/development/database/database_growth_control/data_retention_policy/#schema."
   - End with `/assign me` and `/milestone %<milestone>`. Get the milestone from `VERSION` (for example `19.5.0-pre` gives `19.5`).
4. Create the MR. It is not a draft. The `[skip ci]` prefix stops the pipeline until the user is ready.
   ```shell
   glab mr create -R gitlab-org/gitlab \
     --source-branch "$(git branch --show-current)" --target-branch master \
     --title '[skip ci] Add data retention policy for `<table>`' \
     --description "$(cat <scratchpad>/mr.md)" \
     --label "data-retention,database,type::maintenance,pipeline::tier-1,<team labels without category>" \
     --milestone "<milestone>" --yes
   ```
5. Add the MR to the tracking issue. In the issue's markdown table, find the row for `<table>`, and replace the text of the `Policy` cell with the plain MR URL, for example `| https://gitlab.com/gitlab-org/gitlab/-/merge_requests/257835 |`. Remove the old text, such as `**missing** · [declare](...)`.
   - Get the description again just before you edit it, because other people edit it too:
     `glab api "projects/<encoded project>/issues/<tracking_iid>" | jq -r .description > <scratchpad>/tracking.md`
   - Change only that one cell. Find the row by the exact table name in the first column. Do not touch the other rows. If you do not find exactly one row, or the table has no `Policy` column, stop and ask the user.
   - Gate: show the old row and the new row. The user confirms.
   - Update the issue: `glab issue update <tracking_iid> -R <project> --description "$(cat <scratchpad>/tracking_new.md)"`.
   - Read the description back and check that the row has the URL and that nothing else changed.
6. Give the user the MR URL and the work item URL. Tell them to remove `[skip ci]` from the title and push a commit when they want CI to run. Editing the title alone does not start a pipeline.
