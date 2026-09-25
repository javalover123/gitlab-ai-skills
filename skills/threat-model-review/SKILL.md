---
name: threat-model-review
description: "Reviews threat models for completeness, accuracy, and alignment with current implementation. Identifies drift between threat model and code, uncovered attack surfaces, missing STRIDE categories, incorrect risk scores, and unlinked mitigations. Creates threat models when none exist. Use when auditing a threat model, checking security coverage, finding unmodeled threats, validating risk scores, or when implementation has changed since the threat model was written. Triggers: review threat model, audit threats, threat model drift, security coverage, unmodeled threats, validate risk, threat model gaps."
version: 1.0.1
license: MIT
category: Documentation
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# Threat Model Review

Check whether the threat model still reflects reality. Systems change — new
endpoints, evolving auth flows, updated dependencies, shifted infrastructure —
so an unreviewed threat model is probably out of date. This skill finds where
the model has drifted from what's deployed, discovers unmodeled attack surface,
and validates that risk scores and mitigations aren't stale. When none exists,
it creates one first via `threat-model-create`.

It answers: **is the Data Flow Diagram (DFD) current?** **are all threats
identified?** (did STRIDE miss anything?) **are risk scores accurate?** (have
mitigations changed the picture?) **are mitigations tracked?** (linked to spec
requirements and ADRs?)

## Completion loop

Ships a `hooks.json` with a `Stop` checker (`scripts/check-completion.py`) that
keeps the review running until every gate passes. In opencode this runs via the
`skill-hooks` plugin (see `doc/skill-hooks.md`), which re-prompts on
`{"decision": "block"}`. Without it, re-run until no gaps. The report goes to
`docs/threat-model-review-report.md`, which the checker inspects.

## When to use

- Implementation changed since the model was last updated, or new features added
  trust boundaries / data flows / external integrations.
- Preparing for a security audit; dependencies updated; an incident revealed an
  unmodeled threat.
- `spec-review` or `adr-review` flagged security gaps, or no threat model exists.

## Workflow

### Phase 1 — Locate and inventory

Find models (`find docs/threat-models/ -name '*.md'`). If none, create one via
`threat-model-create` and date it. If they exist, count DFD elements and threats,
note the last-modified date, and check which STRIDE categories are covered.

### Phase 2 — Data Flow Diagram validation (highest-value)

Compare the model's Data Flow Diagram against the code — this is where most drift
hides. Check external entities (new/removed integrations, correct trust levels),
processes (`grep -r 'fn main\|func main\|app.listen'`; added/removed/split,
changed privilege), data stores (`grep -r 'DATABASE_URL\|REDIS_URL\|S3_BUCKET'`;
new stores, changed sensitivity), data flows (new endpoints, changed protocols,
new trust-boundary crossings), and trust boundaries (new containers/meshes,
changed auth boundaries). Record a drift table (element / in model / in code /
status: current, missing-from-model, removed-from-code).

### Phase 3 — STRIDE coverage

For each **current** DFD element, verify STRIDE was applied: external entities →
Spoofing + Repudiation; processes → all six; data stores → Tampering + Info
Disclosure + DoS (including backups/replicas); data flows → Tampering + Info
Disclosure + DoS (including end-to-end encryption for sensitive data). Flag
uncovered element/category combinations with a recommended analysis.

### Phase 4 — Risk-score validation

For each threat, check whether DREAD scores still hold: has Damage changed (more
users / more sensitive data)? Reproducibility/Exploitability (new protections,
public exploit, tooling)? Affected users / Discoverability? Broader context (new
regulations, deployment change)? Check whether any threat was scored before
mitigations and never re-scored, whether any Critical still has "Not Started",
and whether similar threats have consistent scores.

### Phase 5 — Mitigation and cross-reference audit

Each threat entry needs a `**Status:**` using one of these **exact** values so a
completion-checking skill (e.g. `iterate` via its `hooks.json` checker) can track
remaining work:

| Status | Meaning | Blocks completion |
|---|---|---|
| `**Status:** Not Started` | No work | Yes (P0) |
| `**Status:** ⚠️ PARTIAL (…)` | Some done | Yes (P1) |
| `**Status:** ✅ DESIGNED — …` | ADR exists, not coded | Yes (P1) |
| `**Status:** ✅ IMPLEMENTED (SR-NNN, date)` | Coded + tested | No |

Validate every threat ≥11 has a mitigation; statuses are current; `IMPLEMENTED`
entries cite an SR and date; `PARTIAL` lists what's done/left; accepted risks are
justified; no non-standard values. Verify claimed mitigations actually exist in
code (`grep -r 'rate.limit\|throttle'` etc.). Cross-reference mitigations to spec
requirements and ADRs both ways, and flag missing links (add FR-XXX / run
`adr-create` / verify a stale "Implemented" status).

### Phase 6 — Report

Write `docs/threat-model-review-report.md`: summary counts, the DFD-drift table,
missing STRIDE coverage, risk-score issues (current vs. recommended + reason),
mitigation issues, newly discovered threats, and prioritized recommendations.

## Style

Findings must be specific: "TM-AUTH-001 scored 25 before rate limiting; with it
now on the login endpoint, Exploitability drops 8→4, bringing the score to 21
(Medium)", not "some scores may need updating". State what you examined and what
you didn't — a review is a snapshot; don't claim it's "complete".

## Resources

- [references/review-checklist.md](references/review-checklist.md) — detailed threat-model review criteria
- `scripts/check-completion.py` — the `Stop`-hook gate (see `hooks.json`)
