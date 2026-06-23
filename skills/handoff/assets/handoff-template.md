# Handoff

Example structure - adapt to the task; skip sections that don't apply.

**Saved to:** `<path>`
**Redaction check:** all secrets/tokens/PII replaced with `[REDACTED]`.

## Goal

What the user is trying to accomplish (one sentence).

## Artifacts

Links and commands to re-fetch live state:

| Artifact | Link / command |
|----------|---------------|
| Issue | URL |
| MR | URL or `glab mr view <iid> -R <project>` |
| Branch | `git fetch origin <branch> && git switch <branch>` |
| Pipeline | `glab ci status -R <project> --branch <branch>` |

## Done / Current state

What's been completed. Reference commits and MRs, not prose about code changes.

## Next steps

What the next agent should do, in rough priority order.

## Open questions

Decisions needing human input, or blockers.

## Key files

Paths the next agent will need (relative to repo root).

## Suggested skills

Skills the next session should load.
