---
name: glab
description: GitLab workflow automation using glab CLI
version: 1.5.0
license: MIT
metadata:
  audience: developers
  workflow: gitlab
---

# GitLab Workflow Skill

GitLab workflow management using `glab` CLI for merge requests, issues, and Git best practices.

## Creating Merge Requests

Always pass `--push` and `-H <owner/repo>`. Without `--push`, the branch may not exist on
any remote yet. Without `-H`, glab may pick the wrong remote (e.g. a security mirror) as
the source project, creating the MR from the wrong fork.

```bash
# Simple MR
glab mr create --push -H <owner/repo> --title "feat: add feature" --description "Brief description" --assignee <username>

# Complex MR - write description to file first
glab mr create --push -H <owner/repo> --title "feat: add feature" --description "$(cat /tmp/mr-description.md)" --assignee <username>
```

**Templates:** Check `.gitlab/merge_request_templates/` for project-specific templates.

## Updating Merge Requests

```bash
glab mr update <number> --description "$(cat /tmp/description.md)"
glab mr view <number> -R <owner>/<repo>
```

## Issue Management

```bash
# View / comment
glab issue view <number>
glab issue view <number> --comments -R <owner>/<repo>
glab issue note <number> -m "comment" -R <owner>/<repo>
glab issue note <number> -m "$(cat /tmp/comment.md)" -R <owner>/<repo>

# List (open by default — no --state flag)
glab issue list --label "priority::P1,status::doing" -R <owner>/<repo>
glab issue list --closed -R <owner>/<repo>
glab issue list --all   -R <owner>/<repo>

# Create
glab issue create --title "Bug: title" --description "$(cat /tmp/issue-description.md)"

# Labels — use --label / --unlabel, NEVER +label or -label syntax
glab issue update 123 --label "new-label"
glab issue update 123 --unlabel "old-label"
# Scoped labels auto-replace within their scope — no --unlabel needed:
glab issue update 123 --label "status::doing"   # removes any existing status:: label
```

### Issue State Transitions and Notes

```bash
# Close / reopen
glab api --method PUT "projects/<project_id>/issues/<iid>" -f state_event=close
glab api --method PUT "projects/<project_id>/issues/<iid>" -f state_event=reopen

# Post a comment (note: the body field on PUT is silently ignored — always use POST)
glab api --method POST "projects/<project_id>/issues/<iid>/notes" -f "body=Your comment"
glab api --method POST "projects/<project_id>/issues/<iid>/notes" \
  -f "body=$(cat /tmp/comment.md)"
```

## Work Items

GitLab is migrating issues to work items. The URL shows `/work_items/<iid>` but the REST API is the same.

```bash
# ✅ Use the issues API — same IID, same endpoints
glab api "projects/org%2Fproject/issues/<iid>"
glab api "projects/<project_id>/issues/<iid>/notes"

# ❌ /work_items/ REST endpoint does not exist
glab api "projects/org%2Fproject/work_items/<iid>"   # → 404
```

URL parsing: `https://gitlab.com/org/project/-/work_items/539076`
→ `glab api "projects/org%2Fproject/issues/539076"`

Full details, GraphQL alternative, and group-level work items: **[references/work-items.md](references/work-items.md)**

## MR Review

For MR review operations (draft notes, code suggestions, inline comments, bulk publish):

**[references/mr-review.md](references/mr-review.md)** — covers:
- Fetching MR diffs and version SHAs
- Draft notes (general and inline) with correct JSON piping
- Position objects and line type rules (`+`/`-`/context)
- Code suggestion syntax (`suggestion:-N+M`)
- Bulk publishing all drafts as a single review
- Fetching, replying to, and resolving discussions

## Issue Links and Epics

- **Issue links** (`blocked_by`, `relates_to`): [references/issue-links.md](references/issue-links.md)
- **Epics CRUD** (create, list, update, close): [references/epics.md](references/epics.md)
- **Epic comments** (GraphQL read/write, pagination): [references/epic-comments.md](references/epic-comments.md)
- **Nested groups** (`%2F` encoding): [references/nested-groups.md](references/nested-groups.md)

## Epics — Critical Notes

**⚠️ Epic comments require GraphQL** — the REST `/notes` endpoint returns 404.

**Quickest path — use the wrapper scripts:**

