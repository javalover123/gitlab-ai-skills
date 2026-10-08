# Phase 3: Work item and yml

## Justification work item

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

## Branch and files

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
