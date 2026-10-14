# Artifact Status Reference

The completion check script (`scripts/check-completion.py`) cross-references documentation artifacts against the implementation. For the checks to work correctly, use consistent status values in each artifact type. This page documents what the script looks for and what each status means.

## Threat Model Entry Statuses

Each `### TM-XXX-NNN` entry in `docs/threat-models/` must have a `**Status:**` line. The completion script parses these and blocks iteration when mitigations aren't done.

| Status | Meaning | Blocks iteration? |
|---|---|---|
| `**Status:** Not Started` | Mitigation not begun | Yes (P0) |
| `**Status:** ⚠️ **PARTIAL** (details...)` | Some mitigations done, others remain | Yes (P1) |
| `**Status:** ✅ **DESIGNED** — ...` | Architecture decided (ADR exists) but code not written | Yes (P1) |
| `**Status:** ✅ **IMPLEMENTED** (SR-NNN complete, ...)` | Code written, tested, verified | No |

When you implement a threat mitigation, update its `**Status:**` line to `IMPLEMENTED` with the SR reference and verification date. Partial mitigations should list what's done and what remains.

## Story Statuses

Stories use either YAML frontmatter (`status: Draft`) or inline format (`**Status:** Draft`). The script checks both.

| Status | Meaning | Blocks iteration? |
|---|---|---|
| `Draft` | Story written but not yet implemented | Yes (P1) |
| `Revision N` | Story revised but not yet implemented | Yes (P1) |
| `Implemented` | Code written and acceptance criteria verified with tests | No |
| `Complete` / `Done` / `Accepted` / `Shipped` | Fully finished | No |

When you finish implementing a story's acceptance criteria and have passing tests, update its status to `Implemented`. The script counts implemented vs. total stories and reports the gap.

## Security Requirement Statuses

`SECURITY-REQUIREMENTS.md` uses `### SR-NNN:` entries. The script looks for implementation status markers within each entry.

| Status | Meaning | Blocks iteration? |
|---|---|---|
| `Not Started` | Security control not begun | Yes (P0) |
| `Partial` | Some acceptance criteria met, others remain | Yes (P0) |
| `Implemented` / `Complete` | All acceptance criteria verified | No |

## ADR Statuses

ADRs use YAML frontmatter `status:` fields. The script only checks ADRs with `accepted` status for implementation gaps.

| Status | Meaning | Script behavior |
|---|---|---|
| `proposed` | Under discussion | Skipped (not yet decided) |
| `accepted` | Decision made, should be implemented | Checked for implementation files |
| `deprecated` | No longer applies | Skipped |
| `superseded` | Replaced by another ADR | Skipped |

For `accepted` ADRs, the script checks if files referenced in `## Implementation Location` sections actually exist in the codebase. Missing files are flagged as P1 gaps.

## Spec Task Statuses

Specs use `### Task N:` sections with `**File:**` markers pointing to implementation files. The script verifies these files exist.

Missing implementation files referenced by specs are flagged as P1 gaps. Missing test files referenced by `**Test File:**` markers are flagged as P2 gaps.

## Cross-Reference Integrity

The script validates that cross-references between artifacts resolve:
- Stories referencing `ADR-NNNN` → the ADR file must exist
- Stories referencing `TM-XXX-NNN` → the threat entry must exist in the threat model
- Stories referencing `STORY-NNN` as dependencies → the story file must exist

Broken references are flagged as P2 gaps.

## Updating Statuses During Iteration

As you implement features and fix gaps, update the corresponding artifact:

1. **Implement a story** → change its `status:` to `Implemented`
2. **Implement a threat mitigation** → update its `**Status:**` to `✅ **IMPLEMENTED**`
3. **Create a missing file referenced by a spec** → the spec gap auto-resolves
4. **Create a missing ADR** → the cross-reference gap auto-resolves

The completion script re-checks all artifacts on every iteration, so gaps close automatically as you update statuses and create files.