```bash
# Read all comments (handles pagination)
epic-notes.sh <group-path> <epic-iid>
epic-notes.sh gitlab-org 16428

# Post a comment
create-epic-note.sh <group-id> <epic-iid> "body"
create-epic-note.sh 9970 16428 "My comment"
```

Scripts are in `scripts/`; GraphQL templates in `assets/graphql/`.

**Manual GraphQL (when you need more control):**

```bash
# iid must be a quoted string: "16428" not 16428 (integer → type error)
glab api graphql -f query='
{
  group(fullPath: "gitlab-org") {
    workItem(iid: "16428") {
      widgets {
        type
        ... on WorkItemWidgetNotes {
          discussions(first: 100) {
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
# If hasNextPage: true → re-run with discussions(first: 100, after: "<endCursor>")
```

**Epic close/reopen** — REST works fine, no GraphQL needed:

```bash
glab api --method PUT "groups/<group_id>/epics/<iid>" -f state_event=close
glab api --method PUT "groups/<group_id>/epics/<iid>" -f state_event=reopen
```

**Nested groups** — REST requires `%2F`; GraphQL uses plain `/`:

```bash
glab api "groups/gitlab-org%2Ffoundations/epics"                    # ✅ REST
glab api "groups/gitlab-org/foundations/epics"                      # ❌ 404
glab api graphql -f query='{ group(fullPath: "gitlab-org/foundations") { ... } }'  # ✅
```

## MR Listing and Filtering

```bash
glab mr list -R <owner>/<repo>                   # open (default)
glab mr list -R <owner>/<repo> --assignee <user>
glab mr list -R <owner>/<repo> --all             # all states
glab mr list -R <owner>/<repo> --merged
glab mr list -R <owner>/<repo> --closed
glab mr list -R <owner>/<repo> --author <user>
```

**Note:** `glab mr list` has no `--state` or `--status` flag. Use `--all`, `--merged`, `--closed`.

## Search via `glab api`

Use `glab api` to call the GitLab Search REST API directly — no extra CLI flags needed.

### Instance-level search

```bash
# Search issues across the entire instance
glab api "search?scope=issues&search=login+bug" | jq '.[] | {iid, title, web_url}'

# Search merge requests instance-wide
glab api "search?scope=merge_requests&search=refactor" | jq '.[] | {iid, title, state}'

# Paginate: 50 results per page, page 2
glab api "search?scope=issues&search=bug&per_page=50&page=2" | jq '.[] | {iid, title}'

# Filter by state
glab api "search?scope=merge_requests&search=auth&state=merged" | jq '.[] | {iid, title}'
```

### Group-level search

```bash
# Search issues within a group
glab api "groups/gitlab-org/search?scope=issues&search=performance" | jq '.[] | {iid, title, web_url}'

# Search merge requests in a group
glab api "groups/gitlab-org/search?scope=merge_requests&search=refactor" | jq '.[] | {iid, title, state}'

# Nested group — encode the slash as %2F
glab api "groups/gitlab-org%2Ffoundations/search?scope=issues&search=bug" | jq '.[] | {iid, title}'
```

### Project-level search

```bash
# Search issues in a project (URL-encode the project path: / → %2F)
glab api "projects/gitlab-org%2Fcli/search?scope=issues&search=crash" | jq '.[] | {iid, title}'

# Code search (blobs) — requires Advanced Search or Exact Code Search
glab api "projects/gitlab-org%2Fcli/search?scope=blobs&search=handleAuth" | jq '.[] | {path, startline, data}'

# Commits — requires Advanced Search
glab api "projects/gitlab-org%2Fcli/search?scope=commits&search=fix+nil" | jq '.[] | {id, title, authored_date}'

# Wiki pages — requires Advanced Search
glab api "projects/gitlab-org%2Fcli/search?scope=wiki_blobs&search=setup" | jq '.[] | {path, data}'

# Notes (comments) — requires Advanced Search
glab api "projects/gitlab-org%2Fcli/search?scope=notes&search=LGTM" | jq '.[] | {id, body}'
```

### Scope availability

