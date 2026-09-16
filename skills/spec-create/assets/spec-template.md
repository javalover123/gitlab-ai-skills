# [System/Feature Name] — Implementation Specification

**Version:** 0.1.0
**Date:** YYYY-MM-DD
**Author:** [Name]
**Status:** Draft

## RFC 2119 Compliance

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

## 1. Introduction

### 1.1 Purpose

[What this spec covers and who it's for.]

### 1.2 Scope

[What's in scope. What's explicitly out of scope.]

### 1.3 Definitions

| Term | Definition |
|---|---|
| [Term] | [Definition] |

### 1.4 References

- ADRs: [links]
- Threat Model: [link]
- External Standards: [links]

## 2. System Overview

### 2.1 Context

[Where this fits. Include a diagram if it helps.]

### 2.2 Stakeholders

| Role | Concern |
|---|---|
| [Role] | [What they care about] |

### 2.3 Constraints

[Technical, business, regulatory constraints.]

### 2.4 Assumptions

[What you're assuming. Each is a risk if wrong.]

## 3. Functional Requirements

### FR-001: [Requirement Title]

**Priority:** Must Have

[EARS-syntax requirement statement using RFC 2119 keywords.]

**Acceptance Criteria:**

```gherkin
Scenario: [Name]
  Given [precondition]
  When [action]
  Then [expected result]
```

**Traces:**
- ADR: [link]
- Threat: [link]
- Test: [test case ID]

## 4. Non-Functional Requirements

### NFR-001: [Requirement Title]

[Measurable requirement with specific threshold.]

## 5. Interface Requirements

### IR-001: [Interface Title]

[API contracts, message formats, protocols.]

## 6. Data Requirements

### DR-001: [Data Requirement Title]

[Schema, retention, migration needs.]

## 7. Use Cases

### UC-001: [Use Case Title]

- **Actor:** [Who]
- **Goal:** [What they want]
- **Preconditions:** [What must be true]
- **Main Success Scenario:**
  1. [Step]
  2. [Step]
- **Extensions:**
  1a. [Alternate path]

## 8. Tech Stack

| Component | Technology | Version | ADR |
|---|---|---|---|
| [Component] | [Tech] | [Version] | [ADR link] |

## 9. Definition of Done

- [ ] Code complete and compiles
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Security scan passing

## 10. Traceability Matrix

| Req ID | Description | Test Case | ADR | Threat | Status |
|---|---|---|---|---|---|
| FR-001 | [desc] | [TC-ID] | [ADR-ID] | [TM-ID] | [status] |

## 11. Open Issues

| ID | Issue | Owner | Due | Status |
|---|---|---|---|---|
| OI-001 | [description] | [name] | [date] | Open |

## Changelog

| Date | Version | Author | Changes |
|---|---|---|---|
| YYYY-MM-DD | 0.1.0 | [name] | Initial draft |
