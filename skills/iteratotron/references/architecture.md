# Genesis architecture — orchestrator-workers wrapped in evaluator-optimizer

This reference is loaded on demand from the `iteratotron` skill
when you need the full architectural picture: bounded-parallelism math,
worktree state machine, recurrence detection, evaluator-optimizer loop.
It cites Anthropic's *Building Effective Agents* (Schluntz & Zhang,
December 2024) as the canonical taxonomy.

## The pattern, at a glance

Per Schluntz & Zhang, agentic systems decompose into five workflows:
prompt chaining, routing, parallelization (voting / sectioning),
orchestrator-workers, and evaluator-optimizer. Genesis is
**orchestrator-workers** (the outer loop dispatches and gathers)
**wrapped in evaluator-optimizer** (the harness escalation + adversarial
review loop re-runs workers until the evaluator passes).

```
                    ┌──────────────────────────────┐
                    │  /iteratotron (the orchestrator) │
                    │  • reads constitution.md     │
                    │  • reads spec/ADR/threat/    │
                    │    story tree                │
                    │  • computes gap analysis     │
                    │  • emits scope_queue +       │
                    │    bug_queue + harness_vec   │
                    └──────────────┬───────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                                                   ▼
┌──────────────────────────┐                       ┌──────────────────────────┐
│  iteratotron worker N=2  │  ←── alternate ──→    │  bug-burndown worker N=2 │
│  (claude -p stream-json, │                       │  (claude -p stream-json, │
│   per scope, own         │                       │   per finding, own       │
│   worktree)              │                       │   worktree)              │
└────────────┬─────────────┘                       └────────────┬─────────────┘
             │                                                  │
             └────────── streams events ───────────┬────────────┘
                                                   ▼
                                ┌────────────────────────────────┐
                                │  evaluator-optimizer:          │
                                │  • adversarial completion rev. │
                                │  • harness escalation gate     │
                                │  • drift / stop-bias detector  │
                                └─────────────┬──────────────────┘
                                              ▼
                                  (loop until done predicate)
```

The orchestrator is **deterministic** (a Python script's worth of
control flow). The workers are **streamed subprocesses** so iteratotron
can render progress, intervene, and abort cleanly. The
evaluator-optimizer is the **multi-tier harness + adversarial reviewer**
— neither is bypassable.

## Bounded parallelism math

Default: **N=2 outer × M=3 inner**. That's up to 6 concurrent Sonnet
contexts at peak (worst case: both outer iteratotron sessions are
dispatching their full M=3 inner iterate subagents simultaneously).

| Layer | Concurrent | Purpose | Memory budget per slot |
|---|---|---|---|
| Outer (iteratotron) | 2 | distinct top-level scopes | 2 GB RAM |
| Inner (iterate) | 3 per outer | distinct sub-scopes within a top-level scope | 1 GB RAM |
| Adversarial review | 1 per completed scope (sequential) | cold-context verification | 512 MB RAM |
| Bug-burndown | up to 2, alternating with outer | distinct findings | 1 GB RAM |

The incident.io engineering team's experience report ("How we're shipping
faster with Claude Code and Git Worktrees") characterised four-to-five
concurrent agents as the productive ceiling for a single human reviewer
to keep up with. Genesis stacks outer-of-inner, so N×M = 6 is the
conservative right answer; raising it past 8 means the human review of
the merge stream becomes the bottleneck, not the model.

## Worktree state machine

Each worktree at any moment is in one of these states:

```
                  ┌──────┐
                  │ idle │  (worktree exists, no claude subprocess in it)
                  └───┬──┘
                      │ dispatch iteratotron
                      ▼
            ┌──────────────────┐
            │  iteratotron     │ — runs scope-completion loop
            └────────┬─────────┘
                     │ result event
                     ▼
            ┌──────────────────┐
            │  adversarial     │ — cold-context review against design intent
            │  review          │
            └────────┬─────────┘
                     │ APPROVED                  INSUFFICIENT
                     ├───────────────────────────┐
                     ▼                           ▼
            ┌──────────────────┐         ┌──────────────────┐
            │ merged / done    │         │ requeue + tag    │
            └──────────────────┘         │ "lessons         │
                                         │  learned"        │
                                         └────────┬─────────┘
                                                  │
                                                  ▼
                                          (re-dispatch)

      (parallel track, alternating per worktree)

                  ┌──────┐
                  │ idle │
                  └───┬──┘
                      │ dispatch bug-burndown
                      ▼
            ┌──────────────────┐
            │  bug-burndown    │ — runs finding-closure loop
            └────────┬─────────┘
                     │ result event
                     ▼
            ┌──────────────────┐
            │  finding closed  │
            │  (verified by    │
            │  bug-burndown's  │
            │  own Phase 9)    │
            └──────────────────┘
```

A worktree is **never** in two states at once. The global semaphore
(N × M concurrent claude subprocesses) prevents overload across
worktrees.

## Evaluator-optimizer: the harness escalation loop

The evaluator at the centre of the architecture isn't a single LLM
call — it's a deterministic ladder that escalates through tiers:

1. **Tier-1 evaluator (unit + coverage + mutation)** runs after every
   scope completion claim. If it fails, the scope re-enters the
   iteratotron queue with the failing tool's output prepended as a
   finding.
2. **Tier-2 evaluator (integration + contract + BDD)** runs only at
   story-completion claims. If it fails, the finding is structured
   (which scenario failed, which contract was violated) and routed
   to bug-burndown's queue, not back to iteratotron.
