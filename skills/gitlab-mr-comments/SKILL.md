---
name: gitlab-mr-comments
description: Use when creating, reading, replying to, or resolving comments on a GitLab merge request — diff-line notes, thread replies, general notes, and discussion resolution via glab mr note. Also covers batched draft reviews via the optional note CLI. Keywords - GitLab, merge request, MR, comments, notes, code review, diff, resolve, feedback, discussion.
version: 1.0.0
category: Development Workflow
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: gitlab-review
  upstream: https://gitlab.com/viktomas/gitlab-mr-comments
  upstream-author: viktomas
---

# GitLab MR Comments

Read, create, and manage comments on GitLab merge requests using `glab mr note` subcommands.

This skill is a focused MR-comments workflow adapted from [`viktomas/gitlab-mr-comments`](https://gitlab.com/viktomas/gitlab-mr-comments). For broader GitLab automation (MR/issue CRUD, pipelines, work items, search), load the `glab` skill instead.

## Prerequisites

1. **[`glab`](https://gitlab.com/gitlab-org/cli)** — GitLab CLI v1.94.0+ (provides `glab mr note`)
   ```bash
   brew install glab
   glab auth login
   ```

2. **[`note`](https://gitlab.com/viktomas/note)** *(optional)* — only required for batched draft reviews. See [references/DRAFTS.md](references/DRAFTS.md).

## Publishing Rules

`glab mr note create` publishes comments **immediately** — there is no draft mode in `glab`. Follow these rules:

1. **Always confirm with the user before posting.** Show the exact comment text and target (thread, file:line, or general) before running any `glab mr note create` command.
2. **Replying to existing threads** → show the reply text, then use `glab mr note create --reply <id>`.
3. **New comments on diff lines** → show the comment text and target location, then use `glab mr note create --file --line`.
4. **General comments** → show the comment text, then use `glab mr note create`.

**Confirm before every write. Everything is published immediately.**

For draft reviews (batch comments that stay invisible until published), see [references/DRAFTS.md](references/DRAFTS.md) — requires the `note` CLI.

## Auto-detection

When run inside a git worktree whose branch has an open MR, `glab` auto-detects the project and MR — no ID needed. Pass the MR IID as a positional argument only if auto-detection fails or you want to target a different MR.

## Reading Notes

```bash
# List all discussions on the current branch's MR
glab mr note list

# List unresolved discussions
glab mr note list --state unresolved

# List only diff notes
glab mr note list --type diff

# List only diff notes on a specific file
glab mr note list --file src/main.ts

# JSON output — returns discussion objects with nested `notes[]`
glab mr note list -F json

# List discussions on a specific MR
glab mr note list 123
```

### List Options

| Flag | Default | Description |
|------|---------|-------------|
| `--type <type>` | `all` | `all`, `general`, `diff`, or `system` |
| `--state <state>` | `all` | `all`, `resolved`, or `unresolved` |
| `--file <path>` | (none) | Show only diff notes on this file |
| `-F <format>` | `text` | `text` or `json` |
| `-R <repo>` | auto-detect | `OWNER/REPO` or `GROUP/NAMESPACE/REPO` |

### Output Format

```
#d1a2b3c4 [UNRESOLVED] src/example.ts:42 (diff)
  @alice (2024-01-15 10:30): This variable is unused.
  @bob   (2024-01-15 11:00): Fixed, thanks.

#e5f6a7b8 (general)
  @carol (2024-01-15 09:00): Can we add tests for the edge case?
```

Each discussion shows: discussion ID prefix (8 chars), resolution status (if resolvable), file:line (if diff), type, then indented notes with author and timestamp.

## Comment Formatting Convention

**MANDATORY**: ALL outgoing messages MUST be prefixed with `:robot: AI-generated\n\n` followed by the actual content. This applies to every write operation without exception.

Pipe the comment via stdin to preserve formatting:

````bash
glab mr note create --file main.go --line 42 <<'EOF'
:robot: AI-generated

**Title of the finding**

Explanation of the problem.

```go
// suggested fix
```
EOF
````

For inline `-m` flags:

```bash
glab mr note create -m ":robot: AI-generated

Looks good!"
```

> **Heredoc safety:** If your comment body contains backticks, `$`, or `!`, always write to a file with `<< 'EOF'` (single-quoted delimiter) first, then pass via `$(cat "$FILE")` or pipe via stdin. See the `glab` skill's "Message Escaping" section for the full trap list.

## Creating Notes

### Reply to existing discussions

```bash
# Reply to a discussion by ID prefix (8+ chars)
glab mr note create --reply d1a2b3c4 -m ":robot: AI-generated

Good point, will fix."
```

### Comments on diff lines

```bash
# Diff comment on a specific line (new side)
glab mr note create --file main.go --line 42 -m ":robot: AI-generated

Nit: rename this"

# Multiline diff comment (lines 10 through 15)
glab mr note create --file main.go --line 10:15 -m ":robot: AI-generated

Refactor this block"

# Comment on a removed line (old side)
glab mr note create --file main.go --old-line 10 -m ":robot: AI-generated

Why was this removed?"

# File-level diff comment (no line specified)
glab mr note create --file main.go -m ":robot: AI-generated

General comment on this file"
```

### General comments

```bash
glab mr note create -m ":robot: AI-generated

Needs work"

# Body from stdin
echo ":robot: AI-generated

LGTM" | glab mr note create
```

### Idempotent comments

```bash
# Skip if a comment with the same body already exists
glab mr note create -m ":robot: AI-generated

LGTM" --unique
```

`--unique` matches on body only — identical bodies on different diff lines still post (line is part of the position, not the body).

### Targeting a specific MR

```bash
# All create commands accept MR IID as positional argument
glab mr note create 123 -m ":robot: AI-generated

Comment on MR 123"
```

## Managing Discussions

```bash
# Resolve a discussion (by discussion ID prefix or note ID)
glab mr note resolve d1a2b3c4

# Reopen a resolved discussion
glab mr note reopen d1a2b3c4

# On a specific MR
glab mr note resolve 123 d1a2b3c4
```

## Flag Rules

- `--line` and `--old-line` require `--file`, and cannot be used together
- `--file`, `--reply`, and `--unique` are mutually exclusive

## Authentication

Uses `glab` CLI for GitLab authentication:
1. Install `glab` and run `glab auth login`
2. The `GITLAB_TOKEN` environment variable is also respected

## Agent Guidelines

1. **Always prefix `:robot: AI-generated\n\n`** — every outgoing comment, every time.
2. **Confirm before publishing** — `glab mr note create` is not a draft. Show the exact body and target first.
3. **Read before writing** — `glab mr note list --state unresolved` to see context before commenting.
4. **Prefer `--reply` over a new note** when continuing an existing thread; otherwise the conversation fragments.
5. **Use `--unique` on rerun-safe paths** — status comments, recurring summaries — to prevent duplicates.
6. **Heredoc-quote bodies with backticks** — `<< 'EOF'` (single-quoted) for any body containing `` ` ``, `$`, or `!`.
7. **For batched reviews, use the `note` CLI** — see [references/DRAFTS.md](references/DRAFTS.md). Never run `note draft publish` without the user's explicit request.

## References

- `glab mr note --help`, `glab mr note create --help`, `glab mr note list --help` for full CLI usage
- [references/REFERENCE.md](references/REFERENCE.md) — GitLab API details, position object structure, line indexing
- [references/DRAFTS.md](references/DRAFTS.md) — Draft review workflow using the `note` CLI (batch comments, publish control)
