# MR Review — Notes, Code Suggestions, Discussions

**Default to `glab mr note` for every MR-comment operation** — read, write, reply, resolve,
and batch drafts. The raw `glab api` paths exist only for these cases:

1. **Pending drafts on older glab** (Section 3) — only when `glab mr note draft` doesn't
   exist (glab older than v1.122.0).
2. **Raw discussion JSON / position metadata** (Section 4) — when you need fields that
   `glab mr note list -F json` doesn't surface (e.g. full position diff refs).

If your task is "list / post / reply / resolve a single MR comment", use Section 1. **Do not
reach for `glab api` for these operations** — it produces brittle, gotcha-laden code when a
one-liner suffices.

Always check existing discussions before posting — earlier threads may already be resolved or
outdated.

## 1. `glab mr note` (preferred)

### List discussions

```bash
# Auto-detects MR from current branch
glab mr note list

# Filter by resolution state, type, or file
glab mr note list --state unresolved          # state: all | resolved | unresolved
glab mr note list --type diff                 # type:  all | general | diff | system
glab mr note list --file src/main.go          # only diff notes on this path

# JSON output for scripting
glab mr note list -F json | jq '.[] | {id, resolved, position}'

# Specific MR
glab mr note list 123
```

`-F json` returns discussion objects with nested `notes[]` — same shape as
`glab api .../discussions` but already filtered.

**`-F json` returns `null` (not `[]`) when there are no discussions.** This breaks naive `jq`
pipelines like `jq '.[]'` or `jq 'length'`. Guard with one of:

```bash
glab mr note list -F json | jq '. // [] | length'                     # default to []
glab mr note list -F json | jq 'if . == null then [] else . end | .[]' # iterate safely
```

### General comments

```bash
glab mr note create -m "Looks good!"
glab mr note create -m "$(cat "$MSG")"        # multi-line / backtick-safe (see SKILL.md)
echo "LGTM" | glab mr note create             # body from stdin

# Idempotent — skip if a note with the same body already exists
glab mr note create -m "LGTM" --unique
```

### Reply to an existing discussion thread

```bash
# Discussion ID prefix (8+ chars) or full 40-char ID
glab mr note create --reply abc12345 -m "Fixed in the next commit."
```

### Comments on diff lines

```bash
# Diff comment on a specific line (new side / added or unchanged line)
glab mr note create --file src/main.go --line 42 -m "Rename this variable."

# Multi-line range (anchor + N lines)
glab mr note create --file src/main.go --line 10:15 -m "Extract this block."

# Comment on a removed line (old side)
glab mr note create --file src/main.go --old-line 7 -m "Why was this removed?"

# File-level diff comment (no line specified)
glab mr note create --file src/main.go -m "General comment on this file."
```

`glab mr note create --file --line` resolves line types, paths, and version SHAs internally —
no `position` object to hand-build.

### Resolve / reopen threads

```bash
# Accepts discussion ID prefix (8+ chars), full discussion ID, or a note ID
glab mr note resolve abc12345
glab mr note reopen  abc12345

# Targeting a specific MR
glab mr note resolve 123 abc12345          # MR IID first, THEN discussion ID
glab mr note reopen  123 abc12345 -R owner/repo
```

**⚠️ Argument order is `<mr-iid> <discussion-id>`, NOT the reverse.** The CLI `--help` USAGE
line shows `resolve <discussion-id> [<id> | <branch>]` which is confusing — the `<id>` slot
is the MR IID (or branch), and when you pass both, **MR IID comes first**. The EXAMPLES
section of `--help` confirms this (`glab mr note resolve 123 abc12345`).

If a prefix matches multiple discussions, `glab` errors out with the ambiguous matches.

### Flag rules

- `--line` and `--old-line` **require `--file`**, and **cannot be used together**.
- `--file`, `--reply`, and `--unique` are **mutually exclusive**.
- Drafts are a separate command, `glab mr note draft create` (Section 3); `mr note create` has no `--draft` flag.
- All `create` subcommands accept the MR IID as a positional argument; omit it to auto-detect
  from the current branch.

### Targeting a specific MR or repo

The MR IID is always a **positional argument** (there is no `--mr` flag). Omit it to
auto-detect from the current branch.

```bash
glab mr note create 123 -m "Comment on MR 123"
glab mr note create 123 -R owner/repo -m "..."
glab mr note list -R owner/repo
glab mr note resolve 123 abc12345          # MR IID first, then discussion ID
glab mr note resolve abc12345              # auto-detect MR
```

### Multi-line bodies with backticks / code blocks

Follow the message-escaping rule from SKILL.md — write the body to a file with `<< 'EOF'`,
then pass `$(cat "$FILE")`:

```bash
MSG=$(mktemp)
cat > "$MSG" << 'EOF'
**Title**

Explanation with `inline code` and `$VAR`.

```go
// suggested fix
```
EOF
glab mr note create --file main.go --line 42 -m "$(cat "$MSG")"
```

---

## 2. Code suggestions

