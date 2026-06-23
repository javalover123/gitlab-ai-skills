---
name: handoff
description: "Compact the current session into a handoff document so a fresh agent can continue the work. Use when the user says hand off, wrap up, save context, continue later, pick this up in a new session, running low on context, or context is getting long."
version: 0.5.0
license: MIT
category: Agent Tooling
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# handoff

Write a handoff document that lets a fresh agent continue the current work.
Anchor to durable artifacts instead of freezing stale state inline.

## Principles

**Anchor to GitLab artifacts.** Link issues, MRs, branches, and commits by URL.
For anything whose state changes (pipeline, approvals, open threads), include a
command the next agent can run to re-fetch current state rather than pasting a
snapshot.

**Reference, don't duplicate.** Issue descriptions, commit messages, PRDs, diffs,
and plans are already persisted - link by URL or path, don't repeat them.

**Redact secrets.** Never reproduce a secret in the handoff, even when warning
about it. Replace every API key, token, password, and PII occurrence with
`[REDACTED]` - do not quote, echo, or reference the original value.

**Gather current state at write time.** Run `git rev-parse --abbrev-ref HEAD`,
`git log --oneline -5`, `git status`, and any relevant `glab` commands while
writing the handoff to capture accurate repo state.

**Shape to the task.** A good handoff usually covers: the goal, what's done,
what's next, open questions, key files, and suggested skills - include what's
relevant, skip what isn't. See
[assets/handoff-template.md](assets/handoff-template.md) for an example to adapt.

**Save location.** Save to `./tmp/handoff-<slug>.md` where `<slug>` is a short
date or topic identifier (e.g. `handoff-YYYY-MM-DD.md`, `handoff-search-reindex.md`).
Before writing, verify `./tmp/` is gitignored (check `.gitignore`); if it is not,
create and gitignore it, or fall back to a temp file (`mktemp /tmp/handoff-XXXXXX.md`).
Honor an explicit path if the user provides one. Tell the user the saved path so
they can load it in the next session.

## Attribution

Based on the [handoff](https://github.com/mattpocock/skills/tree/main/skills/productivity/handoff)
skill by [Matt Pocock](https://github.com/mattpocock), Copyright (c) Matt Pocock,
MIT License.
