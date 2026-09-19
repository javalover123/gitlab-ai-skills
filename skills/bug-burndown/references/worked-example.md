# Worked example — representative burndown session

This walks through a complete 3-hour burndown on a Rust project called
"ExampleApp". It's illustrative, not prescriptive — your session won't match
exactly, but the structure and reporting format should.

## Trigger

User: "Burn down the bugs in ExampleApp. Run the full test suite, parse last
week's CI logs, and review the codebase for drift from the spec. Time
budget 3 hours, parallelism 3."

## Phase 1 — Setup

Session dir `.bug-burndown/20260516-141503-7a3f/` created.
Baseline `7d8c2a1e`. Integration branch `main`. Working tree clean.
Prior bugfix log has 47 entries.

`PHASE 1: COMPLETE — 6 sources enabled, 47 prior records loaded`

## Phase 2 — Collect

- **logs**: 134 raw error events from CI artifacts (`./ci-logs/*.json`).
- **tests**: 23 failures from `cargo nextest run --message-format libtest-json`.
- **live harness**: ran `cargo test --features fuzz` for 20 minutes → 3 new failures.
- **issues**: 8 open bugs via GitLab MCP (upstream detected as `gitlab.com/example/exampleapp`).
- **code review**: 11 candidate sites matching patterns from prior bugfix-log entries tagged `recurring-pattern`.
- **spec drift**: 4 codepaths contradict ADR-0042, ADR-0058, and `THREATMODEL.md` §3.2.

Total raw findings: 183.

`PHASE 2: COMPLETE — 183 raw findings across 6 sources`

## Phase 3 — Classify

- 6 critical (4 panics, 1 data-loss, 1 security-relevant)
- 31 high (18 incorrect behaviour, 9 recurring patterns, 4 spec drift)
- 87 medium
- 59 low (mostly flakes)

`PHASE 3: COMPLETE — 183 findings classified`

## Phase 4 — Deduplicate

- 183 raw → 94 after structural fingerprint match
- 94 → 71 after embedding similarity match (within-session)
- 12 of the 71 tagged `recurring: true` from prior log match (including one **regression of fix from session 20260328-091422-c1d4**, escalated to critical)

`PHASE 4: COMPLETE — 183 raw → 71 deduped queue entries`

## Phase 5 — Prioritise

Top of queue: the critical regression (severity: critical, blast_radius: 14
callers, blocks 3 others). Top-20 surfaced in `report.md`.

`PHASE 5: COMPLETE — 71 entries ordered, top-20 in report`

## Phase 6 — Dispatch (3 hours, parallelism 3)

**Iteration 1**: dispatched BUG-0001, BUG-0002, BUG-0003 in worktrees.

- BUG-0002 (panic in `dispatch::handle_disconnect`) returned APPROVED in
  14 minutes; merged. The root cause was a missing requeue on disconnect,
  contradicting ADR-0042. Fix: 23 LOC in `dispatcher.rs`.
- BUG-0001 (the regression) returned APPROVED in 23 minutes; merged. The
  prior fix's bugfix-log entry was included in the subagent's prompt — it
  identified that the regression-causing commit reintroduced the unsafe
  pattern the original fix had removed.
- BUG-0003 returned BLOCKED after 42 minutes (mutation testing exposed a
  deeper invariant violation; needs human design input).

Loop continued with BUG-0004, BUG-0005, and so on.

Session totals after 3 hours:
- 28 bugs fixed (28 merges to `main`)
- 5 blocked (worktrees retained for human review)
- 3 introduced_regression (reverted; re-queued with escalated severity)
- 35 remaining → `resumable_queue.jsonl`

`PHASE 6: PARTIAL — 28 fixed, 35 remaining, time budget exhausted`

## Phase 7 — Reconcile (continuous)

Two regressions detected after merge and reverted. Each was re-queued as
a new finding with `caused_by:` annotation and severity escalated to high.
The third regression was caught before merge by the blast-radius test re-run.

`PHASE 7: COMPLETE alongside Phase 6`

## Phase 8 — Report

**Chat summary** (excerpt):

> 28 bugs fixed with full DoD coverage; 5 blocked needing human design
> input; 12 recurring patterns surfaced (one confirmed regression of
> session 20260328); 35 bugs in resumable queue. Recommended next session:
> investigate BUG-0003 and its 4 siblings — they share pattern_id
> `agent-link-lifecycle-invariant` suggesting a missing invariant in the
> agent-link teardown path.

Report file: `.bug-burndown/20260516-141503-7a3f/report.md`
Resumable queue: `.bug-burndown/20260516-141503-7a3f/resumable_queue.jsonl`

`PHASE 8: COMPLETE — 28 bugfix-log entries written, resumable queue ready`
