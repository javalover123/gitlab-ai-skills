---
name: human-review
description: "Interactively resolves items that iteratotron and bug-burndown have escalated to needs_human or requires_human_review status. Reads the active session queues, reconstructs each item's context from linked specs/ADRs/threat-model entries plus the current gap analysis, drafts 2-4 candidate resolutions consistent with the in-flight scope, and runs an interview per item. Records each decision and re-queues actionable items so the parent skill re-engages. Scans all sessions by default, including the bug-burndown sessions a harness-builder runtime harness spawns per iteration. Use when iteratotron or bug-burndown has parked items for human input, when a harness loop won't converge because of parked needs_human items, or to clear the human review queue between sessions."
version: 1.0.0
license: MIT
category: Agent Tooling
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# human-review

Drain the items `iteratotron` and `bug-burndown` park as `needs_human` /
`requires_human_review`. For each, reconstruct the context, draft informed
options consistent with the in-flight scope, ask the user to decide, record the
decision, and re-queue actionable items so the parent skill's loop resumes.

## When to use

- A `bug-burndown` or `iteratotron` run finished with `needs_human` items > 0.
- Before a `resume:<id>` run, to clear human-input blockers first.
- A `harness-builder` runtime loop won't converge because its burndown bridge
  parked items in the per-iteration sessions it spawned — drain those to unblock
  the fixpoint.
- The `human_review_queue.md` artifact accumulated items across sessions.
- Auditing prior `needs_human` decisions for consistency with current scope.

## Arguments and defaults

`[session:<id>] [skill:iteratotron|bug-burndown|both] [scope:all|current|harness]
[include-blocked:yes|no]`

**Scan every session by default** (`scope:all`), not just `CURRENT` — a harness
loop parks items in the session *it* spawned, never in `.bug-burndown/CURRENT`, so
a CURRENT-only scan reports "nothing to review" while parked items quietly block
the fixpoint. `needs_human` and `requires_human_review` are included; `blocked` is
excluded unless `include-blocked:yes`; already-decided sessions are skipped unless
`include-decided:yes`. Narrow with `scope:current` or `session:<id>` only when you
mean to.

## Live context (auto-injected at load)

- Active iteratotron session: !`cat .iteratotron/CURRENT 2>/dev/null || echo "none"`
- Active bug-burndown session: !`cat .bug-burndown/CURRENT 2>/dev/null || echo "none"`
- Bug-burndown sessions total: !`ls -1d .bug-burndown/*/ 2>/dev/null | wc -l | tr -d ' '`
- Harness-origin sessions: !`grep -rlE 'origin:[[:space:]]*[a-z0-9-]+-harness' .bug-burndown/*/manifest.yaml 2>/dev/null | wc -l | tr -d ' '`
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || echo "not a git repo"`

## The six phases

### 1 — Discover

Enumerate sessions (all by default) with `scripts/collect-human-items.py
--all-sessions`, which walks every `.iteratotron/<id>/` and `.bug-burndown/<id>/`
directory — including the per-iteration bug-burndown sessions a harness spawns
(one per `.harness/iter-NNN/` capture). Each parked item carries its session,
`needs_human_dir`, `origin` (e.g. `<toolname>-harness`), and linked artifacts.
The session sources and harness layout are in
[references/queue-mutation.md](references/queue-mutation.md).

**When items span more than one session or origin, ask the user how to scope the
drain before interviewing** — that's the ambiguity gate. Don't silently
interview a hundred items from ten sessions.

### 2 — Contextualise

Per item, load the linked spec/ADR/threat-model entries and the current gap
inventory so the options you draft reflect what's actually in flight, not a stale
snapshot.

### 3 — Research

Draft **2–4 candidate resolutions** per item, ranked by consistency with the
in-flight scope, the recommended one first. Options must be mutually exclusive
and each genuinely actionable. Deepen with a research subagent for a hard call.
Option-drafting rules: [references/decision-research.md](references/decision-research.md).

### 4 — Interview

Present each item **one at a time** via the `question` tool (opencode) /
`AskUserQuestion` (Claude Code), recommended option first, each option's
`description` stating its consequence and the `preview` showing what will change.
Pacing and question construction: [references/interview-patterns.md](references/interview-patterns.md).

### 5 — Persist

Write a decision record (linked artifacts, chosen option, next action) under the
item's `human_decisions/` dir, then mutate the queue status **atomically** with
`scripts/update-queue-status.py` — re-queue an actionable decision so the parent
picks it up, or mark it terminal. Update `human_review_queue.md` if present. The
atomic mutation contract is in
[references/queue-mutation.md](references/queue-mutation.md).

### 6 — Hand back

Return a status block the parent skill's Stop hook reads, so a re-queued item
re-engages the dispatcher. For a harness-origin session, the unblock path is the
harness's own loop — report the counts so the next iteration picks them up.

## Standing rules

Never invent a decision the user didn't make — every re-queued item traces to a
recorded decision. Never interview in bulk without the scope gate when items span
sessions. Keep decision records and queue mutations atomic so a crash mid-drain
is resumable.

## References

- [references/queue-mutation.md](references/queue-mutation.md) — session sources, harness layout, atomic status mutation
- [references/decision-research.md](references/decision-research.md) — option drafting and consistency rules
- [references/interview-patterns.md](references/interview-patterns.md) — question construction and pacing
- `scripts/collect-human-items.py` — enumerate parked items across sessions
- `scripts/update-queue-status.py` — atomic queue-status mutation