| Scope | Instance | Group | Project | Requires |
|-------|----------|-------|---------|----------|
| `projects` | ✅ | ✅ | — | Free |
| `issues` | ✅ | ✅ | ✅ | Free |
| `merge_requests` | ✅ | ✅ | ✅ | Free |
| `milestones` | ✅ | ✅ | ✅ | Free |
| `users` | ✅ | ✅ | ✅ | Free |
| `work_items` | ✅ | ✅ | ✅ | Free |
| `snippet_titles` | ✅ | — | — | Free |
| `blobs` (code) | — | — | ✅ | Advanced Search or Exact Code Search |
| `commits` | — | — | ✅ | Advanced Search |
| `wiki_blobs` | — | — | ✅ | Advanced Search |
| `notes` | — | — | ✅ | Advanced Search |

## GLQL Queries

To query issues, MRs, or epics across projects/groups, load the **`glab-glql`** skill.

## Git Best Practices

```bash
git checkout -b feat/description    # branch naming
git checkout -b fix/description

# Commit format: type: description (conventional commits)
# Reference issues with full URLs: Closes https://gitlab.com/org/project/-/issues/123
# Use single quotes for special characters: git commit -m 'fix: from MR !123'
```

## Agent Guidelines

1. **`glab mr create` always needs `--push -H <owner/repo>`** — omitting either causes the MR to be created from the wrong remote or fail entirely
2. **Always pass `--assignee <username>` on `glab mr create`** — MRs are unassigned by default; always assign to the author
3. **Read context first** — `glab issue view` / `glab mr view` before implementing
4. **Use project templates** — check `.gitlab/issue_templates/` and `.gitlab/merge_request_templates/`
5. **Write descriptions to files** — use `$(cat /tmp/description.md)` not inline strings
6. **Reference with full URLs** — `Closes https://gitlab.com/org/project/-/issues/123`
7. **Descriptive commits** — focus on the "why"
8. **Single quotes for special chars** — `git commit -m 'fix: from MR !123'`
9. **Label syntax** — `--label` to add, `--unlabel` to remove; never `+label`/`-label`
10. **Scoped labels** — `--label "status::doing"` auto-removes old `status::*`; no `--unlabel` needed
11. **No `--jq` flag** — glab has no `--jq`; use `| jq '...'` pipe
12. **No `--state`/`--status` on `mr list`** — use `--all`, `--merged`, `--closed`
13. **Work items use the issues API** — `/work_items/<iid>` URLs → `projects/.../issues/<iid>`
14. **Epic comments need GraphQL** — REST `/notes` → 404; use `epic-notes.sh` or manual GraphQL with `first: 100` + pagination
15. **No `-R` for group-level API** — `-R` expects `OWNER/REPO`; group endpoints use `glab api "groups/..."` directly
16. **Nested groups REST: `%2F`** — `groups/org%2Fsubgroup/epics`; unencoded slashes → 404
17. **GraphQL iid is a String** — `workItem(iid: "16428")` not `workItem(iid: 16428)`
18. **`groups/<id>/work_items` is 404** — use `groups/<id>/epics` (REST) or GraphQL
19. **`project.workItems` not `project.workItem`** — singular doesn't exist; use `workItems(first: 1, iid: "IID")`; no `filter:` argument
20. **Epic close/reopen via REST** — `state_event=close`/`reopen` on `PUT groups/<id>/epics/<iid>` works; no GraphQL needed
21. **No `--body` flag** — glab uses `--description`, not `--body` (which is a `gh` flag); they are not interchangeable
22. **Search: URL-encode project paths** — use `%2F` for `/` in project paths: `projects/gitlab-org%2Fcli/search?...`
23. **Search: no `--jq` flag** — pipe search results through `| jq '...'`; never use `--jq`
24. **Search: tier restrictions** — `blobs` requires Advanced Search or Exact Code Search; `commits`, `wiki_blobs`, and `notes` require Advanced Search; Free tier only supports `projects`, `issues`, `merge_requests`, `milestones`, `users`, `work_items`, and `snippet_titles`
25. **Search: pagination** — add `per_page=<n>&page=<n>` query params to paginate; default page size is 20, max is 100
26. **Search: nested groups need `%2F`** — `groups/gitlab-org%2Fsubgroup/search?...`; unencoded slashes → 404

## Contributing Improvements

If you discover that any guidance in this skill is **inaccurate or outdated** (e.g., a command that no longer works, a wrong flag, an incorrect API behavior), confirm with the user and open an MR to `gitlab-org/ai/skills` with the fix. Keep changes focused — one fix per MR.
