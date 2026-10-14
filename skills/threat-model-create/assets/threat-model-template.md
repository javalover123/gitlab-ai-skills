# [System Name] — Threat Model

**Version:** 0.1.0
**Date:** YYYY-MM-DD
**Author:** [Name]
**Status:** Draft | Reviewed | Approved

## 1. System Description

[Brief description of what the system does and its purpose.]

## 2. System Decomposition

### 2.1 External Entities

| ID | Name | Description | Trust Level |
|---|---|---|---|
| EU-1 | [name] | [description] | [Untrusted/Partial/Trusted] |

### 2.2 Processes

| ID | Name | Description | Technology |
|---|---|---|---|
| P-1 | [name] | [description] | [tech stack] |

### 2.3 Data Stores

| ID | Name | Contents | Sensitivity |
|---|---|---|---|
| DS-1 | [name] | [what's stored] | [Public/Internal/Confidential/Restricted] |

### 2.4 Data Flows

| ID | From | To | Data | Protocol | Encrypted | Crosses Boundary |
|---|---|---|---|---|---|---|
| DF-1 | [source] | [dest] | [what] | [HTTP/gRPC/SQL] | [Yes/No] | [boundary ID] |

### 2.5 Trust Boundaries

| ID | Boundary | Between | Controls |
|---|---|---|---|
| TB-1 | [name] | [side A] ↔ [side B] | [what controls exist] |

## 3. Threat Identification (STRIDE)

### TM-[COMPONENT]-001: [Threat Title]

**Element:** [DFD element]
**Category:** [Spoofing | Tampering | Repudiation | Information Disclosure | DoS | Elevation of Privilege]
**Description:** [Specific threat description]
**Attack Vector:** [How an attacker would exploit this]
**Affected Assets:** [What's at risk]
**DREAD Score:** D:_ R:_ E:_ A:_ D:_ = **_ ([Severity])**
**Mitigation:** [What to do about it]
**Status:** Not Started | In Progress | Implemented | Verified | Accepted
**Spec Requirement:** [FR-XXX or "Needed"]
**ADR:** [ADR-NNNN or "Needed"]

## 4. Risk Summary

| Severity | Count | Status |
|---|---|---|
| Critical | _ | _ mitigated, _ in progress, _ not started |
| High | _ | _ mitigated, _ in progress, _ not started |
| Medium | _ | _ mitigated, _ in progress, _ not started |
| Low | _ | _ mitigated, _ in progress, _ not started |

## 5. Assumptions

| ID | Assumption | Risk if Wrong |
|---|---|---|
| A-1 | [assumption] | [consequence] |

## 6. Residual Risk

[Risks that remain after mitigations are applied. Document what's been accepted and why.]

## 7. Changelog

| Date | Version | Author | Changes |
|---|---|---|---|
| YYYY-MM-DD | 0.1.0 | [name] | Initial threat model |
