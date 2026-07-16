# Worked example — representative iteratotron session

This walks through a 4-hour completion-readiness burndown on a Rust workspace
called "ExampleApp". It's illustrative — your session won't match exactly, but the
phase structure and reporting format should.

## Trigger

User: "Run iteratotron on ExampleApp. I think the orchestrator crates are mostly
done but the agent crates have a lot of stubs and some hallucinated impls from
a long Claude session last week. 4-hour budget, parallelism 3, focus on
hallucinated-stubs and partial implementations."

## Phase 1 — Setup

Session `.iteratotron/20260516-152217-bf2a/` created. Baseline
`9c1d2e0a`. Integration branch `main`. Working tree clean. Prior completion
log has 23 records. `iterate` skill v1.0.0 verified at `~/.claude/skills/iterate/`.

`PHASE 1: COMPLETE — 23 prior records loaded, iterate v1.0.0 verified`

## Phase 2 — Scope discovery

- Cargo workspace enumerated: 22 crates
- 4 feature-area scopes (each spanning multiple crates per story)
- 2 active feature branches with uncommitted work — flagged for user decision,
  not auto-queued
- 3 crates filtered out as recently-complete: marked `complete` within the
  last 7 days, no new commits, no new stop-bias patterns
  (`orchestrator-types`, `example-rpc`, `example-zmq`)
- 19 scopes audit-eligible

`PHASE 2: COMPLETE — 19 scopes audit-eligible (3 filtered, 2 deferred)`

## Phase 3 — Gap audit

134 total gaps across 19 scopes:

- 14 P0, 38 P1, 51 P2, 31 P3 (per iterate's taxonomy)

47 stop-bias-pattern findings (matching user focus):

- 18 stubs (`Ok(vec![])`, `Err(NotImplemented)` patterns)
- 9 placeholders (`todo!()`, `unimplemented!()`)
- 7 partials (spec FR rows marked `Partial`)
- 6 disabled tests (`#[ignore]` macros)
- 5 orphan scaffolding (`#[allow(dead_code)]` on whole modules)
- 2 hallucination tells (`agent_kind: "User"` literal in tests; a
  `dispatch_to_agent` impl that just `println!`s and returns Ok)

**8 severity-lifted findings**: spec FRs marked `Implemented` whose code is a
stub. All lifted to P0 — the user-flagged scenario.

`PHASE 3: COMPLETE — 134 gaps, 47 stop-bias, 8 lifted to P0`

## Phase 4 — Dedupe

- 134 raw gaps → 89 deduped (cross-scope collapse)
- 6 findings tagged `recurring: true` from prior log match
  - 2 are P0 regressions of previously-completed scopes
  - 4 are scope-recurrence (blocked scopes still blocked for the same reasons)

`PHASE 4: COMPLETE — 134 → 89 queued, 6 recurring`

## Phase 5 — Prioritise

Top of queue: `agent-compiler-crate` — 4 severity-lifted findings (spec FRs
claim Implemented but two are stubs). Top-10 surfaced in `report.md`.

No `needs_all_aboard` scopes — all 19 already have spec/ADR/threat-model.

`PHASE 5: COMPLETE — 89 entries ordered, top-10 in report`

## Phase 6 — Orchestrate (4 hours, parallelism 3)

**Iteration 1**: dispatched top-3 — `agent-compiler-crate`, `agent-graph-crate`,
`agent-shell-crate`.

- `agent-graph-crate` returned stop-hook-passed in 47 min; Phase 7 found one
  subtle hallucination (a doc comment claiming retry-on-failure but the impl
  had no retry). Returned INSUFFICIENT.
- Loop continued through 14 more scopes.

Session totals after 4 hours:

- 11 scopes verified complete via Phase 7 (merges to `main`)
- 3 scopes blocked (worktrees retained for human review)
- 1 scope `needs_human` (spec contradicts ADR; user must adjudicate)
- 4 scopes remaining → `resumable_queue.jsonl`

`PHASE 6: PARTIAL — 11 complete, 4 remaining, time budget exhausted`

## Phase 7 — Adversarial review

Ran 17 times in total across attempts. APPROVED 11, INSUFFICIENT 4 (returned
to queue with lessons), NEEDS_HUMAN 2.

## Phase 8 — Consolidate

Chat summary delivered. `report.md` finalised. 11 new entries in
`.iteratotron/completion-log/`. All 8 severity-lifted findings resolved — the
hallucinated impls were caught, 2 cases required new ADRs that the
subagents created via `/adr-create` in-loop.

Recommended next session: investigate the 3 blocked scopes (likely share an
upstream dependency in `example-types` that needs design input), then re-run
iteratotron for resumption. Also recommend running `bug-burndown` — 4 of the
iterate subagents surfaced flaky tests as side effects (those are defects,
not completion gaps).

`PHASE 8: COMPLETE — 11 completion-log entries, resumable queue ready`

The user receives a clear picture: 11 scopes brought to verified completion
(each with stop-hook AND adversarial-review approval), 8
documentation-lies-about-reality caught and fixed, a clean resumable queue
for next session, and a flagged set of defects worth handing to
`bug-burndown`.
