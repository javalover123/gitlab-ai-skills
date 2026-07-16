---
name: story-reviewer
description: "Reviews E2E user stories for INVEST compliance, Gherkin correctness, EARS constraint coverage, and test derivation quality. Produces a structured verdict with per-dimension scores, specific issues, and actionable feedback. Use when validating a story before sprint planning, reviewing stories created by story-creator or an AI generator, or auditing story quality in a PR. Triggers: review story, validate story, story quality, BDD review, acceptance criteria review, story audit, story feedback, INVEST check."
version: 1.0.0
license: MIT
category: Documentation
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# Story Reviewer

Run a story through a seven-dimension quality gate and produce a structured
verdict — PASS, NEEDS_REVISION, or REJECT — with a score and specific,
quoted issues per dimension. The feedback is designed so that feeding it back to
`story-creator` actually improves the score, not generic advice. Loop until PASS.

## Completion loop

Ships a `hooks.json` with a `Stop` checker (`scripts/check-completion.py`) that
keeps the review running until the verdict is PASS. In opencode this runs via the
`skill-hooks` plugin (see `doc/skill-hooks.md`), which re-prompts on
`{"decision": "block"}`. Without it, re-run until PASS.

## When to use

- After `story-creator` produces a draft (always review before sprint planning).
- Reviewing stories in an MR, or auditing existing stories for quality.
- When AI-generated stories need human-quality validation before use.
- After refactoring that may have broken story-to-code traceability.

## Review dimensions

Score each **1–4** (4 = fully satisfies, 3 = minor gaps, 2 = significant gaps
needing revision, 1 = missing/broken). Flag each failure with the exact offending
text and the fix. Detailed rubric:
[references/review-rubric.md](references/review-rubric.md).

1. **INVEST** — Independent (no dep on incomplete stories), Negotiable (not
   over-specified — no "use Redis"), Valuable (real "so that"), Estimable, Small
   (≤4 acceptance criteria), Testable (clear pass/fail, no "feels fast").
2. **Gherkin correctness** — Given = preconditions (state, not actions), When = a
   single trigger, Then = a measurable/observable outcome; And/But only for
   same-type steps; no over-specific implementation detail. Coverage: ≥1
   happy-path, ≥1 failure, plus boundaries for numeric/size/concurrency limits.
3. **EARS coverage** — system invariants expressed as EARS, not buried in
   Gherkin: timeout→event-driven, concurrency→state-driven, security
   failure→unwanted-behavior, performance→ubiquitous.
4. **Autonomy boundaries** (agent stories only) — max actions per cycle (a
   number), escalation threshold (a concrete condition), prohibited actions
   (explicit list), human-oversight requirement. "Uses its judgment" fails.
5. **Security coverage** — for each data flow, STRIDE: Spoofing→authn,
   Tampering→integrity, Repudiation→audit, Info Disclosure→data protection,
   DoS→rate limit, Elevation→authz. Stories crossing trust boundaries must
   address all six. See [references/security-coverage.md](references/security-coverage.md).
6. **Test derivability** — each Gherkin scenario must yield a concrete test
   (Given→setup, When→action, Then→assertion) with a type and framework; flag
   criteria too vague to test. Build the traceability matrix
   ([references/test-derivation.md](references/test-derivation.md)).
7. **Traceability links** — related ADR / spec requirement / dependency stories /
   standards mappings all resolve; flag broken links specifically.

## Verdict

Emit: verdict + date; a per-dimension score table with a total (`/28`, or `/24`
if autonomy N/A); issues (`BLOCK`/`WARN`, dimension, quoted text, what's wrong,
what to change); the derived test-case matrix; and a "Feedback for Revision"
section (3–6 actionable items to paste back into `story-creator`).

**Thresholds:** PASS = all dimensions ≥3 and no BLOCK; NEEDS_REVISION = any
dimension =2 or any BLOCK; REJECT = any dimension =1 or >2 BLOCK issues.

## Generator–critic loop

Works with `story-creator`: draft → review → feed "Feedback for Revision" back →
revise → re-review, up to **3 cycles**; if still not PASS after 3, ask the user
what trade-off to make rather than iterating autonomously. Track the cycle in the
story's Status field, using these **exact** values so a completion-checking skill
(e.g. `iterate` via its `hooks.json` checker) can count unfinished stories:
`Draft` / `Revision N` (both block, P1) → `Implemented` / `Complete` (don't
block). Flag non-standard statuses ("In Progress", "WIP").

When reviewing a batch, score all first, fix REJECT before NEEDS_REVISION, and
prioritize security-coverage gaps > traceability breaks > INVEST > Gherkin.

## Style

Feedback should read like a knowledgeable colleague, aiming at revision not
blame: "the 'system should respond quickly' criterion can't be tested — add a
concrete target (e.g. 'within 500ms under normal load')", not "the acceptance
criteria is insufficient and does not meet the testability requirement".

## Resources

- [references/review-rubric.md](references/review-rubric.md) — detailed scoring criteria with examples
- [references/test-derivation.md](references/test-derivation.md) — building the traceability matrix
- [references/security-coverage.md](references/security-coverage.md) — STRIDE mapping and standards references
- [references/common-failures.md](references/common-failures.md) — patterns that reliably fail review, with fixes
- `scripts/check-completion.py` — the `Stop`-hook gate (see `hooks.json`)
