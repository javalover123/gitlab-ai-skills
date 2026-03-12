# Epics (Group-Level Work Items)

Epics are group-level. `glab issue` commands don't work — use `glab api` with the REST API.

## Finding IDs

```bash
# Group ID (use URL-encoded path or numeric ID)
glab api "groups/my-org%2Fmy-group" | jq '.id'

# Project ID
glab api "projects/my-org%2Fmy-project" | jq '.id'

# Epic internal ID (id) vs display ID (iid) — some endpoints need the internal id
glab api "groups/<group_id>/epics/<iid>" | jq '{id, iid, title}'
```

## List and view

```bash
# List epics
glab api "groups/<group_id>/epics" | jq '.[] | {iid, title, state}'

# View single epic
glab api "groups/<group_id>/epics/<iid>"

# List issues in an epic
glab api "groups/<group_id>/epics/<epic_iid>/issues" | jq '.[] | {iid, title, state}'
```

## Create

```bash
# Simple epic
glab api --method POST "groups/<group_id>/epics" \
  -f title="My Epic" \
  -f "description=$(cat /tmp/epic-description.md)"

# With parent epic (parent_id is the INTERNAL id, not iid)
PARENT_ID=$(glab api "groups/<group_id>/epics/<parent_iid>" | jq '.id')
glab api --method POST "groups/<group_id>/epics" \
  -f title="Child Epic" \
  -f "description=$(cat /tmp/description.md)" \
  -f parent_id=$PARENT_ID
```

## Add issues to an epic

**Preferred method** — update the issue's `epic_id` directly:

```bash
# Get the epic's internal id (not iid)
EPIC_ID=$(glab api "groups/<group_id>/epics/<epic_iid>" | jq '.id')

# Attach issue to epic
glab api --method PUT "projects/<project_id>/issues/<iid>" -f epic_id=$EPIC_ID
```

**Alternative** — the epic issues endpoint (may 404 depending on permissions/plan):

```bash
ISSUE_ID=$(glab api "projects/<project_id>/issues/<iid>" | jq '.id')
glab api --method POST "groups/<group_id>/epics/<epic_iid>/issues/$ISSUE_ID"
```

## Update

```bash
# Update description
glab api --method PUT "groups/<group_id>/epics/<iid>" \
  -f "description=$(cat /tmp/epic-description.md)"

# Update title
glab api --method PUT "groups/<group_id>/epics/<iid>" \
  -f title="New Title"
```

## Remove issue from epic

**Preferred method** — set `epic_id` to 0:

```bash
glab api --method PUT "projects/<project_id>/issues/<iid>" -f epic_id=0
```

**Alternative** — the epic issues endpoint (needs `epic_issue_id` from add/list response):

```bash
glab api --method DELETE "groups/<group_id>/epics/<epic_iid>/issues/<epic_issue_id>"
```

## Common gotchas

- **`parent_id` vs `parent_iid`**: Creating a child epic needs the parent's internal `id` field, not its `iid`
- **Global id only needed for the alternative endpoint**: The preferred `epic_id` approach uses the issue `iid`. Only the alternative `epics/<epic_iid>/issues/<issue_id>` endpoint requires the internal global `id` (`jq '.id'`)
- **`glab issue` doesn't work**: Epics are group-level work items — always use `glab api`
- **`note` field on PUT is ignored**: To add a comment when closing/updating an issue, use a separate `POST issues/<iid>/notes` call (see issue-links.md gotchas)
- **jq and control characters**: Issue descriptions with embedded newlines/tabs cause `jq` parse failures. Extract only specific fields (`jq '.iid'`, `jq '{iid, title}'`) rather than piping full responses. For encoding, use `jq '@json'` to safely stringify a field
