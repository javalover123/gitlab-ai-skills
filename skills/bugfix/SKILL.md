---
name: bugfix
description: "Drives a rigorous, evidence-gated bug fix or regression investigation from first report to Definition-of-Done. When invoked without a specific target, proactively scans logs, code, docs, git history, and issue trackers to discover bug candidates autonomously. User-given direction (bug report, issue ref, log path, class of bugs) takes priority. Enforces reproducer-first testing, root-cause fixes, a three-way diff between desired/documented/implemented behaviour, mandatory delegation to companion doc skills, and a hostile adversarial review before any done claim. Use when fixing bugs, investigating regressions, chasing spec/ADR/threat-model drift, or running a routine bug-hunting pass, especially for changes touching auth, crypto, supply chain, concurrency, persistence, or any trust boundary."
version: 1.0.1
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# Bugfix

Maximum-rigor mode. The job isn't to make symptoms go away — it's to (a)
understand the causal discrepancy between desired and observed behaviour, (b)
fix the root cause at the layer it originated, (c) prove the fix with a
reproducer that first failed for the right reason and now passes, (d) update any
documentation the discrepancy revealed wrong, and (e) survive a hostile
adversarial review. Don't declare success until every gate is PASS with cited
evidence — premature victory is this skill's cardinal failure mode.

**Argument hint:** `[bug summary, issue ref, or "investigate <symptom>"]`

## Two invocation paths

- **Specific direction** ("fix this auth bug, here's the trace") — skip Phase 0,
  emit a `## Bug statement` (expected, observed, environment, smallest input,
  regressed signal), run Phases 2–9.
- **General invocation** ("run a bugfix pass", no target) — run Phase 0 to
  discover candidates, pick the highest priority (security/correctness > drift >
  quality), emit its Bug statement, proceed to Phase 2. Only ask the user when
  candidates are roughly equal and can't be objectively ranked, or none were
  found (report `## No bugs found` with what you searched).

## The fixed reasoning structure

```
0. Discovery          — (general only) scan logs/code/docs/git for candidates
1. Intake             — restate bug; expected vs actual; environment; if the
                         optional DoD gate is registered, write
                         .bugfix/active-<session> and an empty
                         .bugfix/dod-<session>.md here
2. Context gathering  — code, logs, docs; ask only if needed
3. Reproducer first   — failing test that fails for the right reason
4. Causal analysis    — three-way diff; >=3 hypotheses; falsify each
5. Structural fix     — minimal change at the originating layer
6. Verification       — all test layers green; mutation-test the fix
7. Documentation      — delegate ADR / spec / threat-model / story updates
8. Adversarial review — hostile reviewer; cold-context re-derivation
9. Definition of Done — literal checklist with cited evidence
```

After each phase emit `GATE N: PASS` (or `BLOCKED`) with the evidence that
justifies it; if the optional DoD gate is registered, also write the phase
number to `.bugfix/phase-<session>` (the hook reads this to decide when to
start enforcing). Detailed mechanics live in the references:

- Phase 0 discovery scans, prioritisation, stop conditions:
  [references/bug-discovery.md](references/bug-discovery.md). Use `glab issue
  list --label bug` (or the project's tracker) for the issue-tracker scan.
- Phase 3/6 reproducer-quality protocol and mutation runbook:
  [references/reproducer-and-mutation.md](references/reproducer-and-mutation.md).
- Phase 6 test layers:
  [references/test-pyramid.md](references/test-pyramid.md).
- Observability (logs, traces, exemplars):
  [references/observability-debug.md](references/observability-debug.md).
- A full nine-phase walk-through:
  [references/worked-example.md](references/worked-example.md).

## Phase highlights

**Phase 4 — causal analysis.** Emit a three-way diff between *desired*
(spec/AC), *documented* (comments/docs), and *implemented* (code) behaviour;
name the authoritative source. Enumerate ≥3 hypotheses and run a falsification
search for each; the survivor must explain every symptom.

**Phase 5 — structural fix.** Fix at the originating layer, not where the
symptom surfaced. Pass a structural-vs-cosmetic audit (≥4 Ousterhout "yes"), do
a sibling-case sweep, and respect the blast radius — no scope creep.

**Phase 6 — verification.** Reproducer red-on-revert and green-on-fix; every
applicable test layer green; zero surviving mutants on changed lines; lint /
format / type clean. If the project mandates a **verification harness** (a
wrapper that bounds compile/test concurrency and caches results), route every
verification command through it and treat a direct bypass as a Phase 8 finding;
otherwise call the commands directly.

**Phase 7 — documentation deltas (delegated).** This skill doesn't author docs.
Detect which artefact classes the fix touched and invoke the companion skills:
`adr-create`/`adr-review`, `spec-create`/`spec-review`,
`threat-model-create`/`threat-model-review`, `story-creator`/`story-reviewer`.

**Phase 8 — adversarial review.** Switch role to a hostile reviewer whose only
reward is finding how the fix fails or the diagnosis is wrong; "looks good" is
forbidden. Adopt the role and required sections (invariant, attack scenarios,
untested input, symptom-fix audit, regression surface, falsifying observation,
verdict) from
[references/adversarial-reviewer.md](references/adversarial-reviewer.md) — or
delegate to an `adversarial-reviewer` subagent if your setup provides one (for
auth/crypto/supply-chain/concurrency/persistence changes, cold-context review
isn't optional). `GATE 8: PASS` only on an APPROVED verdict.

**Phase 9 — Definition of Done.** Emit the literal DoD checklist as the final
message, every box ticked with cited evidence (test output, file:line, tool
result), followed by `## Evidence`, `## Remaining Risks`, and `## Not Tested`
sections. The full checklist is in
[references/definition-of-done.md](references/definition-of-done.md).

## Forbidden phrases

Refuse to emit these unless immediately followed by cited evidence: "should
work", "looks correct/good", "probably fixed", "I believe this resolves",
"trivial", "obviously", "straightforward fix", "no further changes needed". If
you reach for one, you haven't collected the evidence yet.

## Forbidden actions

Never make the suite green by weakening it: no commenting out / `#[ignore]` /
`skip` / deleting tests; no broadening an assertion without a spec change; no
swallowing the error (`except Exception`, `.unwrap_or_default()`, `.ok()`); no
`sleep` to mask a race; no special-casing the reported input without a property
test for the class; no editing outside the diagnosed blast radius without a
recorded `## Out of scope → in scope` decision; no replacing a structural fix
with a docstring caveat.

## Optional Definition-of-Done gate

The skill ships `scripts/require-dod.sh` and a `hooks.json` declaring it as a
`PreToolUse` hook — under the `skill-hooks` plugin
(`.opencode/plugins/skill-hooks.ts`) it runs advisory during a bugfix session;
state lives in `.bugfix/` (ensure it's gitignored at Phase 1). Leave it
unregistered to keep DoD enforcement purely conversational.

The plugin runs `hooks.json` commands with cwd set to this skill's own
directory (then forces `CLAUDE_PROJECT_DIR` to the target project for the
script's own use), so `hooks.json`'s relative `scripts/require-dod.sh` path
resolves correctly without a `${CLAUDE_PLUGIN_ROOT}`-style substitution.

## Style

Apply the `natural-writing-style` guidance to every prose block: concrete and
evidence-cited (never claim a gate passes without quoting the output or
`file:line`), no readiness/completeness hand-waving, no effort/duration
estimates (describe scope and risk objectively), contractions natural.

## References

- [references/bug-discovery.md](references/bug-discovery.md) — Phase 0 scan patterns
- [references/reproducer-and-mutation.md](references/reproducer-and-mutation.md) — reproducer + mutation runbook
- [references/test-pyramid.md](references/test-pyramid.md) — four-layer test decision tree
- [references/observability-debug.md](references/observability-debug.md) — logs, traces, exemplars
- [references/adversarial-reviewer.md](references/adversarial-reviewer.md) — hostile-reviewer role and sections
- [references/definition-of-done.md](references/definition-of-done.md) — the literal DoD checklist
- [references/worked-example.md](references/worked-example.md) — full nine-phase walk-through
