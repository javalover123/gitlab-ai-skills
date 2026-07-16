---
name: threat-model-create
description: "Creates and updates threat models using STRIDE-per-element analysis, DREAD risk scoring, and Data Flow Diagram decomposition. Handles new projects, existing systems without threat models, and updating models when implementation changes. Links threats to spec requirements and ADRs for mitigation tracking. Use when creating a threat model, analyzing security threats, performing STRIDE analysis, assessing attack surface, updating a threat model after changes, or when spec-create flags missing security analysis. Triggers: threat model, STRIDE, security analysis, attack surface, identify threats, risk assessment, create threat model."
version: 1.0.0
license: MIT
category: Documentation
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# Threat Model Create

Systematically identify what can go wrong with a system and decide what to do
about it, using STRIDE for threat identification and DREAD for risk scoring,
built on a Data Flow Diagram with explicit trust boundaries. Works for new
designs and for existing systems with no security analysis yet.

A threat model answers four questions: **what are we building?** (decomposition)
**what can go wrong?** (STRIDE) **how bad is it?** (DREAD) **what do we do about
it?** (mitigations). Every threat gets a unique ID (`TM-XXX`), a severity score,
and traces to the spec requirements and ADRs implementing its mitigations. Save
to `docs/threat-models/`.

## When to use

- Designing a new system, or retroactively analyzing one with no threat model.
- Implementation changed and the model needs updating.
- `spec-create` flagged security requirements without threat analysis.
- Preparing for a security review, or a feature adds a new trust boundary / data
  flow / external integration.

For code-level vulnerability scanning use `c-security-review` /
`rust-unsafe-ffi-review` — this skill works at the *architectural* level.

## Workflow

### Phase 1 — System decomposition

Scan entry points, config, and existing docs, then confirm scope (via the
`question` tool / `AskUserQuestion`): new design or retroactive, and which trust
boundaries to focus on. Build a Data Flow Diagram
([references/dfd-construction.md](references/dfd-construction.md)) identifying
**external entities** (users, third-party services, bots), **processes** (API
handlers, workers, auth middleware), **data stores** (DBs, caches, queues,
secrets), **data flows** (HTTP, queries, inter-service, file I/O), and **trust
boundaries** (internet→DMZ→internal, unauth→auth, user→admin, app→DB,
your-code→third-party, container→host). For existing systems derive the DFD from
entry points, route/DB/external-call greps, and infra/Docker config.

### Phase 2 — Threat identification (STRIDE)

Apply STRIDE to each element ([references/stride-guide.md](references/stride-guide.md)):

| Element | S | T | R | I | D | E |
|---|---|---|---|---|---|---|
| External entity | X | | X | | | |
| Process | X | X | X | X | X | X |
| Data store | | X | | X | X | |
| Data flow | | X | | X | X | |

Document each threat as `### TM-[COMPONENT]-NNN` with element, category,
specific description, attack vector, and affected assets. Common threats by
category: Spoofing → credential theft / session hijacking; Tampering → injection
/ request modification; Repudiation → missing audit logs; Info Disclosure → data
leaks / verbose errors / missing encryption; DoS → resource exhaustion /
algorithmic-complexity; Elevation → IDOR / privilege escalation / missing authz.

### Phase 3 — Risk assessment (DREAD)

Score each threat 0–10 on Damage, Reproducibility, Exploitability, Affected
users, Discoverability; **total 0–50**
([references/dread-scoring.md](references/dread-scoring.md)):

| Score | Severity | Response |
|---|---|---|
| 40–50 | Critical | within 72 hours |
| 25–39 | High | within 2 weeks |
| 11–24 | Medium | within 1 month |
| 1–10 | Low | monitor quarterly |

Record as `**DREAD Score:** D:8 R:7 E:6 A:9 D:5 = 35 (High)`.

### Phase 4 — Mitigation planning

Per threat, choose a response: **mitigate** (a control, most common), **accept**
(document why), **transfer** (insurance/SLA/managed service), or **eliminate**
(remove the feature). Standard mitigations by category: Spoofing → MFA / strong
session tokens; Tampering → input validation / integrity hashing; Repudiation →
audit logging / signed transactions; Info Disclosure → encryption at rest+transit
/ access controls; DoS → rate limiting / quotas / circuit breakers; Elevation →
RBAC/ABAC / least privilege / authz at every layer.

Record each mitigation's status with one of these **exact** values so a
completion-checking skill (e.g. `iterate` via its `hooks.json` checker) can track
remaining work:

| Status | Meaning | Blocks completion |
|---|---|---|
| `**Status:** Not Started` | Not begun | Yes (P0) |
| `**Status:** ⚠️ PARTIAL (…)` | Some criteria met | Yes (P1) |
| `**Status:** ✅ DESIGNED — ADR-NNN` | Decided, not coded | Yes (P1) |
| `**Status:** ✅ IMPLEMENTED (SR-NNN, date)` | Coded, tested, verified | No |

Link each to its ADR and spec requirement; update the status as work lands.

### Phase 5 — Cross-reference and validate

Trace every mitigation to a spec requirement and security decisions to ADRs;
flag missing ones inline (`> Missing ADR: run adr-create` / `> Missing spec
requirement: run spec-create`). Validate: every DFD element analyzed against its
applicable STRIDE categories; every trust-boundary crossing documented; every
threat scored; every threat ≥11 has a mitigation; every mitigation traces to a
spec requirement or ADR; assumptions and residual risks acknowledged.

## Updating existing threat models

Read the current model and diff the DFD; add new elements; re-analyze changed
trust boundaries; add new threats with the next `TM-XXX`; re-score and update
statuses where mitigations landed; mark removed attack surface "Eliminated"
rather than deleting; add a changelog entry.

## Style

Threat descriptions must be concrete — "an attacker can steal session tokens by
sniffing unencrypted HTTP" is useful; "security could be compromised" is not.
State what you analyzed and what you didn't; don't claim a model is "complete".

## Resources

- [references/stride-guide.md](references/stride-guide.md) — STRIDE-per-element methodology
- [references/dread-scoring.md](references/dread-scoring.md) — scoring rubric with calibration
- [references/dfd-construction.md](references/dfd-construction.md) — building Data Flow Diagrams
- [assets/threat-model-template.md](assets/threat-model-template.md) — copy-paste starter
