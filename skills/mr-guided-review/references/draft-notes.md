# Staging draft notes on a merge request

Phase 3b of [the skill](../SKILL.md). Everything here creates *unpublished* draft
notes. Publishing stays with the reviewer: never call
`PUT .../draft_notes/:id/publish` or `POST .../draft_notes/bulk_publish`.

## Get the diff anchors

```bash
glab api "projects/:fullpath/merge_requests/<iid>" | jq '.diff_refs'
```

That returns `base_sha`, `start_sha` and `head_sha`, all three of which the
position needs. The `:fullpath` placeholder resolves from the current repo; for
an MR in another project, pass the URL-encoded path instead
(`gitlab-org%2Fgitlab`).

## Post one draft per finding

Build the JSON with `jq` so multi-line bodies and backticks survive, and pipe it
in with `--input -`. A nested `position` object does not survive `--field`.

```bash
jq -n --rawfile note /tmp/mr-review/01.md \
      --arg base "$BASE_SHA" --arg start "$START_SHA" --arg head "$HEAD_SHA" \
      --arg path "app/services/foo.rb" --argjson line 42 \
  '{note: $note,
    position: {base_sha: $base, start_sha: $start, head_sha: $head,
               position_type: "text",
               new_path: $path, old_path: $path, new_line: $line}}' \
| glab api "projects/:fullpath/merge_requests/<iid>/draft_notes" \
    --method POST -H "Content-Type: application/json" --input -
```

`--input` sets no content type of its own. Without that header the request comes
back `HTTP 415 The provided content-type '' is not supported.` and nothing is
staged.

## Positioning rules

A wrong position either returns 400 or silently attaches the comment to the
wrong code, so derive each field from the diff rather than guessing:

- **Added line** (`+` in the diff): `new_path` + `new_line`. Set `old_path` to
  the same file.
- **Removed line** (`-`): `old_path` + `old_line`, and no `new_line`.
- **Unchanged context line**: both `old_line` and `new_line`, and both paths.
- **Renamed file**: `old_path` is the pre-rename path.
- Anchor only to lines that actually appear in a `glab mr diff` hunk. When the
  finding is about code outside the diff, stage it with **no** `position` and
  name the file and line in the body instead.
- Never set `resolve_discussion`. To reply inside an existing thread, pass
  `in_reply_to_discussion_id` and no `position`.

## Verify what landed

```bash
glab api "projects/:fullpath/merge_requests/<iid>/draft_notes" \
  | jq -r '.[] | "\(.id)  \(.position.new_path // "general"):\(.position.new_line // "-")  \(.note[0:60])"'
```

If a post fails, report which one and why. Do not retry with a guessed position.

## Fixing a draft afterwards

- Reword: `PUT .../draft_notes/<id>` with `note`, plus `position` if it moved.
- Wrong line, or unwanted: `DELETE .../draft_notes/<id>`, then re-post if needed.

Both are fine without a fresh go-ahead as long as the reviewer asked for the
change. Publishing still is not.
