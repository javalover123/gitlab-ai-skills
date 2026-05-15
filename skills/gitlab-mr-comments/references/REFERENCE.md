# GitLab MR Comments — API Reference

## API Structure

### GraphQL Query: getDiscussions

Returns discussions (comment threads) from a merge request. Each discussion contains multiple notes.

```graphql
query getMrDiscussions($projectPath: ID!, $iid: String!) {
  project(fullPath: $projectPath) {
    mergeRequest(iid: $iid) {
      discussions {
        nodes {
          id
          replyId          # Discussion ID for creating replies
          createdAt
          resolved
          resolvable
          notes {
            nodes {
              id
              author { name, username, avatarUrl }
              body           # Markdown text
              bodyHtml       # Rendered HTML
              createdAt
              position       # null for general notes, object for diff notes
            }
          }
        }
      }
    }
  }
}
```

## Position Object Structure

The `position` field on a note determines where it appears in the diff. It is `null` for general MR comments.

```json
{
  "diffRefs": {
    "baseSha": "abc123...",
    "headSha": "def456...",
    "startSha": "ghi789..."
  },
  "filePath": "src/file.ts",
  "newPath": "src/file.ts",
  "oldPath": "src/file.ts",
  "positionType": "text",
  "newLine": 42,
  "oldLine": 38
}
```

### Position Types

#### Added Line

```json
{ "newLine": 42, "oldLine": null }
```

Comment on code **added** in the MR. Only exists in the new version. Use `newPath` and `headSha`.

#### Removed Line

```json
{ "newLine": null, "oldLine": 38 }
```

Comment on code **removed** in the MR. Only exists in the old version. Use `oldPath` and `baseSha`.

#### Unchanged Line

```json
{ "newLine": 42, "oldLine": 38 }
```

Comment on code in **both versions**. Line numbers may differ if lines were added/removed above. Use `newPath` and `headSha` by convention.

## Line Number Indexing

GitLab API uses **1-indexed** line numbers. Most editors use 0-indexed.

```
GitLab API → Editor:  editorLine = glLine - 1
Editor → GitLab API:  glLine = editorLine + 1
```

## Authentication

The `note` CLI uses `glab` CLI for authentication:
- Stored credentials from `glab auth login`
- `GITLAB_TOKEN` environment variable
- Supports multiple GitLab instances

## Error Handling

Common errors:
- **Authentication failed**: Run `glab auth login`
- **MR not found**: Check project path and MR IID
- **Insufficient permissions**: Need at least Reporter role

## Note Creation — Position Building

To create diff notes via the API directly, you need a complete position object:

1. Fetch MR diffs (get `diffRefs`)
2. Find target file in diffs
3. Parse diff hunks to map line numbers
4. Determine position type:
   - Added: `newLine` set, `oldLine` null
   - Removed: `oldLine` set, `newLine` null
   - Unchanged: both set (requires parsing diff)
5. Build position object
6. Call `createDiffNote` mutation

The `glab mr note create` command and the `note` CLI both handle all of this automatically — prefer either over raw API calls.
