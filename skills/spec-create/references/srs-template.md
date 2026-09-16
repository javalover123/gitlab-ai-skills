# SRS Document Structure

Based on IEEE 830/29148 with modern adaptations for agile teams.

## Document Outline

````markdown
# [System/Feature Name] — Implementation Specification

**Version:** [SemVer]
**Date:** [YYYY-MM-DD]
**Author:** [Name]
**Status:** Draft | Review | Approved | Superseded

## RFC 2119 Compliance

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in RFC 2119.

## 1. Introduction

### 1.1 Purpose
What this spec covers and who it's for.

### 1.2 Scope
System boundaries — what's in, what's out.

### 1.3 Definitions and Acronyms
Domain terms the reader needs. Don't assume knowledge.

### 1.4 References
- Related ADRs: [list with links]
- Threat Model: [link]
- External standards: [list]

## 2. System Overview

### 2.1 Context
Where this fits in the larger system. Include a context diagram if helpful.

### 2.2 Stakeholders
Who cares about this system and what they care about.

### 2.3 Constraints
Technical, business, regulatory, or resource constraints.

### 2.4 Assumptions
What you're taking for granted. Each assumption is a risk if wrong.

## 3. Functional Requirements

### FR-001: [Requirement Title]
**Priority:** Must Have | Should Have | Could Have | Won't Have (MoSCoW)

[EARS-syntax requirement statement]

**Acceptance Criteria:**
```gherkin
Scenario: [Name]
  Given [precondition]
  When [action]
  Then [expected result]
```

**Traces:**
- ADR: [link if applicable]
- Threat: [link if applicable]
- Test: [test case ID]

### FR-002: [Next Requirement]
[Repeat pattern]

## 4. Non-Functional Requirements

### NFR-001: Performance
The system SHALL respond to API requests within [X]ms at the 95th percentile
under [Y] concurrent users.

### NFR-002: Availability
The system SHALL maintain [X]% uptime measured monthly.

### NFR-003: Security
[Reference threat model entries directly]

### NFR-004: Scalability
[Measurable thresholds, not vague goals]

## 5. Interface Requirements

### IR-001: External APIs
[OpenAPI/Swagger references or inline definitions]

### IR-002: User Interfaces
[Wireframes, component specs, state diagrams]

### IR-003: System Interfaces
[Service-to-service contracts, message formats]

## 6. Data Requirements

### DR-001: Data Models
[Schema definitions, entity relationships]

### DR-002: Data Retention
[How long data lives, archival policies]

### DR-003: Data Migration
[If migrating from existing system]

## 7. Use Cases

For complex workflows, use Cockburn fully-dressed format:

### UC-001: [Use Case Title]
- **Actor:** [Who initiates]
- **Goal:** [What they want to achieve]
- **Preconditions:** [What must be true before starting]
- **Success End Condition:** [What's true when done successfully]
- **Failed End Condition:** [What's true when it fails]
- **Main Success Scenario:**
  1. Actor does X
  2. System responds with Y
  3. Actor confirms Z
  4. System completes action
- **Extensions:**
  2a. System can't find data:
    2a1. System returns 404 with helpful message
    2a2. Actor retries with different parameters
  3a. Actor cancels:
    3a1. System rolls back any partial changes

## 8. Tech Stack and Dependencies

| Component | Technology | Version | ADR |
|---|---|---|---|
| Runtime | Node.js | 20.x | ADR-001 |
| Database | PostgreSQL | 16.x | ADR-002 |
| Cache | Redis | 7.x | ADR-003 |

## 9. Definition of Done

Universal across all work items in this spec:

- [ ] Code complete and compiles
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Security scan passing
- [ ] Deployed to staging and verified

## 10. Traceability Matrix

| Req ID | Description | Test Case | ADR | Threat | Status |
|---|---|---|---|---|---|
| FR-001 | [desc] | TC-001 | ADR-001 | TM-001 | Done |
| FR-002 | [desc] | TC-002 | — | — | In Progress |

## 11. Open Issues

| ID | Issue | Owner | Due | Status |
|---|---|---|---|---|
| OI-001 | [description] | [name] | [date] | Open |

## Changelog

| Date | Version | Author | Changes |
|---|---|---|---|
| YYYY-MM-DD | 0.1.0 | [name] | Initial draft |
````

## Section Guidelines

**Introduction** should be 1-2 paragraphs max. Don't pad it.

**Functional Requirements** are the heart of the doc. Each one needs:
- A unique ID that never changes (even if the requirement is deprecated)
- An EARS-syntax statement with RFC 2119 keywords
- At least one Gherkin acceptance criterion
- Traceability links (ADR, threat model, test case)

**Non-Functional Requirements** must have measurable thresholds. "The system should be fast" is useless. "The system SHALL respond within 200ms at p95" is testable.

**Use Cases** are only needed for complex multi-step workflows. Simple CRUD operations don't need Cockburn format — the Gherkin scenarios on the functional requirements are enough.

**Traceability Matrix** is your gap detector. Empty cells mean something's missing. Review it after every update.
