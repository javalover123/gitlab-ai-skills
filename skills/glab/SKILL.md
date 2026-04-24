---
name: glab
description: GitLab workflow automation using glab CLI
version: 1.6.0
category: Development Workflow
license: MIT
metadata:
  audience: developers
  workflow: gitlab
---

# GitLab Workflow Skill

GitLab workflow management using `glab` CLI for merge requests, issues, and Git best practices.

## ⚠️ Message Escaping — Common Trap

**If your message contains backticks (`` ` ``), `$`, or other shell special characters, NEVER inline them directly in `-m "..."`.** The shell interprets backticks as command substitution, silently mangling your message and producing errors like `/bin/bash: line 1: client_name: command not found`.

This has caused real production failures: agents posting malformed comments to GitLab MRs/issues, followed by apologetic correction notes.

### ❌ DON'T — inline backticks in double-quoted -m

```bash
# BROKEN: shell tries to execute `client_name` as a command
glab mr note 100 -m "Use `client_name` and `wor/` here." -R org/repo
# Error: /bin/bash: line 1: client_name: command not found
# The comment is posted as: "Use  and  here." (identifiers silently stripped)

# Also BROKEN: backslash-escaped backticks break in nested/scripted contexts
glab mr note 100 -m "Use \`client_name\`" -R org/repo
# Works in simple cases but fails when the command is double-quoted by a caller:
# bash -c "glab mr note 100 -m \"Use \`client_name\`\""  → still executes client_name
```

### ✅ DO — write to a file first, then pass via $(cat ...)

Pick a path appropriate for your environment (a `mktemp` result, a scoped workspace tmp file, whatever fits — the skill doesn't prescribe a specific path; agents choose one that's unique to their invocation to avoid clobbering parallel runs):

```bash
# MSG = path you choose (e.g. mktemp, ~/workspace/tmp/note-$$.md, etc.)
MSG=<agent picks>

cat > "$MSG" << 'EOF'
Use `client_name` and `wor/` here. The `glab` tool handles this.
EOF
glab mr note 100 -m "$(cat "$MSG")" -R org/repo
```

The single-quoted `'EOF'` heredoc delimiter prevents ALL variable/backtick expansion when writing the file. The `$(cat "$MSG")` substitution is safe because the file content is already written literally. **Triple-backtick code blocks (` ``` `) are also safe inside `<<'EOF'` heredocs** — no escaping needed; only single-backticks and `$` trigger command substitution.

### ✅ Also safe — glab api with -f flag

```bash
glab api --method POST "projects/org%2Frepo/merge_requests/100/notes" \
  -f "body=$(cat "$MSG")"
```

### ⚠️ Unquoted heredoc still interprets backticks

```bash
# BROKEN: unquoted EOF delimiter — backticks in body are still interpreted
cat > "$MSG" << EOF
Use `client_name` here.    # ← shell executes client_name when writing the file
EOF
```

### ⚠️ Heredoc-inside-heredoc breaks shell parsing

If your content itself contains a heredoc example **with an unindented `EOF` terminator**, the inner `EOF` at column 0 closes the outer heredoc early:

```bash
# BROKEN: the inner EOF is at column 0 — it closes the OUTER heredoc early
cat > "$OUTER" << 'EOF'
Here is the safe pattern:
cat > "$MSG" << 'EOF'
Use `client_name` here.
EOF
# ↑ This EOF terminates the OUTER heredoc — the lines below run as shell commands!
echo "more content..."
EOF
# ↑ This stray EOF becomes a command: "EOF: command not found"
```

**Fix — use a different delimiter for the outer heredoc:**

```bash
cat > "$OUTER" << 'OUTEREOF'
Here is the safe pattern:
  cat > "$MSG" << 'EOF'
  Use `client_name` here.
  EOF
OUTEREOF
```

Or write the file in chunks — first chunk uses `>`, subsequent chunks use `>>`, each with its own delimiter.

**Rule of thumb:** If the message contains `` ` ``, `$`, `!`, or `\` — write to a file with `<< 'EOF'` first, always. If the content itself contains heredoc syntax, use a unique outer delimiter (e.g. `OUTEREOF`, `MSGEOF`) that won't appear in the body.

## Creating Merge Requests

Always pass `--push` and `-H <owner/repo>`. Without `--push`, the branch may not exist on
any remote yet. Without `-H`, glab may pick the wrong remote (e.g. a security mirror) as
the source project, creating the MR from the wrong fork.

```bash
# Simple MR
glab mr create --push -H <owner/repo> --title "feat: add feature" --description "Brief description" --assignee <username>

