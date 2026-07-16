---
name: harness-builder
description: "Scaffolds project-specific harness crates or modules that drive a project through its natural interface, observe and instrument the output, and triage it against documented requirements (stories, ADRs, specs, threat-model items) to schedule and burn down implementation gaps and defects in a continuous loop. Generates a runtime quality harness, an implementation genesis harness, or both, and can audit an existing harness up to standard. Use when asked to build a harness, scaffold project genesis, drive X and fix what breaks, loop until clean, build a closed-loop harness, or burn down bugs agentically."
version: 2.3.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# harness-builder

Scaffold a harness that drives a project through its real interface, observes
the result, triages it against documented requirements, and burns down the gaps
— continuously, until scope is exhausted. It generates the harness code; it
doesn't run the loop itself.

## Two modes

- **Build** — scaffold a new harness crate/module for a project.
- **Audit** — bring an existing harness up to standard and find its bugs
  ([references/audit-mode.md](references/audit-mode.md)).

Two harness *shapes* come out of build mode: a **runtime quality harness** (drive
a running service/CLI, triage behaviour) and an **implementation genesis harness**
(drive a project from docs to a done predicate). A project can want both.

## The continuous loop

Both shapes run the same cycle until scope is exhausted:

```
INSTRUMENT → DRIVE → OBSERVE → TRIAGE → SCHEDULE → BURN DOWN → repeat
```

Instrument (sandbox verdict, state snapshot, requirements load), drive the
project through its natural interface, observe structured output/logs/metrics,
triage each signal against requirements (LLM reviewer **plus** a structural
anti-rationalization audit), schedule rejects/gaps onto the story/ADR/spec/threat
item they violate, then dispatch in-session agents to close each one.

## Loop termination — the global fixpoint (mandatory)

The harness may stop **only** when implementation (`iterate`), the adversarial
review of documented requirements, **and** bug burndown all report zero remaining
work **in the same pass**. A clean signal from one phase is necessary but never
sufficient — stopping on it while another phase still has work (or was never
re-run) is the canonical early-exit defect.

Make every phase return an explicit `PhaseOutcome { Clean, WorkRemaining }`, not
a bare `Ok(())`, and wrap the plan in an outer fixpoint loop that ends only when
an entire round is `Clean` for every phase (a later phase's fixes routinely
reopen earlier scope). Bound it with `max_rounds` so cross-phase oscillation
terminates as a loud error, never a success. Count as `WorkRemaining`: an
unsatisfied done predicate, any adversarial reject, a queue left non-empty, a hit
`max_iterations`/time cap, or a `--dry-run`.

**Reviewer/transport outage ≠ clean.** A phase that couldn't get a verdict (the
session endpoint 500'd, every prompt hit its deadline, the JSON never parsed) has
*zero* information — the opposite of "found nothing wrong". Treat a total review
outage as a phase error (`WorkRemaining`), never as zero rejects.

## Size the deadlines to the workload (mandatory)

The skeleton timing constants suit a fast service watchdog. A build system, an
E2E harness, or any project whose drive surface or fix turns invoke heavy work
needs much larger ceilings, or phases time out mid-flight and report false
Timeouts — the most misleading failure mode. Classify the workload in Step 2 (a
`flake.nix`/`Makefile` with image or VM-test outputs, a gate that shells out to
`nix build`/`docker build`/`bazel`/a VM-booting suite signals the build-system
envelope) and set hard ceilings to clear the *slowest productive* turn, keeping
only the stall/liveness window tight. Never lower a ceiling to catch hangs faster
— that's the stall watchdog's job. The knob-by-knob table is in
[references/runtime-gotchas.md](references/runtime-gotchas.md).

## Workflow (build mode)

Interview first, build second — confirm shape(s), drive surface, requirement
sources, and workload class before scaffolding. Then: detect project context
(Step 2), scaffold the harness crates (Steps 4–5), wire the orchestration bridges
to `iteratotron`/`bug-burndown` (Step 6), write the README (Step 7), smoke-test
(Step 8), and commit (Step 9). Per-language skeletons:
[Rust](references/runtime-rust-skeletons.md),
[Go](references/runtime-go-skeletons.md), and the implementation-harness variants
([Rust](references/implementation-rust.md), [Go](references/implementation-go.md),
[Python](references/implementation-python.md), [Ruby](references/implementation-ruby.md),
[Nix](references/implementation-nix.md)).

## Sandbox contract

The harness runs the project and its agents inside a sandbox — never
unsandboxed. The generated code wraps every drive and agent invocation with the
sandbox preflight and per-language read dirs. See
[references/nono-integration.md](references/nono-integration.md).

## Agent backend

Generated harnesses dispatch in-session agents through an opencode server (the
native backend) — lifecycle state machine, the shared `/event` reader, and
never deleting live sessions (reclaim via server dispose) are covered in
[references/opencode-server-integration.md](references/opencode-server-integration.md).
The interview maps `AskUserQuestion` → the `question` tool and task tracking →
`todowrite`/`todoread`.

## Structural anti-rationalization audit (mandatory for runtime harnesses)

An LLM reviewer alone accepts plausible-sounding failure. Pair it with a
deterministic audit: a success marker sitting next to a fallback marker is
evidence of *failure*, regardless of how the log is worded. In one real
seven-iteration run, iterations accepted zero upstream fetches because "served
from cached entries — cache-fallback succeeded" satisfied the LLM rubric; the
audit makes that impossible. Maintain project-specific failure/success/fallback
marker lists and a whole-log correlation pass that catches non-error divergence
the per-operation tally misses.
[references/runtime-reviewer-rubric.md](references/runtime-reviewer-rubric.md).

## Hard anti-patterns

Never accept a single phase's clean result as done; never treat a review outage
as zero rejects; never lower a hard ceiling to catch hangs; never run the project
or its agents unsandboxed; never ship the generated harness without a post-merge
`bugfix` review of its own new concurrency/persistence code. The full list is in
[references/runtime-gotchas.md](references/runtime-gotchas.md).

## Companion skills

Generated harnesses dispatch `iteratotron` (lifecycle orchestrator),
`bug-burndown` (finding closure), and transitively `iterate`; use `bugfix` for
the post-merge review of the harness's own code. harness-builder scaffolds the
bridges to these but doesn't modify them.

## References

- [references/nono-integration.md](references/nono-integration.md) — sandbox contract and preflight
- [references/opencode-server-integration.md](references/opencode-server-integration.md) — agent-dispatch backend
- [references/audit-mode.md](references/audit-mode.md) — bringing an existing harness up to standard
- [references/runtime-rust-skeletons.md](references/runtime-rust-skeletons.md) / [runtime-go-skeletons.md](references/runtime-go-skeletons.md) — runtime harness code
- [references/runtime-reviewer-rubric.md](references/runtime-reviewer-rubric.md) — three-pass reviewer, fingerprinting
- [references/runtime-gotchas.md](references/runtime-gotchas.md) — deadline knobs, anti-patterns, debug lessons
- [references/runtime-test-effectiveness-baseline.md](references/runtime-test-effectiveness-baseline.md) — `.test-effectiveness/` schema
- [references/orchestration-integration.md](references/orchestration-integration.md) — iteratotron/bug-burndown invocation
- Implementation harness: [Rust](references/implementation-rust.md), [Go](references/implementation-go.md), [Python](references/implementation-python.md), [Ruby](references/implementation-ruby.md), [Nix](references/implementation-nix.md), [Nix toolchain](references/nix-harness-toolchain.md)
