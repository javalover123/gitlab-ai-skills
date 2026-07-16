---
name: spec-review
description: "Reviews implementation specifications for completeness, correctness, and traceability. Identifies gaps between spec and implementation, missing requirements, broken cross-references to ADRs and threat models, and ambiguous or untestable requirements. Creates new specs when none exist. Use when reviewing a spec, auditing requirements coverage, checking spec quality, finding spec gaps, or when the codebase has drifted from its spec. Triggers: review spec, audit requirements, spec gaps, spec quality, requirements coverage, check specification, spec drift."
version: 1.0.0
license: MIT
category: Documentation
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# Spec Review

Review specs for completeness, find gaps between what the spec says and what the
code actually does, and make sure every requirement is testable, traceable, and
unambiguous. If no spec exists, analyze the codebase and create one (via
`spec-create`), then review that output.

A spec review checks four things: **completeness** (does it cover everything
built?), **correctness** (does it match the code?), **traceability** (does every
requirement link to tests, ADRs, threat-model entries?), and **quality** (is
every requirement unambiguous and testable?).

## Completion loop

Ships a `hooks.json` with a `Stop` checker (`scripts/check-completion.py`) that
keeps the review running until every gate passes. In opencode this runs via the
`skill-hooks` plugin (see the repo's `doc/skill-hooks.md`), which re-prompts on
`{"decision": "block"}`. Without the plugin, re-run until it reports no gaps. The
report goes to `docs/spec-review-report.md`, which the checker inspects.

## When to use

- Auditing an existing spec after significant development, or before a release.
- Checking whether a spec still reflects the implementation.
- A project has code but no spec — create and review one retroactively.
- `adr-review` or `threat-model-review` flagged spec gaps.

## Workflow

### Phase 1 — Discover and inventory

Find specs (`find docs/specs/ -name '*.md'`; also `*spec*`/`*requirement*`/`*srs*`).
If none, ask whether to generate one from the codebase (via `spec-create`) or
look in a non-standard location, then continue the review. If specs exist, count
requirements (FR/NFR/…), check for a traceability matrix, note the last-modified
date, and read for coverage.

### Phase 2 — Gap analysis (spec vs. code)

The most valuable phase. **Code not in spec (drift):** scan for API endpoints,
data-model fields, error paths, config options, authn/authz checks, and
background jobs without a requirement (`grep -r 'route\|handler\|endpoint'`,
`grep -r 'class.*Model\|struct\|CREATE TABLE'`). **Spec not in code
(unimplemented):** for each requirement confirm code exists; verify `**File:**`
markers point to real files (a completion-checking skill like `iterate`, via its
`hooks.json` checker, treats missing implementation files as P1 and missing
`**Test File:**` as P2); confirm removed requirements are `[DEPRECATED]` rather
than silently deleted. Check every `### Task N:` section has an accurate,
project-relative `**File:**` marker.

### Phase 3 — Quality assessment

- **Testability:** "the checkout flow SHALL complete in ≤4 steps", not "should
  be user-friendly". Every FR has Gherkin criteria; every NFR a measurable
  threshold; correct RFC 2119 keyword usage.
- **Ambiguity:** EARS syntax; no requirement joining unrelated behaviors with
  "and"; no "etc."/"as appropriate"; edge cases explicit.
- **Completeness:** error handling (not just happy paths), security (authn,
  authz, data protection), performance thresholds, data retention, operational
  and monitoring requirements.
- **INVEST** for any user stories present.

### Phase 4 — Cross-reference validation

Audit the traceability matrix (every requirement present with ≥1 test case;
security → threat entries; tech choices → ADRs; no orphan tests; status current)
— build one if absent. Flag missing ADRs (`adr-create`/`adr-review`) and missing
threat coverage (`threat-model-create`/`threat-model-review`).

### Phase 5–6 — Report and recommend

Write `docs/spec-review-report.md` structured by severity (critical / important /
suggestions), with a gap-inventory table (type / description / recommendation —
code-without-spec, spec-without-code, missing test, missing ADR, missing threat
entry) and prioritized recommendations. Give a specific fix per finding.

## Creating a spec from scratch

When none exists: analyze the codebase (`spec-create` Phase 1), generate
requirements (each endpoint/model/integration), write the spec with the
`spec-create` template, then review your own output with Phases 2–4. State
honestly: "generated from code analysis on [date]; covers observable behavior
but may miss business logic, edge cases, or design intent not evident from the
implementation." Don't pretend to have captured everything.

## Style

Findings must be specific and actionable — "FR-003 uses 'should be fast'; replace
with 'SHALL respond within 200ms at p95'", not "some requirements could be
improved". Never claim the review is "complete" — state what you reviewed, the
criteria applied, and what wasn't examined.

## Resources

- [references/completeness-checklist.md](references/completeness-checklist.md) — detailed spec-review checklist
- `scripts/check-completion.py` — the `Stop`-hook gate (see `hooks.json`)
