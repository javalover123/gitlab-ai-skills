# Requirements Traceability Matrix

The RTM connects every requirement to its tests, decisions, and security analysis. Empty cells are gaps that need attention.

## Template

| Req ID | Description | Priority | Test Cases | ADR | Threat Model | Implementation | Status |
|---|---|---|---|---|---|---|---|
| FR-001 | User login | Must Have | TC-001, TC-002 | ADR-002 | TM-AUTH-001 | `src/auth/login.rs` | Done |
| FR-002 | Session expiry | Must Have | TC-003 | ADR-002 | TM-AUTH-003 | `src/auth/session.rs` | In Progress |
| FR-003 | Password reset | Should Have | — | — | — | — | **Not Started** |
| NFR-001 | Response < 200ms | Must Have | TC-PERF-001 | — | — | — | **Untested** |

## How to Read It

**Forward traceability** (left to right): Does every requirement have tests, decisions, and implementation?

**Backward traceability** (right to left): Does every test map to a requirement? Are there orphan tests that validate nothing documented?

## Gap Detection Rules

These gaps need resolution:

| Gap Type | What It Means | Action |
|---|---|---|
| No test case | Requirement isn't verified | Write test cases |
| No ADR for tech choice | Architectural decision undocumented | Run `adr-create` |
| No threat model entry | Security implications unanalyzed | Run `threat-model-create` |
| No implementation | Requirement exists but isn't built | Schedule work |
| Test but no requirement | Orphan test — what does it validate? | Add requirement or remove test |

## Building the Matrix

### Step 1: List all requirements

Pull every `FR-XXX`, `NFR-XXX`, `IR-XXX`, and `DR-XXX` from the spec.

### Step 2: Map test cases

For each requirement, find tests that validate it. Name tests with a traceable convention: `TC-FR-001-01` (test case for FR-001, scenario 1).

### Step 3: Link ADRs

Scan `docs/adr/` for decisions related to each requirement. Technology choices, algorithm selections, and architectural patterns should all have ADRs.

### Step 4: Link threat model entries

Security-relevant requirements (authentication, authorization, data handling, encryption, input validation) should trace to threat model entries with `TM-XXX` IDs.

### Step 5: Identify implementation files

Map each requirement to the source files that implement it. This helps during code review — you can verify the implementation matches the spec.

## Maintenance

Update the RTM whenever you:
- Add a new requirement
- Write or modify tests
- Create a new ADR
- Update the threat model
- Complete implementation of a requirement

The matrix is only useful if it's current. A stale RTM is worse than none — it gives false confidence.
