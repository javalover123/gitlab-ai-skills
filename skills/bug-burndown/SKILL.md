---
name: bug-burndown
description: "Runs a continuous, autonomous bug burndown session — collecting defects from logs, tests, issue queues, and spec drift; deduplicating and triaging them through an 8-phase pipeline; then dispatching bounded parallel bugfix subagents in isolated worktrees until the queue is empty or the time budget runs out. Use when asked to burn down the bugs, clear the backlog, triage CI failures, find regressions, run a fix session, or anything that's batch quality-improvement rather than a single targeted bug fix."
version: 1.0.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# bug-burndown

Collect defects across the whole codebase, triage and deduplicate them, then
dispatch parallel `bugfix` subagents in isolated worktrees until the queue is
empty or the time budget runs out. This is the orchestrator layer over the
`bugfix` skill — it finds and schedules the work; each fix runs through
`bugfix`'s full rigor, which isn't cut for throughput.

## When to use

Use it for batch quality improvement: "burn down the bugs", "clear the
backlog", "triage the CI failures", "find regressions", "run a fix session".
For a single known defect, use `bugfix` directly.

## The 8-phase pipeline

Don't skip phases. Emit a status line after each:
`PHASE <n> (<name>): COMPLETE | PARTIAL | BLOCKED — <n found / new / queued / fixed>`.

1. **Setup** — session dir, baseline snapshot, dependency check.
2. **Collect** — fan out to each enabled source collector (logs, tests, issue
   trackers, spec/ADR/threat-model drift, test-effectiveness).
3. **Classify** — tag each finding with kind, severity, and signals.
4. **Deduplicate** — fingerprint + embedding match within the session and
   against the prior bug log.
5. **Prioritise** — sort by severity > blast radius > dependency graph > cost.
6. **Dispatch** — bounded parallel `bugfix` subagents, each in an isolated
   worktree.
7. **Reconcile** — collect results, update the queue, detect regressions.
8. **Report** — chat summary, update the queue file and the bug log.

Phase mechanics live in the references: collectors
([references/collectors.md](references/collectors.md)), classification and
severity ([references/triage-pipeline.md](references/triage-pipeline.md)),
recurrence detection
([references/recurrence-detection.md](references/recurrence-detection.md)), and
the dispatcher ([references/dispatcher.md](references/dispatcher.md)). A full run
is walked in [references/worked-example.md](references/worked-example.md).

## Autonomy contract — overrides default turn-taking

The user invoked this because they want autonomous, parallel, end-to-end triage
and fixing in a single turn. For the session's duration:

- **Don't pause for permission between phases.** Dispatch happens automatically
  once Phase 5 produces a queue. The only valid pauses are a dirty working tree
  at Phase 1, borderline dedup pairs whose merge would change queue rank, or a
  circuit-breaker firing.
- **Don't surface tool-call cost or duration as friction** — the user accepted
  that cost by invoking the skill; orchestration is your job, cost-accounting is
  theirs.
- **Parallelism is fan-out by default** (default N=3). Dropping to serial
  without a cited reason is a defect.
- **Ask only for genuine ambiguity**, never procedural check-ins. If you're
  about to write "let me check in before dispatching", that sentence is the bug
  — delete it and dispatch.

## Completion loop

The skill ships a `hooks.json` with a `Stop` checker
(`scripts/check-completion.py`). On each Stop it reads the active session's
`queue.jsonl` and **blocks** (`{"decision": "block", ...}`) while any bug is in
a non-terminal status (`queued`, `in_flight`, `re-evaluate`, `needs_rebase`) and
the time budget hasn't expired (an `introduced_regression` counts as
non-terminal — reconciliation reverts and re-queues it); it **approves** only
when every entry is terminal (`fixed`, `blocked`, `needs_human`, `skipped`,
`requires_human_review`) or the budget is exhausted.
Under the repository's skill-hooks plugin this drives the loop; the checker is
skipped in subagent context so a `bugfix` subagent's own stop isn't caught.
Without the plugin, re-run until the checker approves.

## Concurrency and the optional verification harness

Heavy-work concurrency (compile/test) is the throughput bottleneck. If the
project provides a **verification harness** — a wrapper that runs verification
commands through a tier-weighted slot semaphore and caches results — the
dispatcher routes heavy work through it and sizes parallelism from its
slot-status command. Without one, cap parallelism at 2 on hosts under ~16 GB RAM
and log `slot semaphore unavailable — capping parallelism at 2`. Raising N above
5 requires both an explicit `parallel:N` argument and a reported slot capacity of
at least `2 × N`. See [references/dispatcher.md](references/dispatcher.md).

## Harness-driven sessions

An external harness can pre-populate a session and drive it (e.g. spawning a
`resume:<id>` invocation). The contract is intentionally simple so any harness
in any language can implement it: set `manifest.origin: <toolname>-harness` in
the session manifest and `BUG_BURNDOWN_HARNESS_DRIVEN=1` in the spawned
subprocess. The Stop checker uses these to tell a harness-driven session apart
from a different session that merely finds a leftover session directory (which
it skips). The `harness-builder` skill's runtime mode is one implementation.

## Standing rules

Never make a suite green by weakening it (that's `bugfix`'s rule, and it holds
here). Keep the queue file and bug log the sources of truth so a session is
resumable. Escalate a bug the pipeline can't place to `human-review` rather than
guessing. Full standing rules and circuit-breaker conditions:
[references/dispatcher.md](references/dispatcher.md).

## References

- [references/collectors.md](references/collectors.md) — Phase 2 source collectors
- [references/triage-pipeline.md](references/triage-pipeline.md) — classification, severity, dedup
- [references/recurrence-detection.md](references/recurrence-detection.md) — cross-session recurrence
- [references/dispatcher.md](references/dispatcher.md) — Phase 6 dispatch, invariants, concurrency
- [references/worked-example.md](references/worked-example.md) — a full run
- `scripts/check-completion.py` — the Stop-hook completion oracle (see `hooks.json`)
