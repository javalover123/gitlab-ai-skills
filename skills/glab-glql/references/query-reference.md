# GLQL Query Fields and Operators

## Operators

| Operator | Description |
|----------|-------------|
| `=`      | Equals / all values in list must match |
| `!=`     | Not equal / none of values in list |
| `in`     | Any value in list (OR) |
| `>`      | Greater than |
| `<`      | Less than |
| `>=`     | Greater than or equal to |
| `<=`     | Less than or equal to |

Only `and` is supported as a logical operator. Use `in (...)` for OR across values.

## State

```
state = opened
state = closed
state = merged        # MergeRequest only
state = all           # include all states (default)
```

## Type

```
type = Issue
type = MergeRequest
type = Epic           # requires group = scope
type = Task
type = Incident
type = Objective
type = KeyResult
type in (Issue, Task) # OR across types
```

## Users

```
assignee = currentUser()
assignee = @username
assignee = (@user1, @user2)       # both assigned (AND)
assignee in (@user1, @user2)      # either assigned (OR)
assignee = none                   # unassigned
assignee = any                    # has any assignee

author = @username
author != currentUser()

reviewer = @username              # MR only
reviewer = currentUser()          # MR only

approver = currentUser()          # MR only
approver = none                   # not yet approved
```

## Labels

```
label = ~bug
label = ~"workflow::in progress"        # scoped labels need quotes
label = (~bug, ~"team::planning")       # both labels (AND)
label in (~bug, ~feature)               # either label (OR)
label != ~"workflow::in progress"       # does not have label
label != ~"workflow::*"                 # no workflow:: scoped label (wildcard negation)
label = none                            # no labels
label = any                             # has any label
```

## Milestone

```
milestone = %"17.10"
milestone = %Backlog
milestone in (%17.9, %17.10)
milestone != (%17.9, %17.10)
milestone = none
milestone = any
milestone = upcoming              # next upcoming milestone
milestone = started               # currently active milestone
```

## Dates (issues, MRs, epics)

All date fields accept absolute (`YYYY-MM-DD`) or relative (`-30d`, `2w`, `-6m`, `1y`) values.
`>=` and `<=` are inclusive; `>` and `<` are exclusive.

```
created > -30d                    # created in last 30 days
created >= 2026-01-01             # created on or after Jan 1
created = today()                 # created today

updated < -1w                     # not updated in over a week
updated > -1m                     # updated in last month

closed > 2026-01-01 AND closed < 2026-02-01

due < 1w                          # due within a week
due = today()
due > -1m AND due < today()       # overdue in last month

merged > -30d                     # MR merged in last 30 days (MergeRequest only)
merged > 2026-01-01 AND merged < 2026-02-01
```

## Draft (MRs only)

```
type = MergeRequest AND draft = true
type = MergeRequest AND draft = false
```

## Other filters

```
confidential = true
confidential = false

weight = 5
weight != 5
weight = none
weight = any

health = "on track"
health = "needs attention"
health = "at risk"
health = none

iteration = current
iteration = 123456
iteration in (123, 456)

includeSubgroups = true           # group scope only; default is true
includeSubgroups = false          # only direct child projects

subscribed = true                 # current user subscribed

sourceBranch = "main"             # MR only
targetBranch = "main"             # MR only
targetBranch in ("main", "develop")
```

## Sort fields

```
sort: created desc
sort: updated asc
sort: due asc
sort: merged desc
sort: title asc
sort: popularity desc             # by thumbs-up reactions
sort: weight desc
sort: milestone asc               # by milestone due date
```
