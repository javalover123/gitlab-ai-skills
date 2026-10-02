# Worked example — a full nine-phase walk-through

This shows what the bugfix skill looks like end-to-end on a representative
distributed-systems bug. Names and stack details are generic; substitute
your own. The point's the shape of the evidence, not the specific
technology.

## The report

> "Our dispatcher sometimes loses task results when a worker restarts
> mid-run. Logs show `task_dispatched` then `worker_disconnect` and the
> result never appears in the database. Reproducer's flaky on my laptop."

## Phase 1 — Intake

```
## Bug statement

- **Expected**: every dispatched task ends in either `task_completed` or
  `task_failed`, persisted to the database within the configured timeout.
- **Observed**: `task_dispatched` then `worker_disconnect`, no terminal
  event, no row in the database.
- **Environment**: rustc 1.87, NixOS unstable, dispatcher@HEAD~3, default
  config.
- **Smallest triggering input**: any task whose worker SIGKILLs during
  execution.
- **Regressed signal**: Errors (silent loss; RED's Errors and SRE Golden
  Signals).
```

`GATE 1: PASS — evidence: bug statement block above`

## Phase 2 — Context

- **Code**: `crates/dispatcher/src/handler.rs::handle_disconnect` doesn't
  requeue or fail in-flight tasks. Read end-to-end.
- **Logs**: spans show `dispatch.span_id=X` → `worker_link.span_id=Y`
  (child) drops without a `worker_link::close` event ⇒ cleanup absent.
- **Docs**: `docs/decisions/0042-worker-lifecycle.md` says "on disconnect,
  the dispatcher MUST move in-flight tasks to `pending` or `failed`."
  → **ADR says X, code does Y → code defect, ADR-aligned authoritative.**

```
CONTEXT CHECK:
- Code path read end-to-end?   yes — handler.rs, worker_link.rs
- Relevant logs / traces seen? yes — spans abc123 across dispatcher
- Spec / ADR / TM / AC located? yes — ADR-0042
- Desired behaviour unambiguous? yes
```

`GATE 2: PASS — evidence: CONTEXT CHECK above`

## Phase 3 — Reproducer

L2 component test `handler::tests::disconnect_requeues_inflight`: spin up
an in-memory worker fake, dispatch a task, kill the fake mid-run, assert
task transitions to `failed` AND a `task_failed` row exists in the
in-memory database within 200ms. Fails red with `assertion failed: row
not found`. **Confirmed fails for the right reason** — wrong post-state,
not a setup error.

Also add an L4 stateful proptest: arbitrary dispatch / disconnect
sequences; invariant: at end, every dispatched task has a terminal row.

```
## Reproducer

- File: crates/dispatcher/src/handler.rs (tests module)
- Test: disconnect_requeues_inflight
- Command: cargo test --package dispatcher disconnect_requeues_inflight
- Initial output:
    thread 'handler::tests::disconnect_requeues_inflight' panicked at
    'assertion failed: row.is_some()'
```

`GATE 3: PASS — evidence: red on broken tree, wrong post-state pinned`

## Phase 4 — Causal analysis

```
## Causal discrepancy

Desired:     ADR-0042 wording — disconnect requeues or fails in-flight tasks.
Documented:  ADR-0042:lines 12-18, same.
Implemented: handler.rs:142 — silent drop on disconnect.
Classification: code-defect.
Authoritative source: ADR-0042.
```

**Hypotheses:**

- **H1**: `handle_disconnect` missing requeue branch.
  - Confirming: no requeue call in source. Found.
  - Disconfirming: searched for any other path that marks tasks failed.
    Not found.
  - **Verdict**: surviving.
- **H2**: requeue exists but uses wrong worker key.
  - Disconfirming: read `dispatch_table` indexing; the key matches.
    Falsified.
- **H3**: database write fails silently.
  - Disconfirming: added a tracing event, observed no attempted write.
    Falsified.
- **H4**: a separate cleanup task races with `handle_disconnect` and
  removes the in-flight rows before they can be marked failed.
  - Disconfirming: there's no cleanup task; the only writer to the
    inflight table's the handler itself. Falsified.

Surviving: H1. Explains both the missing row and the missing terminal
event.

**Rubber-duck trace:** in `handle_disconnect`, line 142 removes the
worker from the registry; line 143 returns Ok. Expected: iterate
`inflight[worker]`, mark each task failed, persist. Reality: no
iteration. **Divergence line: handler.rs:142.**

`GATE 4: PASS — evidence: three-way diff + 3 hypotheses + rubber-duck`

## Phase 5 — Structural fix

- **Layer check**: originating = dispatcher; patch = dispatcher. ✓
- **Structural audit**:
  1. Signature change — Y, `handle_disconnect` now returns
     `Vec<TaskId>` of failed tasks.
  2. Deletes special case — N.
  3. Adds broad catch — N.
  4. Perturbation still triggers — N (proptest covers).
  5. Makes bad state unrepresentable — partial (new `Inflight<T>` newtype).
  6. Property test — Y.
  7. Commit msg names invariant — Y.
  8. Special-case for reported input — N.
  Score: 5 structural Y, 0 cosmetic.
