# Orchestration integration

How generated harnesses invoke the `iteratotron` and `bug-burndown`
orchestrators. Both run as in-session agents via the opencode server
(see `opencode-server-integration.md §4`). The harness creates a
session, sends the prompt, and waits for the three-way AND completion
before processing the result.

## Session context (all orchestrators)

Every dispatch prompt must include:

```
Project root: <absolute path>
Worktree: <absolute path to the isolated worktree>
Scope: <scope title or description>
Constitution: <path to constitution.md>
Budget remaining: $<X.XX> USD
```

Pass the worktree path as `--add-dir` in the opencode session
configuration; the project root comes from the cwd of the opencode server
(set at launch — see `opencode-server-integration.md §3.4`).

**Every dispatch prompt must also carry the no-questions directive.** These are
autonomous sessions: there's no human to answer the `question` /
`AskUserQuestion` tool, and a call to it blocks the turn until the driver
cancels it (a false Timeout for the whole scope). Prepend a standing directive
telling the agent the run is autonomous, not to call the question tool, and to
decide for itself — best option for the documented intent (for a bug, the shape
of the bug) weighing complexity against intent, or defer a genuinely
load-bearing choice to a `docs/decisions/` note for human review and keep going.
The driver's auto-answer (`opencode-server-integration.md §14`) is the safety
net when an agent ignores the directive; the directive keeps it from happening
in the first place.

## iteratotron — genesis mode

Use when driving new implementation from documentation.

```
/iteratotron mode:genesis scope:"<scope title>"
context: <scope description paragraph from plan>
constitution: <path>
worktree: <path>
```

The session agent runs the full iteratotron lifecycle (constitution check,
bootstrap, gap analysis, plan, inner loop, adversarial review, done
predicate). The harness waits for session completion and reads
`.iteratotron/<session-id>/state.json` for the outcome.

## iteratotron — sweep mode

Use when documentation is current and you're closing remaining gaps.

```
/iteratotron mode:sweep scope:"<scope title>"
context: <scope description>
constitution: <path>
```

Sweep runs the inner loop only (no bootstrap/gap-analysis). Faster and
cheaper than genesis; use it for follow-up iterations after the initial
genesis pass converges.

## bug-burndown

Use to close a specific defect or batch of defects.

```
/bug-burndown
session: <bug-burndown session directory>
scope: <affected component or file path>
```

The harness writes the bug-burndown session directory before dispatch
(via `findings.rs`/`findings.go`) and passes the path to the agent.
The agent reads findings from the session, produces fixes, and exits.
The harness then re-runs the affected Tier-1 gates to verify closure.

## Handling completion

After the three-way AND check (`message.updated` with
`info.time.completed` set, `session.idle`, and `/todo` empty — see
`opencode-server-integration.md §5`), the harness reads the
orchestrator's output from its state directory:

| Orchestrator | Output location | Key fields |
|---|---|---|
| iteratotron genesis | `.iteratotron/<session-id>/state.json` | `phase`, `done_predicate_passed`, `cost_usd` |
| iteratotron sweep | `.iteratotron/<session-id>/state.json` | `scopes_remaining`, `last_verdict` |
| bug-burndown | `.bug-burndown/<session-id>/findings.json` | `status` per finding |

A `done_predicate_passed: true` with no `error` field means the scope
is closed. A `status: "fixed"` on all findings in the burndown session
means the batch is resolved. Anything else re-queues the scope or
escalates to `park_for_human`.

## Global termination — the cross-phase fixpoint

Per-orchestrator completion (above) is necessary but not sufficient to
stop the **flow**. The harness drives multiple phases — iterate /
implementation, the adversarial review of documented requirements and
state, and bug burndown — and each must report no remaining work **in
the same round** before the flow exits. See SKILL.md "Loop termination —
the global fixpoint" for the full rule; the protocol pieces the
orchestration layer must respect:

1. **Every phase returns `Clean | WorkRemaining`, never a bare `Ok`.**
   Map the orchestrator outputs to it:
   - iteratotron genesis → `Clean` iff `done_predicate_passed: true`
     (scopes empty AND bugs clean AND tier-1 green AND alignment gate
     `ALIGNED`); otherwise `WorkRemaining`.
   - iteratotron sweep → `Clean` iff `scopes_remaining == 0`.
   - bug-burndown → `Clean` iff every finding is `fixed`/`wont_fix`
     with zero `queued`/`in_flight`; a zero-tool-call turn is
     `WorkRemaining`, never resolved.
   - adversarial reviewer → `Clean` iff it **ran** and returned zero
     rejects. A run where it could not produce any verdict is **not**
     `Clean` (next point).

2. **A review/transport outage is an error, not zero rejects.** When the
   reviewer cannot obtain a verdict from any pass (e.g. `POST /session`
   500s, every prompt hits the deadline, the JSON never parses across
   all candidates), it has zero information about the corpus. Return an
   error so the phase is `WorkRemaining`; never let an empty verdict list
   from a dead reviewer read as `CLEAN`. One surviving pass is still real
   signal and is fine. (2026-06-14 false-clean incident: both passes
   500'd, the loop logged `ITERATION CLEAN — zero rejects`, the flow
   exited with documented scope open.)

3. **The outer loop repeats the full plan** until a round is clean across
   all phases, because a later phase's fixes can reopen earlier scope.
   Bound it with `max_rounds` (derive from `max_iterations`) and fail
   loudly on exhaustion — oscillation is a bug to surface, not a success
   to claim.

## Parallel dispatch limits

- **Runtime outer loop**: serial — one daemon at a time.
- **Implementation inner loop**: up to `parallel_outer` worktrees concurrently (CLI flag, default 2). Each worktree gets its own opencode session; they share the single server instance.
- **Bug-burndown**: inner fan-out up to `parallel_inner` (CLI flag, default 3) within a single burndown session.
