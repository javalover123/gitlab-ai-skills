# Phase 2: Decision tree

## Collect the facts first

- Dictionary entry: `db/docs/<table>.yml` (description, classes, feature categories, gitlab_schema).
- Partitioned now or not: `grep -A3 "CREATE TABLE <table> (" db/structure.sql | grep "PARTITION BY"`. Note the partition key if there is one.
- Size and class: from the tracking issue row.
- Lifecycle: find the model classes from the dictionary. Search `app/`, `ee/app/`, `lib/`, and `ee/lib/` for code that deletes rows. Look for workers, `delete_all`, `destroy`, `dependent:` on associations, and event store subscriptions. Check `db/structure.sql` for foreign keys with `ON DELETE CASCADE`.
- Existing analysis: search the comments on the tracking issue and its linked work items for notes about this table.

## Team context

- Read the comments on the tracking issue for team decisions, for example from the product manager about which data must stay. Show the decisions that apply to this table, with a link to the comment.
- For every lifecycle-based answer, ask: "What happens if the parent record stays forever?" For example, an MR that stays open forever. If some rows never leave, the lifecycle alone is not enough.
- A non-excluded policy removes data from the database. The team can still keep a copy in long-term storage.

## Questions, in the order of the decision tree

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

## Then the other fields

- `retention_window`: `-1` only when `exclude` is set. In all other cases ask for a positive number of days. For `transient_data`, ask for the longest time a row can stay (for example 30 days for stale rows). When the window depends on planned work, such as a table drop, suggest a window that leaves room for that work to slip.
- `enforcing`: default `false`. Use `true` only when the enforcement runs in production now.
- `pause_mechanism`: `type` is `none`, `application_setting`, or `feature_flag`. Ask for `name` when `type` is not `none`. Use the nested form below, not the `pause_mechanism::name` form in the doc example.

Gate: show all answers and the resulting values. The user confirms.