When you want to propose a specific change, embed GitLab's suggestion syntax in the note body.
GitLab renders an "Apply suggestion" button on the diff. Suggestions work in both
`glab mr note create --file --line ...` and draft notes.

Single-line replacement (comment anchored on that line):

````text
```suggestion:-0+0
replacement code here
```
````

Multi-line replacement — `-N` includes N lines above the anchor, `+M` includes M lines below:

````text
```suggestion:-2+1
all replacement lines here
```
````

Use suggestions when you have a concrete fix. Use plain text comments for questions or
broader patterns.

---

## 3. Draft notes (batched reviews)

`glab mr note draft` is **experimental** (help text: "might be unstable or removed at any
time"). It needs glab v1.122.0 or newer (older glab: see the raw-API fallback below). Each comment becomes a pending draft, and `publish`
posts them as one review event (one notification):

```bash
glab mr note draft create <iid> --file path/to/file --line 42 -m "$(cat "$MSG")"
glab mr note draft create <iid> --file path/to/file --old-line 7 -m "$(cat "$MSG2")"
glab mr note draft publish <iid> -m "Summary of the review" --yes
```

Subcommands: `create`, `list`, `update <draft-id>`, `delete <draft-id>`, `publish`. Each takes
an optional MR IID or branch (omit to use the current branch). `update` and `delete` take the
MR IID first, then the draft ID: `glab mr note draft update 123 456 -m "..."`.

- `--line` and `--old-line` **require `--file`** and cannot be used together. `--file` and `--reply` are **mutually
  exclusive**. `--line` also takes a range (`10:15`).
- Draft reply: `glab mr note draft create <iid> --reply abc12345 -m "..."` (full discussion ID
  or a unique prefix of 8+ characters).
- `create` prints the new draft's ID; capture it with `id=$(glab mr note draft create ...)`.
- `create`/`update` also accept `--attach <file>`.
- **Always pass `--yes` to `publish`** (and `delete`) — without a TTY they fail instead of prompting.
- `publish` sends **all** of your pending drafts on the MR, so list leftovers first.
- `publish --reviewer-state reviewed|requested_changes` also sets your review state. It records
  no approval (use `glab mr approve`). On your own MR, GitLab ignores it unless you are also
  listed as a reviewer; glab warns when that happens, so treat the warning as "state not set".
- Drafts are per-user: `list`, `update`, `delete` and `publish` only touch your own.

```bash
glab mr note draft list <iid> -F json | jq '.[].id'   # also: --file <path>, --jq
glab mr note draft update <iid> <draft-id> -m "new text"
glab mr note draft delete <iid> <draft-id> --yes
```

For any single comment, prefer `glab mr note create` above.

### Fallback: raw API (glab without `mr note draft`)

Use only on glab older than v1.122.0, where `glab mr note delete`/`update` don't work on draft
IDs and there is no list command.

```bash
# List. Once published, this returns an empty array. A draft with .position == null is a
# general note or a reply; drafts on removed lines have old_line set and new_line null.
glab api --method GET --paginate \
  "projects/<project_id>/merge_requests/<mr_iid>/draft_notes" \
  | jq '.[] | {id, path: .position.new_path, new_line: .position.new_line, old_line: .position.old_line, reply_to: .discussion_id, note: .note[0:40]}'

# Edit the text of one draft
glab api --method PUT \
  "projects/<project_id>/merge_requests/<mr_iid>/draft_notes/<draft_id>" \
  -F "note=@$MSG"

# Delete one draft
glab api --method DELETE \
  "projects/<project_id>/merge_requests/<mr_iid>/draft_notes/<draft_id>"

# Publish all of your drafts
glab api --method POST \
  "projects/<project_id>/merge_requests/<mr_iid>/draft_notes/bulk_publish"
```

---

## 4. Discussions via `glab api` (last-resort fallback)

MR diffs: `glab mr diff <iid> --raw` for the whole diff. For the changed paths or one file:
`glab api "projects/<project_id>/merge_requests/<mr_iid>/diffs?unidiff=true&per_page=100" | jq '.[] | select(.new_path == "path/to/file") | .diff'`.

**Use Section 1 (`glab mr note`) for any read / reply / resolve.** This section exists only
for the narrow case where you need fields that `glab mr note list -F json` does not surface
(e.g. raw `position.base_sha` / `head_sha` for cross-referencing with the diff endpoint, or
the full `notes[].resolved_by` chain). For "list discussions to find a thread ID" or
"resolve thread X", **do not use these commands** — `glab mr note list` and
`glab mr note resolve` are correct and shorter.

```bash
# Fetch all discussions (each thread has id, notes array, position info)
glab api --method GET "projects/<project_id>/merge_requests/<mr_iid>/discussions?per_page=100"

# Extract key fields
glab api --method GET "projects/<project_id>/merge_requests/<mr_iid>/discussions?per_page=100" \
  | jq '.[] | {id, resolved: .notes[0].resolved, body: .notes[0].body}'
```

### Resolve / reopen via the API

```bash
# Resolve
glab api --method PUT \
  "projects/<project_id>/merge_requests/<mr_iid>/discussions/DISCUSSION_ID" \
  -f resolved=true

# Reopen
glab api --method PUT \
  "projects/<project_id>/merge_requests/<mr_iid>/discussions/DISCUSSION_ID" \
  -f resolved=false
```

For non-batched flows, prefer `glab mr note resolve|reopen <id>`.

---

## 5. `glab api` field flags: `-f` vs `-F`

Evidence for item 17. To probe any assumption in ~30s, set `GLAB_DEBUG_HTTP=1` and `POST` to a
nonexistent issue IID: it prints the serialized request body and guarantees nothing lands.

### `-F`/`--field` converts its inline value; `-f`/`--raw-field` never does

| `-F` inline value | sent as |
|---|---|
| JSON literal `true`/`false`/`null` | `{"body":true}` — not a string |
| integer `123`, `007` | `123`, `7` (leading zeros dropped; **only** integers — `12.5`, `1e3`, `" true"` stay strings) |
| value starting with `{` or `[` | parsed as JSON (an object/array); invalid JSON fails loudly, e.g. `-F 'body=[WIP] fix'` |
| leading `@`, e.g. `@note.md` | the contents of `note.md` |
| `:repo`/`:namespace`/`:branch`/`:fullpath` | substituted **anywhere in the value** (substring match; they're Ruby symbols too) |

The placeholder row is the trap — it's a substring match:

```
# remote is <group>/<project>
-F "body=opts[:namespace] ||= params[:repo]"  → {"body":"opts[<group>] ||= params[<project>]"}  sent, exit 0, no warning
-f "body=opts[:namespace] ||= params[:repo]"  → unchanged                                       -f has no conversion surface
```

**Conversions apply to the inline value only** — content read through `@` passes untouched
(verified for both type inference and placeholders). `-F "body=@$MSG"` also preserves the file's
trailing newline, has no size ceiling, and **aborts loudly, sending nothing, if the file is
missing**. One hole: `@-` reads **stdin**, and with nothing piped sends `{"body":""}` silently.

### `-f "body=$(cat "$MSG")"` is the weaker transport for a file (shell limits, not glab)

- **A failed `$(cat …)` sends an empty body, not an error** — even under `set -e`, a failing
  command substitution inside an argument does not abort. This is why item 17's repair `PUT`
  uses `-F "body=@$MSG"`: a mistyped path there would replace real content with an empty body.
- **~128 KiB per argument** (`MAX_ARG_STRLEN`, not `ARG_MAX`): a 131,067-byte body dies with
  `Argument list too long`, nothing sent. `-F "body=@file"` has no such limit (note bodies
  allow up to 1,000,000 chars).
- **`$()` strips trailing newlines and drops NUL bytes**; `-F "body=@file"` preserves both.

Non-UTF-8 bytes become U+FFFD under **both** flags (Go's JSON encoder) — neither is verbatim for
binary content.

### Nested JSON: pass a JSON value or use `--input`

Bracketed names like `position[new_line]` are rejected before sending. Pass the object as a JSON
value (`-F 'position={...}'`) or the whole body with `--input`. `--input` without `-H "Content-Type: application/json"`
returns **HTTP 415**. Write the JSON with a single-quoted `<< 'EOF'` heredoc so backticks and `$`
in review bodies are not interpolated.

## Gotchas

### `glab mr note`

- **EXPERIMENTAL flag** — `glab mr note *` is marked experimental. Stable enough
  for our workflows; watch upstream changelogs for flag changes.
- **`resolve`/`reopen` arg order is `<mr-iid> <discussion-id>`** — the `--help` USAGE line
  reads `<discussion-id> [<id>]` which is misleading. The EXAMPLES line is correct
  (`glab mr note resolve 123 abc12345`). MR IID always first when you pass both.
- **`draft update`/`delete` arg order is `<mr-iid> <draft-id>`** — the `--help` USAGE line
  lists `<draft-note-id> [<id>]`, but with two arguments the last one is the draft ID. The
  EXAMPLES line is correct (`glab mr note draft update 123 456 -m "..."`).
- **Create drafts with `glab mr note draft create`, not the API** — it builds and validates
  the position (version SHAs, line type) against the latest diff.
- **`-F json` returns `null` on empty** — not `[]`. Guard `jq` pipelines with `. // []` or
  `if . == null then [] else . end` before iterating / counting.
- **Ambiguous prefix** — `glab mr note resolve abc12345` errors if more than one discussion
  matches the prefix. Use a longer prefix or the full ID.
- **Flag exclusivity** — `--file`, `--reply`, and `--unique` cannot be combined. To
  idempotently post a diff comment, list existing notes first and check before creating.
- **Auto-detection failure** — if the current branch has no open MR (or is detached), pass
  the MR IID as a positional argument.

### `glab api .../draft_notes` (fallback for old glab)

- **Draft notes are per-user** — you can only list, edit, delete, or publish YOUR drafts.
