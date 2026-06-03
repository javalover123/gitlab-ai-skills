# Epic Comments (Notes)

**⚠️ The REST `/groups/<id>/epics/<iid>/notes` endpoint returns 404 — it does not exist.**

Both **GET and POST** on this endpoint 404. Verified on gitlab.com and on a GitLab
19.1 instance (GDK) — the GraphQL path below is still the only way to read or write
epic comments, and there is no native `glab epic` subcommand. Epics are internally
implemented as work items; use GraphQL or the wrapper scripts.

## Quick start — use the scripts

```bash
# Read comments (handles pagination automatically)
epic-notes.sh <group-path> <epic-iid>
# Example:
epic-notes.sh gitlab-org 16428

# Post a comment
create-epic-note.sh <group-id> <epic-iid> "comment body"
# Example:
create-epic-note.sh 9970 16428 "This is my comment"
```

Scripts live in `scripts/` alongside the skill. See the script source for the full GraphQL used.

## Reading comments — GraphQL

Pass the group path and iid as **GraphQL variables** (`-f`, raw string — `-F`
coerces a numeric-looking iid to Int, failing `String!`). `first: 100` fetches all
discussions for most epics in one shot.

```bash
glab api graphql -f groupPath=gitlab-org -f epicIid="16428" -F pageSize=100 \
  -f query='
query($groupPath: ID!, $epicIid: String!, $pageSize: Int = 100, $cursor: String) {
  group(fullPath: $groupPath) {
    workItem(iid: $epicIid) {
      widgets {
        type
        ... on WorkItemWidgetNotes {
          discussions(first: $pageSize, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              notes {
                nodes { id body author { username } createdAt }
              }
            }
          }
        }
      }
    }
  }
}'
```

Response structure:
- `widgets[].type == "NOTES"` → contains `discussions`
- Each `discussion` is a thread; `notes.nodes` is the list of replies in that thread
- `pageInfo.hasNextPage` + `pageInfo.endCursor` drive pagination

## Pagination

If `pageInfo.hasNextPage` is `true`, re-run the same query with the `cursor`
variable set to the previous page's `endCursor`:

```bash
glab api graphql -f groupPath=<group-path> -f epicIid="<epic_iid>" \
  -F pageSize=100 -f cursor="<endCursor value>" -f query='...'   # same query as above
```

In practice: most epics fit in `pageSize: 100`. Only very high-traffic epics need multiple pages.

## Posting a comment — GraphQL mutation

The REST notes endpoint (POST) also returns 404. Use the `createNote` GraphQL
mutation, passing `noteableId` and `body` as **variables** (`-f`). Do **not**
string-interpolate the body into the query: bodies with newlines, backticks, `$`,
or non-ASCII characters (e.g. an em dash) break the query — and on GitLab 19.1+ a
stray non-ASCII byte outside a `#` comment raises `UNKNOWN_CHAR`. Variables sidestep
all of it.

```bash
# Step 1: get the epic's internal id (not iid)
EPIC_ID=$(glab api "groups/<group_id>/epics/<epic_iid>" | jq '.id')

# Step 2: post the note (body passed as a variable, no escaping needed)
glab api graphql \
  -f noteableId="gid://gitlab/Epic/${EPIC_ID}" \
  -f body="Your comment here" \
  -f query='
mutation($noteableId: NoteableID!, $body: String!) {
  createNote(input: { noteableId: $noteableId, body: $body }) {
    note { id body }
    errors
  }
}'
```

The `noteableId` format is always `gid://gitlab/Epic/<internal_id>` — using the internal `id`, not the `iid`.

## Template files

The `.graphql` files in `assets/graphql/` are parameterised with GraphQL
**variables** (passed via `glab api graphql -f`/`-F`, no string substitution):

- `assets/graphql/epic-notes.graphql` — read query (`groupPath`, `epicIid`, `pageSize`, `cursor`)
- `assets/graphql/create-note.graphql` — `createNote` mutation (`noteableId`, `body`)

## Why REST doesn't work

GitLab migrated epics to the work items data model. The legacy REST endpoints for epic notes (`/notes`, `/discussions`) were removed. The epic response still includes a `work_item_id` field that exposes this relationship. GraphQL via `group.workItem(iid: "...")` is the stable path.
