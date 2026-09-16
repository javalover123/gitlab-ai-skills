---
name: iteratotron
description: "Drives a project through any stage of the implementation lifecycle — from documentation (or none) through partial implementation to verifiable completion. Wraps the iterate and bug-burndown skills via bounded parallel subagent dispatch in isolated git worktrees, with a Constitution Check, a per-language harness vector (unit/coverage/mutation, integration/contract, chaos/DST), adversarial completion review, a stop-bias-pattern catalogue, and an attestable done predicate. Auto-detects whether a project needs greenfield bootstrap, partial-implementation completion, or a completion-readiness sweep. Use for drive this to completion, no stubs no TODOs, ship-ready burndown, project genesis, doc-to-impl, spec-driven development, constitution check, burn down the gaps, or build the implementation harness."
version: 1.0.1
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# iteratotron

Drive a project to verifiable completion, whatever stage it's at. iteratotron is
the top orchestrator: it discovers scopes, audits gaps per scope, and dispatches
bounded-parallel subagents — `iterate` for feature/quality gaps, `bug-burndown`
for defects — each in its own git worktree, then gates the result behind an
adversarial completion review and a done predicate.

## When to use

Use it to take a project from any starting point to done: greenfield bootstrap
("project genesis", doc-to-impl), completing a partial implementation ("no stubs,
no TODOs", "burn down the gaps"), or a completion-readiness sweep of a
nominally-finished project. For a single scope with docs already in place,
`iterate` alone is lighter; for defect batches, `bug-burndown` alone.

## Modes

Auto-detected at Phase 1: **genesis** (little or no implementation — bootstrap
docs, then build), **completion** (partial implementation — finish it), and
**sweep** (looks done — verify and close residual gaps). Mode sets the default
parallelism and budget.

## Relationships

- **`iterate`** — dispatched per scope to close feature/correctness/quality/
  coverage gaps.
- **`bug-burndown`** — dispatched to triage and fix defect batches.
- **`harness-builder`** — supplies the per-language harness vector (the
  verification tiers) iteratotron runs work through when present.
- **`human-review`** — receives items iteratotron parks as needing a human
  decision.

## Completion loop

The skill ships a `hooks.json` with a `Stop` checker
(`scripts/check-completion.py`) that blocks the stop while any scope has
non-terminal work and the budget holds. Under the repository's skill-hooks
plugin this drives the loop; without it, re-run until it approves. The
genesis-mode **done predicate** is a separate, stricter gate
(`scripts/done-check.py`, see [references/done-predicate.md](references/done-predicate.md)).

## Autonomy contract

The user wants end-to-end completion in a single turn. Don't pause between phases
or ask procedural check-ins; dispatch automatically once a plan exists. The only
valid pauses are a dirty working tree, a genuine design ambiguity (park it for
`human-review`), or a circuit-breaker firing. Don't surface tool-call cost as
friction — budget caps (`--max-budget-usd` per subagent and a global `budget:$N`)
are the safeguard, not hesitation.

## The 8-phase pipeline

1. **Setup + bootstrap** — session identity, baseline snapshot, mode detection,
   harness-vector composition, and (genesis) idempotent doc bootstrap via
   `all-aboard`. Verify `iterate`, `bug-burndown`, and capabilities.
2. **Scope discovery** — decompose the project into independently-buildable
   scopes ([references/scope-discovery.md](references/scope-discovery.md)).
3. **Gap audit (per scope)** — documentation-readiness gate, the four-kind gap
   inventory, the twelve-family stop-bias scan
   ([references/stop-bias-patterns.md](references/stop-bias-patterns.md)), and an
   iteration-log forensic read.
4. **Dedupe** — within-session, cross-session recurrence, and a cross-scope
   dependency graph.
5. **Prioritise + plan** — order scopes by severity and dependency, assign
   modes.
6. **Orchestrate** — bounded-parallel dispatch of `iterate`/`bug-burndown`
   subagents in isolated worktrees
   ([references/orchestration.md](references/orchestration.md),
   [references/streaming-orchestration.md](references/streaming-orchestration.md)).
7. **Adversarial completion review** — a hostile pass that tries to prove a
   scope *isn't* done
   ([references/adversarial-completion-reviewer.md](references/adversarial-completion-reviewer.md)).
8. **Consolidate + done predicate** — report, completion log, resumable queue,
   the genesis done predicate with SLSA attestation, and handing parked items to
   `human-review`.

## Constitution Check and harness vector

Before dispatch, a **Constitution Check** confirms the project's non-negotiables
are encoded as gates (see [references/constitution-check.md](references/constitution-check.md)).
The **harness vector** is the per-language set of verification tiers — Tier 1
unit/coverage/mutation, Tier 2 integration/contract, Tier 3 chaos/DST/multi-VM —
that each subagent's work is verified against; composition and Tier-3 triggers
are in [references/harness-vector.md](references/harness-vector.md) and
[references/tier3-triggers.md](references/tier3-triggers.md).

## Standing rules

Every subagent runs in an isolated worktree; never dispatch two writers to the
same worktree. Keep the completion log and queue as the sources of truth so a
run is resumable ([references/completion-log.md](references/completion-log.md),
[references/state-schema.md](references/state-schema.md)). Never weaken a gate to
make a scope pass. Park genuine design questions for `human-review` rather than
guessing. Forbidden phrases (delete then dispatch): cost-and-control hedges,
"good stopping point", numbered-iteration ordinals, "deferred" as a stop.

## References

- [references/architecture.md](references/architecture.md) — the orchestrator design
- [references/orchestration.md](references/orchestration.md) / [streaming-orchestration.md](references/streaming-orchestration.md) — dispatch mechanics
- [references/scope-discovery.md](references/scope-discovery.md) — decomposing into scopes
- [references/constitution-check.md](references/constitution-check.md) — non-negotiable gates
- [references/harness-vector.md](references/harness-vector.md) / [tier3-triggers.md](references/tier3-triggers.md) — verification tiers
- [references/stop-bias-patterns.md](references/stop-bias-patterns.md) — the twelve stop-bias families
- [references/adversarial-completion-reviewer.md](references/adversarial-completion-reviewer.md) — the hostile completion pass
- [references/done-predicate.md](references/done-predicate.md) — the genesis done gate
- [references/completion-log.md](references/completion-log.md) / [state-schema.md](references/state-schema.md) — resumable state
- [references/worked-example.md](references/worked-example.md) — a full run
- `scripts/check-completion.py` (Stop gate), `scripts/done-check.py` (done predicate)
