---
name: adr-review
description: "Reviews Architecture Decision Records for quality, completeness, and consistency. Identifies undocumented decisions by analyzing code, specs, and threat models. Backfills missing ADRs for past decisions, validates cross-references, and checks the decision log for staleness or contradictions. Use when auditing ADRs, finding missing decisions, reviewing ADR quality, checking for undocumented architecture choices, or when spec-review or threat-model-review flags missing ADRs. Triggers: review ADR, audit decisions, missing ADRs, ADR quality, backfill ADRs, decision log, undocumented decisions."
version: 1.0.0
license: MIT
category: Documentation
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# ADR Review

Audit the decision log for gaps, staleness, and quality issues. Teams routinely
make important decisions and never write them down — this skill finds decisions
hiding in code that have no ADR, checks existing ADRs for completeness,
validates cross-references to specs and threat models, and backfills what's
missing by analyzing the codebase. When it finds undocumented decisions it
recommends creating ADRs via `adr-create`.

An ADR review answers: **are all significant decisions documented?**
(completeness) **are existing ADRs well written?** (quality) **do they still
reflect reality?** (currency) **are cross-references intact?** (traceability).

## Completion loop

This skill ships a `hooks.json` with a `Stop` checker
(`scripts/check-completion.py`) that keeps the review running until every gate
passes. In opencode this runs via the `skill-hooks` plugin (see the repo's
`doc/skill-hooks.md`); the plugin re-prompts on `{"decision": "block"}`. Without
the plugin, re-run the skill until it reports no gaps. The report is written to
`docs/adr-review-report.md`, which the checker inspects.

## When to use

- Auditing the decision log before onboarding, a governance review, or after a
  major refactor that may have invalidated ADRs.
- Checking whether all technology choices are documented.
- `spec-review` or `threat-model-review` flagged missing ADRs.
- Periodic maintenance to keep the log current.

## Workflow

### Phase 1 — Inventory

Find all ADRs (`find docs/adr/ -name '*.md'`). If none, scan non-standard
locations (`docs/decisions/`, `architecture/`, decision-named `.md` files), ask
the user whether to scan candidates or start with ADR-0001, and jump to Phase 2.
If ADRs exist, catalog each into a table: number, title, status, date, and
whether it links to a spec requirement and threat-model entry.

### Phase 2 — Discover undocumented decisions

The highest-value phase. Mine the codebase: dependency files (`Cargo.toml`,
`package.json`, `go.mod`, `Gemfile`, `pyproject.toml`) — every significant
dependency (DB, web framework, auth lib, cache/queue, logging) is a decision;
infra files (Dockerfile, compose, Terraform, Nix, nginx, Procfile); architectural
patterns (MVC vs hexagonal, JWT vs sessions, ORM vs raw SQL, error handling,
inter-service comms); and git history (`git log --diff-filter=A -- '*.toml'
'*.json' '*.nix'`, `git log --grep='migrate\|switch\|replace\|deprecate'`).
Cross-check specs and threat models for choices mentioned without an ADR. Each
gap is a backfill candidate.

### Phase 3 — Quality assessment

Per ADR check format (frontmatter with status+date, noun-phrase title,
sequential `NNNN-brief-title.md` naming) and content (context describes forces
not conclusions; ≥2 options; honest pros/cons, no strawmen; outcome tied to
drivers; both good and bad consequences; plausible date). Common issues:
one-option ADRs, strawman rejections, missing bad consequences, context written
as conclusion, missing/invalid status.

**Status validation** — only `proposed` / `accepted` / `deprecated` /
`superseded` are valid. Flag non-standard values ("draft", "wip"). For an
`accepted` ADR with an `## Implementation Location` section, verify the
referenced files exist — a completion-checking skill (e.g. `iterate` via its
`hooks.json` checker) treats missing files as a gap (decision made, code not
written). Also check staleness: accepted ADRs still reflect the architecture,
superseded ones reference their replacement, deprecated ones have a reason.

### Phase 4 — Cross-reference validation

Verify ADRs for technology choices reference the spec requirements they enable
and vice versa; security ADRs reference the threats they mitigate and vice
versa; no broken links; superseded ADRs chain correctly with no cycles;
numbering is sequential with no duplicates; no two accepted ADRs contradict each
other on the same concern.

### Phase 5 — Report and backfill

Write `docs/adr-review-report.md` with a summary (counts by status, undocumented
decisions, quality issues, missing cross-references, stale ADRs), an
undocumented-decisions table (decision / source / recommended ADR title /
priority), a quality-issues table, cross-reference gaps, and prioritized
recommendations. Backfill via `adr-create` (retroactive workflow), security
decisions first, then technology, then patterns — 4–6 per session is
sustainable. Cross-reference new ADRs immediately.

## Style

Findings should be specific: "ADR-003 lists no alternatives — it just says 'we
chose Redis'. Add at least one (Memcached, in-process cache) with honest pros and
cons." Don't claim the log is "complete" — state what you reviewed, how many
decisions you found, and which areas weren't examined.

## Resources

- [references/review-checklist.md](references/review-checklist.md) — detailed ADR review criteria
- `scripts/check-completion.py` — the `Stop`-hook gate (see `hooks.json`)
