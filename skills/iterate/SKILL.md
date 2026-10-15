---
name: iterate
description: "Brings projects to 100% completion through iterative cycles — implementing missing features, fixing security/correctness gaps, and refining code until all specs, ADRs, and threat model requirements are met. Runs gap analysis, prioritizes by security/correctness/quality/coverage, and auto-iterates until nothing remains. Use when completing an incomplete project, implementing remaining features from specs, addressing technical debt, or reaching production readiness. Triggers: iterate, bring to completion, implement remaining features, production readiness, gap analysis, address all gaps, complete project, iterative development."
version: 1.0.3
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# iterate

Drive an incomplete project to 100% — implement missing features, close
security and correctness gaps, and refine code until every spec, ADR, and
threat-model requirement is met. Each pass runs gap analysis, prioritises, fixes
the top item, validates, and checks whether anything remains.

## When to use

Use it to bring an incomplete project to feature completeness and security
coverage, implement remaining spec items (including stubs and placeholders),
address technical debt (TODOs, ignored tests), or work a backlog defined in
specs/ADRs/threat models toward completion. Don't use it to start a brand-new
project (run `all-aboard` first to create the docs), for exploratory refactoring
with no completion criteria (use `refactor`), or for a single focused change.

## Completion loop

This skill ships a `hooks.json` declaring three hooks that the repository's
skill-hooks plugin runs (see the plugin for the contract):

- **Stop** → `scripts/check-completion.py` — the deterministic gate. It emits
  `{"decision":"block", "reason":...}` with the remaining gaps while work
  remains, so the plugin re-prompts and the loop continues until it approves.
- **SessionStart** → `scripts/session-start-handover.py` — re-orients after a
  context compaction.
- **PreToolUse** → `scripts/context-watchdog.py` — advisory context check.

Without the plugin, run the skill again after each pass until the completion
checker reports no gaps.

## Single-turn autonomy — overrides default turn-taking

Base training biases you toward stopping at a clean summary, a "deferred"
annotation, a chunk boundary, or after the first verification pass. While
iterate is active those are **hard overrides**, and the Stop checker enforces the
same patterns — it will block a stop that violates them.

**Banned phrases** (writing any of these is the signal to keep going, not to
stop): "iteration done/complete", "moved the needle", "good stopping point",
"remaining debt", "follow-up for next session", a trailing "what changed:" /
"summary:" block, "re-invoke /iterate to continue", numbered iteration ordinals
("iteration 3", "after N passes"), "I'll pause here", "stopping here to let you
review".

**"Deferred" is the next task, never a stop.** When you find "deferred",
"pending", "waiting for", "follow-up", "placeholder", "not yet wired", or
"Partial" in a spec, story, ADR, threat model, changelog, or code comment, that
*is* the next task — start building the missing dependency in the same turn, even
if it means adding a type, a server stub, a client variant, and multi-file
wiring. "Deferred because it's hard" decomposes into smaller gaps, never into a
stop. For example, a story that says "dep-graph tab deferred until the graph RPC
lands" means: add the RPC type, add the service method returning a typed stub,
wire the client command and event, then wire the view — then scan for the next
gap.

**Don't number iterations.** Numeric anchoring ("5 iterations complete") primes
done-enough thinking; describe what changed instead.

**Valid stops (exhaustive):** every gap across features, security, correctness,
quality, and coverage is closed and the completion checker approves; or a gap
genuinely needs a human decision (surface it and ask); or a destructive action
needs confirmation. Nothing else.

## Iteration cycle

### Step 0 — Documentation & gap analysis (mandatory)

Project docs define what "done" means, so they aren't optional. Confirm all
three exist and are current, creating or reviewing each via its companion skill:
spec (`spec-create` / `spec-review`), ADRs (`adr-create` / `adr-review`), threat
model (`threat-model-create` / `threat-model-review`) — or `all-aboard` to
bootstrap all three. Then run a structured gap inventory (via
`implementation-review` if available) for a baseline that feeds Step 2.

### Step 1 — Assess current state

Before running any build/test/lint tool, read the **verification budget** in
[references/common-patterns.md](references/common-patterns.md): narrow, targeted
invocations during the inner loop, full suites only at validation. Detect the
project's languages and load the matching guidance from
[references/language-guides.md](references/language-guides.md).

### Steps 2–4 — Identify, prioritise, execute

Bucket gaps by severity: **P0 security**, **P1 correctness**, **P2 quality**,
**P3 coverage** (checklist in
[references/security-checklist.md](references/security-checklist.md) and
[references/coverage-guide.md](references/coverage-guide.md)). Work strictly
top-down, fixing the highest-priority gap first, and keep an iteration log
describing what changed (not numbered) per
[references/progress-tracking.md](references/progress-tracking.md).

### Steps 5–6 — Validate & check stopping criteria

Run the quality gates (`scripts/run-quality-checks.sh`, or the tools in
[references/ecosystem-tooling.md](references/ecosystem-tooling.md)); coverage
targets are in [references/coverage-guide.md](references/coverage-guide.md).
Then let the Stop checker decide whether to continue — don't self-declare
completion.

## Configuration

An optional `.iterate.json` at the project root tunes scope and timeouts
(include/exclude paths and extensions, per-command timeouts, coverage
threshold). Validate it with `scripts/validate-config.py`. Artifact-status
tracking (how spec/ADR/threat-model/story statuses drive the completion check)
is described in [references/artifact-status.md](references/artifact-status.md).

## Style

Iteration-log and gap-analysis prose should be concrete and specific — name the
files, types, and RPCs a gap touches. Don't write readiness or completeness
claims you can't back with a passing gate.

## References

- [references/common-patterns.md](references/common-patterns.md) — verification budget, inner-loop discipline
- [references/language-guides.md](references/language-guides.md) — per-language gap detection and tooling
- [references/security-checklist.md](references/security-checklist.md) — P0/P1 security gaps
- [references/coverage-guide.md](references/coverage-guide.md) — coverage targets and measurement
- [references/progress-tracking.md](references/progress-tracking.md) — iteration-log format
- [references/artifact-status.md](references/artifact-status.md) — status values the completion check reads
- [references/ecosystem-tooling.md](references/ecosystem-tooling.md) — quality tools by ecosystem
- [references/dependency-updates.md](references/dependency-updates.md) and [references/tool-setup.md](references/tool-setup.md)
- `scripts/check-completion.py` (Stop gate), `scripts/run-quality-checks.sh`, `scripts/validate-config.py`
