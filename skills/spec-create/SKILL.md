---
name: spec-create
description: "Creates and updates implementation specifications using IEEE 830 structure, RFC 2119 requirement levels, EARS syntax, and Gherkin acceptance criteria. Produces traceable, testable specs with cross-references to ADRs and threat models. Use when writing a spec, creating a specification document, defining requirements, documenting acceptance criteria, or updating an existing spec to cover new functionality. Triggers: write spec, create specification, document requirements, define acceptance criteria, update spec, spec gaps."
version: 1.0.0
license: MIT
category: Documentation
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# Spec Create

Write implementation specifications that are testable, traceable, and
unambiguous — greenfield specs, or updating existing ones to cover new
functionality or retroactively document what's already built.

A spec captures **what** to build, **why** it matters, **how** you'll verify
it's done, and **where** its architectural decisions and security constraints
come from. Every requirement gets a unique ID (`FR-001`), uses RFC 2119 keywords
for precision, and traces to test cases, ADRs, and threat-model entries. With no
existing docs, analyze the codebase directly and produce the spec from what's
there. Save specs to `docs/specs/`.

## When to use

- Starting a new feature or system and need a formal spec before coding.
- Retroactively documenting a system that lacks a spec, or updating a spec after
  features landed without spec changes.
- Breaking a large initiative into testable, traceable requirements.
- Connecting requirements to ADRs (`adr-create`) and threat models
  (`threat-model-create`).

Not for quick TDD-style task breakdowns with code snippets.

## Workflow

### Phase 1 — Discovery

Scan for existing artifacts first (`find docs/ -name '*.md'`, `ls docs/specs/
docs/adr/ docs/threat-models/`). If specs exist, read them and update against the
current codebase. If none, analyze the code — entry points, route/API handlers,
data models, persistence, external integrations, config/deploy — and extract
constraints from any existing ADRs, threat model, and README.

### Phase 2 — Requirements elicitation

**New features:** clarify (via the `question` tool / `AskUserQuestion`) the goal
and problem, the stakeholders/roles, non-negotiable constraints (performance,
security, compliance), and what's out of scope. **Existing systems:** derive
requirements from the implementation — each endpoint is a functional
requirement, each data model a data requirement, each integration an interface
requirement, each error handler an edge case, each test an acceptance criterion.
**Updates:** diff what the spec says against what the code does; uncovered code
paths become new requirements.

### Phase 3 — Draft

Use [references/srs-template.md](references/srs-template.md), starting with the
RFC 2119 boilerplate. Write requirements in **EARS** syntax
([references/ears-patterns.md](references/ears-patterns.md)):

| Pattern | Template | Use |
|---|---|---|
| Ubiquitous | The `<system>` SHALL `<response>` | Always-active |
| Event-driven | **When** `<trigger>`, the `<system>` SHALL `<response>` | Triggered |
| State-driven | **While** `<precondition>`, the `<system>` SHALL `<response>` | Conditional |
| Optional | **Where** `<feature>`, the `<system>` SHALL `<response>` | Feature flags |
| Unwanted | **If** `<condition>`, **then** the `<system>` SHALL `<response>` | Error handling |

Write acceptance criteria in **Gherkin**
([references/gherkin-guide.md](references/gherkin-guide.md)) —
`Given`/`When`/`Then`, using RFC 2119 keywords in the `Then` assertions. Assign
grouped unique IDs: `FR-` (functional), `NFR-` (non-functional), `IR-`
(interface), `DR-` (data).

### Phase 4 — Cross-reference

Trace every technology choice to an ADR and every security-relevant requirement
to a threat, inline under the requirement:

```markdown
## FR-003: Session Storage
The system SHALL store user sessions in Redis with a 30-day TTL.
- Rationale: [ADR-002: Use Redis for Sessions](../adr/0002-use-redis-for-sessions.md)
- Threat: [TM-AUTH-003: Session Hijacking](../threat-models/auth-threat-model.md#tm-auth-003)
```

If an ADR or threat-model entry doesn't exist yet, flag it inline (`> Missing
ADR: run adr-create` / `> Missing threat-model entry: run threat-model-create`).

### Phase 5 — Validate

Build a Requirements Traceability Matrix
([references/traceability-matrix.md](references/traceability-matrix.md)) mapping
each requirement → test case → ADR → threat model → status. **Empty cells in
critical columns are gaps.** Then check: every requirement has a unique ID and
correct RFC 2119 keywords; follows an EARS pattern; functional requirements have
Gherkin criteria; security requirements trace to threats; architectural choices
trace to ADRs; no vague terms ("fast", "user-friendly", "secure"); NFRs have
measurable thresholds.

## Implementation tracking

Specs use `### Task N:` sections with `**File:**` markers pointing at the
implementation file (and optional `**Test File:**`). A completion-checking skill
(e.g. `iterate` via its `hooks.json` checker) verifies those files exist —
missing implementation files are a P1 gap, missing test files a P2 gap. Keep the
markers accurate (update them if code moves).

## Updating existing specs

Read the current spec and map its IDs; scan for uncovered functionality; add new
requirements with the next IDs (never renumber); mark removed ones `[DEPRECATED]`
rather than deleting; refresh the traceability matrix and `**File:**` markers;
add a changelog entry at the bottom.

## Style

Requirements are formal (RFC 2119 keywords), but context, rationale, and
descriptions should read naturally — "the system SHALL let users log in", not
"the system shall enable user interaction". Don't make unsubstantiated
completeness claims; state what you analyzed and what remains unexamined.

## Resources

- [references/srs-template.md](references/srs-template.md) — full SRS structure
- [references/ears-patterns.md](references/ears-patterns.md) — requirement syntax
- [references/gherkin-guide.md](references/gherkin-guide.md) — acceptance-criteria format
- [references/traceability-matrix.md](references/traceability-matrix.md) — RTM template
- [assets/spec-template.md](assets/spec-template.md) — copy-paste starter