3. **Tier-3 evaluator (chaos + DST + multi-VM + Wycheproof)** runs
   only when the scope's spec content matches a trigger. Failures
   become P0 bug-burndown findings.
4. **Adversarial completion reviewer** runs on every APPROVED
   scope-completion claim, regardless of tier. It's a fresh stateless
   `claude -p` with `Read, Glob, Grep` only — no edit tools. Its job
   is to catch semantic completion failures that the deterministic
   tiers can't.

The adversarial reviewer's prompt template lives in
`references/streaming-orchestration.md` § "Adversarial review prompt".

## Recurrence detection

`.iteratotron/recurrence.jsonl` is append-only:

```jsonl
{"session_id": "20260525-...", "scope_id": "example/transport/zmq-router", "attempt_idx": 0, "embedding": [...], "outcome": "incomplete", "diff_summary": "..."}
{"session_id": "20260525-...", "scope_id": "example/transport/zmq-router", "attempt_idx": 1, "embedding": [...], "outcome": "incomplete", "diff_summary": "..."}
```

Before launching attempt N+1 of a scope, compute cosine similarity of
the new attempt's planned-diff embedding vs. all prior attempts for
the same scope. If similarity > 0.92 **and** the prior outcomes were
all "incomplete", promote the scope to a `STOP-PAT` entry and surface
to the human after **3 hits**, not 1 (false positives are real — a
similar-sounding scope is not necessarily the same problem).

Embedding is done with the local `sentence-transformers` model when
available, else fallback to a deterministic n-gram-similarity Python
function (iteratotron pins one in `scripts/recurrence.py`). The embedding
itself doesn't have to be high-quality; it just has to be **stable
across sessions** — that's what matters for recurrence.

## When parallelism legitimately drops

`parallel:N` and `inner:M` from arguments are the user-specified
maxima. Genesis may drop below them only for the following reasons.
Anything outside this list is a defect:

| Reason | Trigger | New value |
|---|---|---|
| Sequential doc bootstrap | Any dispatchable scope has `needs_all_aboard: true` | parallel:1, inner:1, until all such scopes have completed `/all-aboard` |
| Capability check at Phase 0 | Available RAM < 2 GB per outer slot OR CPU cores < parallel | min(available_slots, requested) |
| User override | User passed `parallel:1` or `inner:1` in arguments | as specified |
| Merge-conflict circuit breaker | Three consecutive reconcile cycles produced conflicts | 1, until human investigates |
| Cost circuit breaker | Per-day USD usage > 80% of budget | drop by 1 until utilisation < 60% |
| Budget circuit breaker | Wall-clock used > 90% of `time:Nh` | 1, drain in-flight scopes only |

When parallelism is reduced, emit a one-line status to the operator:
`parallelism reduced to N×M — reason: <reason from table>`. Without
the line, the reduction is silently broken behaviour.

## Phase 7 — Adversarial completion review

Runs after every subagent's stop-hook-passed completion claim, before
the worktree merges. The reviewer subagent (spawned via streamed
`claude -p` with cold context) sees only:

- The diff between `baseline_sha` and the worktree HEAD.
- The scope's linked design artefacts (spec, ADRs, threat model, stories).
- The iteration log produced.
- The original gap inventory.

It does **not** see the iteratotron subagent's reasoning. Cold-context
verification is the point — the reviewer can't be primed by the worker's
narrative.

### Required subsections (every one must be filled)

1. **Restate the completion intent** — one sentence per gap category, citing spec/ADR/story line.
2. **Three-way diff per gap** — *Desired* (spec/ADR), *Documented* (iteration log), *Implemented* (the diff). Any divergence is suspect.
3. **Stop-bias-pattern re-scan against the worktree** — re-run iteratotron's stop-bias scan (twelve families) against the post-iterate state. New stub / placeholder / partial means iterate introduced a new gap. Reject.
4. **Hallucination spot-check** — for any new function/test, verify it does substantive work, asserts on the code under test (not its own setup), and that doc comments accurately describe the code.
5. **Doc-vs-code three-way diff at scope boundaries** — for each artefact the iteration log claims to have moved to `Implemented`, confirm the artefact was updated AND the implementation matches.
6. **Cross-scope contract preservation** — does the diff change any public API that other in-flight scopes depend on? If yes, surface as a coordination warning.

### Verdicts

- **APPROVED** — every subsection filled, no defect. Proceed to merge.
- **INSUFFICIENT** — scope returns to queue with new findings prepended to its gap inventory; `attempt_count++`. Prior iteration log entries preserved as lessons.
- **NEEDS_HUMAN** — review found something requiring human design input (spec says X, ADR says Y, implementation does Z).

## Why orchestrator-workers, not "agent team"

Claude Code's experimental "Agent Teams" (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`,
v2.1.32+) treats peer agents as separate sessions with their own context.
That's the wrong shape for iteratotron. Per the *Building Effective Agents*
guidance, **orchestrator-workers is strictly more controllable** than a
peer team because:

- The orchestrator owns the dispatch decisions (no consensus required).
- Workers can be killed and restarted cheaply.
- Cost / time / scope budgets are enforced at the orchestrator boundary.
- The audit trail is a single linear log per worker, not an N-way
  conversation that's harder to replay.

Resist the urge to model iteratotron as a team. The SOP / orchestrator
pattern (MetaGPT's ICLR 2024 lesson — see `docs/genesis.md` § Part 5)
is strictly the right one for spec-driven completion work.
