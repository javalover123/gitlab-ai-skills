---
name: gitlab-mr-comments
description: Use when creating, reading, replying to, or resolving comments on a GitLab merge request — diff-line notes, thread replies, general notes, and discussion resolution via glab mr note. Also covers batched draft reviews via the optional note CLI. Keywords - GitLab, merge request, MR, comments, notes, code review, diff, resolve, feedback, discussion.
version: 1.1.0
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

> **Full command reference:** All `glab mr note` commands, flags, code suggestions, draft reviews, and gotchas are documented in the `glab` skill's [`references/mr-review.md`](../glab/references/mr-review.md). This skill adds the MR-comments-specific publishing rules and AI prefix convention on top of that reference.

## Prerequisites

1. **[`glab`](https://gitlab.com/gitlab-org/cli)** — GitLab CLI v1.94.0+ (provides `glab mr note`)
   ```bash
   brew install glab
   glab auth login
   ```

2. **[`jq`](https://jqlang.github.io/jq/)** *(optional)* — only required for batched draft reviews via `glab api`. See [references/DRAFTS.md](references/DRAFTS.md).

## Publishing Rules

`glab mr note create` publishes comments **immediately** — there is no draft mode in `glab`. Follow these rules:

1. **Always confirm with the user before posting.** Show the exact comment text and target (thread, file:line, or general) before running any `glab mr note create` command.
2. **Replying to existing threads** → show the reply text, then use `glab mr note create --reply <id>`.
3. **New comments on diff lines** → show the comment text and target location, then use `glab mr note create --file --line`.
4. **General comments** → show the comment text, then use `glab mr note create`.

**Confirm before every write. Everything is published immediately.**

For draft reviews (batch comments that stay invisible until published), see [references/DRAFTS.md](references/DRAFTS.md) — uses `glab api` directly.

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

## Quick Reference

```bash
# List discussions
glab mr note list --state unresolved

# General comment (confirm with user first)
glab mr note create -m ":robot: AI-generated

<body>"

# Reply to a thread (confirm with user first)
glab mr note create --reply <discussion-id> -m ":robot: AI-generated

<body>"

# Diff comment (confirm with user first)
glab mr note create --file main.go --line 42 -m ":robot: AI-generated

<body>"

# Resolve / reopen a thread
glab mr note resolve <discussion-id>
glab mr note reopen  <discussion-id>
```

For the full reference — all flags, code suggestions, batched draft reviews, position objects, and gotchas — see the `glab` skill's [`references/mr-review.md`](../glab/references/mr-review.md).

## Agent Guidelines

1. **Always prefix `:robot: AI-generated\n\n`** — every outgoing comment, every time.
2. **Confirm before publishing** — `glab mr note create` is not a draft. Show the exact body and target first.
3. **Read before writing** — `glab mr note list --state unresolved` to see context before commenting.
4. **Prefer `--reply` over a new note** when continuing an existing thread; otherwise the conversation fragments.
5. **Use `--unique` on rerun-safe paths** — status comments, recurring summaries — to prevent duplicates.
6. **Heredoc-quote bodies with backticks** — `<< 'EOF'` (single-quoted) for any body containing `` ` ``, `$`, or `!`.
7. **For batched reviews, use `glab api .../draft_notes`** — see [references/DRAFTS.md](references/DRAFTS.md). Never run `bulk_publish` without the user's explicit request.

## References

- `glab mr note --help`, `glab mr note create --help`, `glab mr note list --help` for full CLI usage
- [`glab` skill — `references/mr-review.md`](../glab/references/mr-review.md) — Full MR comment reference (all flags, code suggestions, drafts/batch fallback, position objects, gotchas)
- [references/DRAFTS.md](references/DRAFTS.md) — Draft review workflow using `glab api` (batch comments, publish control)
