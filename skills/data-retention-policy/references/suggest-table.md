# Phase 1: Suggest a table

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
