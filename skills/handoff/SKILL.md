---
name: handoff
description: "Compact the current session into a handoff document so a fresh agent can continue the work. Use when the user says hand off, wrap up, save context, continue later, pick this up in a new session, running low on context, or context is getting long."
version: 0.1.0
license: MIT
category: Productivity
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# handoff

Summarize the current session's state into a structured handoff document that a
fresh agent can load to continue the work. Anchors to durable artifacts
(issues, MRs, branches, commits) instead of freezing stale state inline.

## When to use

- User asks to hand off, wrap up, save context, or continue in a new session.
- Context window is getting long and the user wants to checkpoint progress.
- Switching between agents or tools mid-task.

## When NOT to use

- The work is done and nothing needs continuing — close the issue instead.
- The user wants a summary for humans (meeting notes, status update) — just
  write one directly; no skill needed.

## Current context (DCI)

!`git rev-parse --abbrev-ref HEAD 2>/dev/null && git log --oneline -3 2>/dev/null || echo "(not in a git repo)"`

## Procedure

1. **Gather state.** Identify the goal, what's done, what's next, and any open
   questions. Scan for GitLab artifacts (issue/MR URLs, branch names, pipeline
   status) mentioned or used in this session.

2. **Write the handoff** using the template in
   [assets/handoff-template.md](assets/handoff-template.md). Fill every section;
   leave a section empty with "N/A" only if genuinely inapplicable.

3. **Reference, don't duplicate.** For anything already captured in an issue,
   MR description, commit message, or file — link to it by URL or path. Include
   `glab` commands the next agent can run to re-fetch live state:
   ```
   glab mr view <iid> -R <project>
   glab ci status -R <project> --branch <branch>
   ```

4. **Redact secrets.** Strip API keys, tokens, passwords, and PII before
   writing. Replace with `[REDACTED]`.

5. **Save the file** to `./tmp/handoff-YYYY-MM-DD.md` (the project's gitignored
   scratch directory). If `./tmp/` doesn't exist, create it. Tell the user the
   path and suggest how to resume:
   ```
   Load this handoff: read ./tmp/handoff-YYYY-MM-DD.md
   ```

6. **Tailor for the next session.** If the user says what the next session will
   focus on, emphasize the relevant next steps and suggest skills to load.

## Rules

- **No stale state inline** — pipeline results, MR approval status, and CI
  output change constantly. Give `glab` commands to fetch current state.
- **Don't duplicate artifacts** — issue descriptions, PRDs, ADRs, plans, diffs,
  and commit messages are already persisted. Reference by URL/path.
- **Keep it scannable** — the next agent should orient in under 30 seconds.
- **Always suggest skills** — list skills the next session should load.
- **One file** — everything in a single handoff document, not scattered notes.