- **Blast radius**: `handler.rs`, `inflight.rs` (new), `tests/`.
  ADR-0042 unchanged (code now matches it; no new ADR needed).
- **Siblings**: searched for other `worker_disconnect` handlers — found
  one in `bin/cli/src/admin.rs` that already requeues; consistent.

`GATE 5: PASS — evidence: audit + blast radius + sibling sweep`

## Phase 6 — Verification

- **Reproducer**: green; revert → red with original assertion;
  re-applied. ✓
- **L1 / L2**: `cargo nextest run` — 348 pass, 0 fail.
- **L3**: BDD harness — scenario "worker disconnect mid-task" passes.
- **L4**: `cargo test --features proptest -- proptest` — 1000 cases
  pass.
- **Mutation**: `cargo mutants --in-diff <(git diff HEAD)` — 0 survivors
  after adding two more assertions to the L2 test.
- **Lint / fmt / build**: clean.

`GATE 6: PASS — evidence: command outputs above`

## Phase 7 — Doc deltas (delegated)

- **ADR triggers**: 1 Y (contract change: `handle_disconnect` signature)
  → below threshold for new ADR, but ADR-0042 covers this decision and
  the code now matches it. Invoked `/adr-review` with the three-way diff
  and Phase 5 summary. Result: ADR-0042 Confirmation section updated to
  link the new tests
  (`docs/decisions/0042-worker-lifecycle.md`).
- **Spec / AC**: invoked `/spec-create` (new Gherkin scenario) — produced
  `features/dispatcher/worker_lifecycle.feature` addition: Scenario
  "worker disconnect mid-task requeues in-flight work."
- **Threat model**: trust boundary unchanged, no new external input, no
  dep change — **N to all triggers**, recorded. No companion skill
  invoked.
- **User story**: AC for `STORY-187 Worker resilience` already covered
  this. Invoked `/story-reviewer` to confirm the new test link satisfies
  the existing AC — confirmed, no story change needed.

`GATE 7: PASS — evidence: artefact paths returned by companion skills`

## Phase 8 — Adversarial review

Delegated to `adversarial-reviewer` subagent.

- **8a Invariant**: every dispatched task ends in a terminal database
  row.
- **8b Attack scenarios**: empty inflight (handled), 1000 in-flight
  (proptest bound raised), disconnect during requeue itself (NEW failing
  test added → fix Phase 5 again to make requeue idempotent), unicode
  worker ID (irrelevant), simultaneous disconnect of all workers (added
  L3 test), clock-jump during requeue timeout (added bounded-clock
  fixture).
- **8c Untested input**: disconnect during database outage. Result:
  requeue succeeds in-memory but persist fails — added
  retry-on-persist-failure with bounded backoff; new test.
- **8d Symptom-fix audit**: all N.
- **8f Falsifying test**: "kill dispatcher between requeue and persist"
  — added; introduces a new architecturally-significant decision
  (dispatcher crash-recovery scans `inflight` table on startup). **New
  ADR required** — return to Phase 7, invoke `/adr-create` with the
  falsifying-test context; `/adr-create` returns
  `docs/decisions/0061-dispatcher-crash-recovery.md`. Re-run gates with
  the new ADR linked.
- **Verdict (after second pass)**: APPROVED.

`GATE 8: PASS — evidence: subagent transcript + ADR-0061 path`

## Phase 9 — Definition of Done

All boxes ticked with cited evidence. Final commit graph: one fix
commit, one ADR-0061 commit (new), one spec commit (Gherkin scenario),
one test-only commit (mutation-survivor kill).

```
## Definition of Done

- [x] Bug statement recorded.                Evidence: Phase 1 block
- [x] Context-sufficiency check completed.   Evidence: Phase 2 paths
- [x] Reproducer test added.                 Evidence: handler::tests::disconnect_requeues_inflight
- [x] Causal-discrepancy doc emitted.        Evidence: Phase 4 block
- [x] ≥3 hypotheses enumerated.              Evidence: Phase 4 hypotheses
- [x] Rubber-duck trace.                     Evidence: handler.rs:142
- [x] Structural fix at originating layer.   Evidence: Phase 5 audit
- [x] Blast radius respected.                Evidence: 2 files + tests
- [x] Every applicable test layer green.     Evidence: nextest, BDD, proptest outputs
- [x] Mutation testing: 0 survivors.         Evidence: cargo mutants output
- [x] Lint / format / build clean.           Evidence: clippy + fmt output
- [x] ADR delta filed.                       Evidence: docs/decisions/0042 + 0061
- [x] Spec / AC delta filed.                 Evidence: features/dispatcher/worker_lifecycle.feature
- [x] Threat-model delta filed.              Evidence: N/A — recorded
- [x] User-story delta filed.                Evidence: STORY-187 (no change needed)
- [x] Adversarial review APPROVED.           Evidence: subagent transcript
- [x] Final-message hygiene.                 Evidence: below

## Evidence
<test outputs and diffs above>

## Remaining Risks
- Crash-recovery scan on startup adds ~30ms to cold-start latency.
  Accepted; documented in ADR-0061.

## Not Tested
- Concurrent dispatcher crash AND worker disconnect (out of scope; covered
  by ADR-0061's recovery scan in principle but no explicit test).
```

`GATE 9: PASS — DoD complete`
