# GLQL Output Fields, jq Patterns, and Pagination

## Fields for output

Common fields to include in `fields:`:

| Field | Notes |
|-------|-------|
| `id` | Global ID (GID), e.g. `gid://gitlab/Issue/123` |
| `title` | Title |
| `state` | `OPEN`, `CLOSED`, or `MERGED` in response |
| `author` | Nested: `.author.username` |
| `assignees` | Nested list: `.assignees.nodes[].username` |
| `reviewers` | Nested list: `.reviewers.nodes[].username` (MR only) |
| `labels` | Nested list: `.labels.nodes[].title` |
| `milestone` | Nested: `.milestone.title` |
| `created`, `createdAt` | ISO timestamp |
| `updated`, `updatedAt` | ISO timestamp |
| `merged`, `mergedAt` | ISO timestamp (MR only) |
| `closed`, `closedAt` | ISO timestamp |
| `due`, `dueDate` | Date string |
| `draft` | Boolean (MR only) |
| `description` | Full description text |
| `webUrl` | Always returned in response |

## jq patterns

The fields `reference`, `iid`, and `webUrl` are always present in every node regardless of what
you specify in `fields:` -- you don't need to request them explicitly.

```bash
# Reference + title (flat fields)
| jq -r '.data.nodes[] | "\(.reference)  \(.title)"'

# With state
| jq -r '.data.nodes[] | "\(.reference)\t[\(.state)]\t\(.title)"'

# With author (nested object)
| jq -r '.data.nodes[] | "\(.reference)  @\(.author.username)  \(.title)"'

# With assignees (nested node list)
| jq -r '.data.nodes[] | "\(.reference)  \(.title)  → \(.assignees.nodes | map(.username) | join(", "))"'

# With reviewers (nested node list)
| jq -r '.data.nodes[] | "\(.reference)  \(.title)  → reviewers: \(.reviewers.nodes | map(.username) | join(", "))"'

# With labels (nested node list)
| jq -r '.data.nodes[] | "\(.reference)  \(.title)  [\(.labels.nodes | map(.title) | join(", "))]"'

# With timestamp field (e.g. mergedAt, createdAt, updatedAt)
| jq -r '.data.nodes[] | "\(.reference)  \(.mergedAt // "—")  \(.title)"'

# Count + hasNextPage summary
| jq '"Total: \(.data.count), hasNextPage: \(.data.pageInfo.hasNextPage)"'

# Full table with count header
| jq -r '"Total: \(.data.count)", (.data.nodes[] | "  \(.reference)\t\(.state)\t\(.title)")'
```

## Pagination

```bash
# First page
glab api --method POST glql \
  --raw-field 'glql_yaml=limit: 10
query: project = "group/project" AND state = opened'

# Next page -- pass endCursor from previous response
glab api --method POST glql \
  --raw-field 'glql_yaml=limit: 10
query: project = "group/project" AND state = opened' \
  --raw-field 'after=<endCursor>'
```

Only forward pagination is supported (`after` + `endCursor`).

## Response shape

`reference`, `iid`, and `webUrl` are always present in every node. Everything else is determined
by `fields:`. The `fields` array in the response reflects what was requested.

```json
{
  "success": true,
  "error": null,
  "fields": [
    { "key": "id",    "label": "ID",    "name": "id"    },
    { "key": "title", "label": "Title", "name": "title" },
    { "key": "state", "label": "State", "name": "state" }
  ],
  "data": {
    "count": 42,
    "nodes": [
      {
        "id": "gid://gitlab/Issue/123",
        "iid": "123",
        "reference": "#123",
        "state": "OPEN",
        "title": "...",
        "webUrl": "https://gitlab.com/..."
      }
    ],
    "pageInfo": {
      "startCursor": "...",
      "endCursor": "...",
      "hasNextPage": true,
      "hasPreviousPage": false
    }
  }
}
```

## Rate limiting and timeouts

- Queries are rate-limited by SHA-256 hash of the query string.
- Repeated timeouts on the same query temporarily block it (returns `429`).
- If a group-scoped query times out, narrow it with `assignee`, `label`, `milestone`, or a date filter.
- Maximum input size: 10,000 bytes for `glql_yaml`.
