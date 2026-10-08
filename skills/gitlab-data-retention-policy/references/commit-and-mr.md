# Phase 4: Commit, push, and MR

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
