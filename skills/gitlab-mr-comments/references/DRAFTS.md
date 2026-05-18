# Draft Reviews (batched via `glab api`)

`glab mr note create` publishes comments **immediately** — there is no draft mode in `glab mr note`. When you need to batch multiple inline comments and publish them together as a single review event (one notification, all comments grouped), use the `glab api .../draft_notes` path described in the `glab` skill's `mr-review.md`.

> **Note:** This is the one workflow where the raw API is still required. For any single comment — reply, diff note, or general — prefer `glab mr note create`.

## Creating Draft Notes

### General draft note (not inline)

```bash
glab api --method POST \
  "projects/<project_id>/merge_requests/<mr_iid>/draft_notes" \
  -f note=":robot: AI-generated

Your summary comment here"
```

### Inline draft note (attached to a diff line)

**Do NOT use `-f` flags for inline draft notes** — the nested `position` object will not serialize correctly and the comment will silently appear as a general (non-inline) note. Use JSON piped with `Content-Type: application/json`:

```bash
echo '{"note":":robot: AI-generated\n\nNit: rename this","position":{"position_type":"text","base_sha":"BASE_SHA","head_sha":"HEAD_SHA","start_sha":"START_SHA","old_path":"path/to/file.rb","new_path":"path/to/file.rb","new_line":42}}' \
  | glab api --method POST \
    "projects/<project_id>/merge_requests/<mr_iid>/draft_notes" \
    -H "Content-Type: application/json" --input -
```

For multi-line note bodies, write the JSON to a file first:

```bash
cat > /tmp/draft.json << 'DRAFT'
{
  "note": ":robot: AI-generated\n\nNit: rename this",
  "position": {
    "position_type": "text",
    "base_sha": "BASE_SHA",
    "head_sha": "HEAD_SHA",
    "start_sha": "START_SHA",
    "old_path": "path/to/file.rb",
    "new_path": "path/to/file.rb",
    "new_line": 42
  }
}
DRAFT
glab api --method POST \
  "projects/<project_id>/merge_requests/<mr_iid>/draft_notes" \
  -H "Content-Type: application/json" --input /tmp/draft.json
```

### Fetching MR version SHAs

Inline draft notes require three SHAs from the latest MR version. Always fetch fresh — cached SHAs may be rejected.

```bash
# ⚠️ API returns base_commit_sha / head_commit_sha / start_commit_sha
# but the position object expects base_sha / head_sha / start_sha — jq renames here
glab api "projects/<project_id>/merge_requests/<mr_iid>/versions" \
  | jq '.[0] | {base_sha: .base_commit_sha, head_sha: .head_commit_sha, start_sha: .start_commit_sha}'
```

## Managing Drafts

```bash
# List pending draft notes
glab api "projects/<project_id>/merge_requests/<mr_iid>/draft_notes"

# Publish all drafts (ONLY when user explicitly asks)
glab api --method POST \
  "projects/<project_id>/merge_requests/<mr_iid>/draft_notes/bulk_publish"
```

## Publishing Rules for Drafts

1. **Never run `bulk_publish` without the user explicitly requesting it.**
2. After creating drafts, report what's pending and let the user decide when to publish.
3. Use drafts as the default when the user wants to review comments before they go live.

## Auto-detection

The `glab api` path requires explicit `<project_id>` and `<mr_iid>`. Fetch them from `glab mr view --output json | jq '{iid, project_id}'` if needed.
