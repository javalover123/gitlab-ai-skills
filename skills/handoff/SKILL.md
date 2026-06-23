---
name: handoff
description: "Compact the current session into a handoff document so a fresh agent can continue the work. Use when the user says hand off, wrap up, save context, continue later, pick this up in a new session, running low on context, or context is getting long."
version: 0.2.0
license: MIT
category: Productivity
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# handoff

Write a handoff document that lets a fresh agent continue the current work.
Anchor to durable artifacts instead of freezing stale state inline.

## When to use

- User asks to hand off, wrap up, save context, or continue in a new session.
- Context window is getting long and the user wants to checkpoint.
- Switching between agents or tools mid-task.

## Current context (DCI)

!`git rev-parse --abbrev-ref HEAD 2>/dev/null && git log --oneline -3 2>/dev/null || echo "(not in a git repo)"`

## Principles

**Anchor to GitLab artifacts.** Link issues, MRs, branches, and commits by URL.
For anything whose state changes (pipeline, approvals, open threads), give `glab`
commands the next agent can run instead of pasting a snapshot:

```
glab mr view <iid> -R <project>
glab ci status -R <project> --branch <branch>
```

**Reference, don't duplicate.** Issue descriptions, commit messages, PRDs, diffs,
and plans are already persisted — link by URL or path, don't repeat them.

**Redact secrets.** Strip API keys, tokens, passwords, and PII. Replace with
`[REDACTED]`.

**Shape to the task.** A good handoff usually covers: the goal, what's done,
what's next, open questions, key files, and suggested skills — but include only
what's relevant. A two-line bugfix doesn't need nine sections. See
[assets/handoff-template.md](assets/handoff-template.md) for an example to adapt.

**Save location.** Default to `./tmp/handoff.md` (project-local, typically
gitignored). Use a more specific name if multiple handoffs could collide, or
save wherever the user asks. Tell the user the path so they can load it in the
next session.