# Complex MR - write description to file first (pick your own path)
glab mr create --push -H <owner/repo> --title "feat: add feature" --description "$(cat "$DESC")" --assignee <username>
```

**Templates:** Check `.gitlab/merge_request_templates/` for project-specific templates.

## Updating Merge Requests

```bash
glab mr update <number> --description "$(cat "$DESC")"
glab mr view <number> -R <owner>/<repo>
```

## Issue Management

```bash
# View / comment
glab issue view <number>
glab issue view <number> --comments -R <owner>/<repo>
glab issue note <number> -m "comment" -R <owner>/<repo>
glab issue note <number> -m "$(cat "$MSG")" -R <owner>/<repo>

# List (open by default — no --state flag)
glab issue list --label "priority::P1,status::doing" -R <owner>/<repo>
glab issue list --closed -R <owner>/<repo>
glab issue list --all   -R <owner>/<repo>

# Create
glab issue create --title "Bug: title" --description "$(cat "$DESC")"

# Labels — use --label / --unlabel, NEVER +label or -label syntax
glab issue update 123 --label "new-label"
glab issue update 123 --unlabel "old-label"
# Scoped labels auto-replace within their scope — no --unlabel needed:
glab issue update 123 --label "status::doing"   # removes any existing status:: label
```

For issue state transitions (close/reopen via API) and posting notes via `glab api`: **[references/issue-api.md](references/issue-api.md)**

## Work Items

GitLab is migrating issues to work items. The URL shows `/work_items/<iid>` but the REST API is the same.

```bash
# ✅ Use the issues API — same IID, same endpoints
glab api "projects/org%2Fproject/issues/<iid>"

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

## Issue Links, Epics, and Nested Groups

- **Issue links** (`blocked_by`, `relates_to`): [references/issue-links.md](references/issue-links.md)
- **Epics CRUD** (create, list, update, close): [references/epics.md](references/epics.md)
- **Epic comments** (GraphQL read/write, pagination — REST returns 404): [references/epic-comments.md](references/epic-comments.md)
- **Nested groups** (`%2F` encoding): [references/nested-groups.md](references/nested-groups.md)

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

## Search

For full search examples (instance / group / project, scope table, pagination): **[references/search.md](references/search.md)**

Quick reference:

```bash
glab api "search?scope=issues&search=<query>" | jq '.[] | {iid, title}'
glab api "groups/<group>/search?scope=merge_requests&search=<query>" | jq '.[]'
glab api "projects/<org>%2F<repo>/search?scope=issues&search=<query>" | jq '.[]'
```

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
5. **Write descriptions to files** — use `$(cat "$FILE")` not inline strings; you pick the path
6. **Reference with full URLs** — `Closes https://gitlab.com/org/project/-/issues/123`
7. **Descriptive commits** — focus on the "why"
8. **Single quotes for special chars** — `git commit -m 'fix: from MR !123'`
9. **Label syntax** — `--label` to add, `--unlabel` to remove; never `+label`/`-label`
10. **Scoped labels** — `--label "status::doing"` auto-removes old `status::*`; no `--unlabel` needed
11. **No `--jq` flag** — glab has no `--jq`; use `| jq '...'` pipe
12. **No `--state`/`--status` on `mr list`** — use `--all`, `--merged`, `--closed`
13. **Work items use the issues API** — `/work_items/<iid>` URLs → `projects/.../issues/<iid>`
14. **Epic comments need GraphQL** — REST `/notes` → 404; see [references/epic-comments.md](references/epic-comments.md)
15. **No `-R` for group-level API** — `-R` expects `OWNER/REPO`; group endpoints use `glab api "groups/..."` directly
16. **Nested groups REST: `%2F`** — `groups/org%2Fsubgroup/epics`; unencoded slashes → 404
17. **GraphQL iid is a String** — `workItem(iid: "16428")` not `workItem(iid: 16428)`
18. **`groups/<id>/work_items` is 404** — use `groups/<id>/epics` (REST) or GraphQL
19. **`project.workItems` not `project.workItem`** — singular doesn't exist; use `workItems(first: 1, iid: "IID")`; no `filter:` argument
20. **Epic close/reopen via REST** — `state_event=close`/`reopen` on `PUT groups/<id>/epics/<iid>` works; no GraphQL needed
21. **No `--body` flag** — glab uses `--description`, not `--body` (which is a `gh` flag); they are not interchangeable
22. **Search: URL-encode project paths** — use `%2F` for `/`; see [references/search.md](references/search.md) for full examples
23. **Backticks in messages → write to a file you name yourself** — never inline `` ` `` in `-m "..."` or `--description "..."`; write to a file you pick (e.g. `mktemp`, a workspace tmp path — unique per invocation to avoid clobbering parallel agents) using `<< 'EOF'` (single-quoted delimiter, critical), then pass via `$(cat "$FILE")`

## Contributing Improvements

If you discover that any guidance in this skill is **inaccurate or outdated** (e.g., a command that no longer works, a wrong flag, an incorrect API behavior), confirm with the user and open an MR to `gitlab-org/ai/skills` with the fix. Keep changes focused — one fix per MR.
