---
name: story-creator
description: "Creates formal E2E user stories with BDD acceptance criteria, EARS constraints, and INVEST compliance through interactive user prompting. Use when creating new feature stories, documenting agent behaviors, writing acceptance criteria for multi-agent systems, or starting a new feature that needs behavioral verification coverage. Triggers: write user story, create story, BDD story, acceptance criteria, feature story, E2E behavior, agent story, INVEST story, Gherkin story."
version: 1.0.1
license: MIT
category: Documentation
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# Story Creator

Turn vague feature ideas into precise, testable user stories. You answer
questions interactively; the skill assembles a story that satisfies INVEST,
carries Gherkin acceptance criteria and EARS constraints, and maps to whatever
verification standard the project uses (SLSA, SSDF, SCVS, or none). Built for
multi-agent systems where autonomy boundaries matter, but works for plain web
features too. Output goes to `docs/stories/STORY-NNN-[kebab-title].md`.

## When to use

- Starting a feature that needs formal behavioral verification.
- Documenting multi-agent behaviors where autonomy boundaries matter.
- Before test-first development — the story is the spec that drives the failing tests.
- When a project has implementation code but no behavioral stories.
- When a story review (`story-reviewer`, if available in your skillset —
  it doesn't ship in this repository's catalog as of this writing) flags a
  story as incomplete and it needs a rewrite.

## Workflow

Interactive throughout — ask with the `question` tool (opencode) /
`AskUserQuestion` (Claude Code); don't guess the answers.

### Stage 0 — Gap analysis

Scan the project to surface candidate stories before writing: existing stories
(`docs/stories/`), spec requirements (`grep '^## FR-\|^## NFR-' docs/specs/`),
threat-model entries and mitigations, ADRs (decisions imply behaviors), and
source directories with no story coverage. Derive a candidate per gap (an
unlinked `FR-NNN`, a mitigation with no security flow, an ADR behavioral
contract, an uncovered subsystem, a trust-boundary crossing) and let the user
pick which to write. If they already described one, use that as context but
still run the scan for Stage 4 cross-referencing. Greenfield project → skip to
Stage 1 and note there are no spec cross-references yet.

### Stage 1 — Context

Establish the primary actor (human role / AI agent / external system / scheduled
job) and the triggering event. For an agent actor, also capture what data it
consumes, what tools it has, and what it must **not** do. Record `actor`,
`actor_type`, `trigger`.

### Stage 2 — Goal

Get a specific goal ("parse the SARIF file and normalize findings into canonical
CVE records", not "process the request") and why it matters, then write the
title and `As a <role>, I want <action>, so that <outcome>.` statement. Validate
the "so that" describes real value, not an echo of the action.

### Stage 3 — Acceptance criteria

Walk each scenario type and write Gherkin (`Given`/`When`/`Then` with measurable
outcomes): the happy path; failure modes (at minimum input-validation failure,
downstream unavailable, timeout/partial); and important boundary conditions
(empty inputs, max payloads, concurrency, rate limits, permissions revoked
mid-operation). **Target 2–4 criteria** — more than four means the story should
split.

### Stage 4 — Constraints

Capture system-level guarantees as EARS invariants (`While <state>, the <Actor>
shall <behavior>`; `If <failure>, then the <Actor> shall <fallback>`; `When
<event>…`; ubiquitous `The <Actor> shall …`). For agents, capture autonomy
limits (max actions per cycle, escalation threshold, prohibited actions). For
security: for each of authn/authz, trust-boundary data, external inputs,
persistent writes, and secrets that the story touches, add a matching acceptance
criterion or EARS constraint, and map to SLSA/SSDF/SCVS if the project uses them.
Detail: [references/security-mapping.md](references/security-mapping.md).

### Stage 5 — INVEST check

Validate Independent / Negotiable / Valuable / Estimable / Small / Testable. If
**Small** fails, split into the smallest value-delivering story plus backlog. If
**Testable** fails, return to Stage 3 and add measurable outcomes.

### Stage 6 — Write the artifact

Assemble into the story format ([assets/story-template.md](assets/story-template.md))
with statement, trigger, Gherkin acceptance criteria, EARS constraints, autonomy
limits (agents), security + standards mapping, and dependencies (depends
on/blocks/related ADR/related spec requirement). Then suggest running a
story-review skill (such as `story-reviewer`, if available in your skillset)
before the story enters a sprint.

Use these **exact** status values so a completion-checking skill (such as
`iterate`, if available in your skillset) can count unfinished stories:

| Status | Meaning | Blocks completion |
|---|---|---|
| `Draft` | Written, not implemented | Yes (P1) |
| `Revision N` | Revised after review, not implemented | Yes (P1) |
| `Implemented` | Criteria coded and tested | No |
| `Complete` | Finished and verified | No |

## Style

Stories should read like a knowledgeable teammate wrote them, not a requirements
generator. The "so that" clause especially should sound like something a real
person cares about — "the scanner agent parses the SARIF file and stores
normalized findings, so the dashboard shows current status without manual data
entry", not "the system shall process the input consistent with the
requirements".

## References

- [references/methodologies.md](references/methodologies.md) — INVEST, Gherkin, EARS, agent stories in depth
- [references/security-mapping.md](references/security-mapping.md) — STRIDE, SLSA, SCVS, SSDF reference
- [references/examples.md](references/examples.md) — worked examples (human, agent, system actors)
- [assets/story-template.md](assets/story-template.md) — blank templates by story type
