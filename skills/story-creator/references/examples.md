# Story Examples

## Example 1: Human Actor — CVE Dashboard Filter

**Context:** Security analyst needs to filter vulnerability findings by severity.

```markdown
# Story: CVE Dashboard — Filter by Severity

**Story ID:** STORY-001
**Status:** Draft
**Created:** 2026-03-15
**Actor type:** Human

## Statement

As a security analyst, I want to filter open CVEs by severity level,
so that I can focus remediation work on the highest-risk vulnerabilities first.

## Trigger

User applies a severity filter on the CVE dashboard.

## Acceptance Criteria

### Scenario: Filter to critical severity

```gherkin
Given the dashboard shows open CVEs across multiple severity levels
When the analyst selects "Critical" from the severity filter
Then only CVEs with CVSS score >= 9.0 are displayed
And the displayed count updates to reflect the filter
```

### Scenario: No results match the filter

```gherkin
Given the current scan contains no critical CVEs
When the analyst selects "Critical" from the severity filter
Then an empty state message reads "No critical CVEs found in current scan"
And the filter remains active
```

### Scenario: Stale scan data

```gherkin
Given the last scan completed more than 24 hours ago
When the analyst loads the CVE dashboard
Then a banner displays "Scan data is [N]+ hours old"
```

## EARS Constraints

- The dashboard shall display scan age whenever data is older than 1 hour.
- When a filter is applied, the URL shall update to reflect the filter state.
- If the vulnerability database is unreachable, the system shall show cached results with a staleness warning.

## Security Mapping

| Threat Category | Addressed By |
|---|---|
| Information Disclosure | CVE access requires authenticated session (STORY-000 dependency) |

## Dependencies

- Depends on: STORY-000 (authentication)
- Related spec requirement: FR-012
```

**What makes this work:** The "so that" clause is concrete — "focus remediation" is something a real analyst would care about. Each scenario has a specific observable outcome, not an internal state change. The EARS constraints cover what happens when things go wrong. Authentication is explicitly out-of-scope with a reference.

---

## Example 2: Agent Actor — SBOM Scanner

**Context:** An AI agent scans repositories and writes SBOMs to a graph database.

```markdown
# Story: SBOM Scanner Agent — Dependency Inventory

**Story ID:** STORY-042
**Status:** Draft
**Created:** 2026-03-15
**Actor type:** Agent

## Statement

As an SBOM Scanner Agent with dependency analysis capability,
I need access to a repository URL, a valid GitLab token for private repos,
SurrealDB write credentials, and SCVS BOM-3 compliance requirements,
to produce a complete transitive dependency inventory for the repository,
so that the audit dashboard can show current SBOM coverage without manual scanning.

## Trigger

Agent receives a ZeroMQ ScanRequest message containing repo_url and job_id.

## Context Package

- Data: repository URL, optional GitLab auth token, package manifest files
- Tools: git clone, cargo metadata / npm list / pip show (auto-detect)
- Standards: SCVS BOM-3 (all transitive dependencies), SPDX 2.3 SBOM format
- Constraints: 5-minute scan timeout, no network access except to target repo

## Acceptance Criteria

### Scenario: Successful scan of public repository

```gherkin
Given the agent receives a ScanRequest with a valid public repository URL
When the agent completes dependency analysis
Then an SPDX-format SBOM is written to the SurrealDB graph under the job_id
And the SBOM includes all direct and transitive dependencies
And the agent publishes a ScanComplete event with the SBOM record ID
```

### Scenario: Authentication required for private repository

```gherkin
Given the ScanRequest includes a repository requiring authentication
And the request does not include a GitLab token
When the agent attempts to clone the repository
Then the agent publishes a ScanFailed event with code "AUTH_REQUIRED"
And no partial data is written to the graph
```

### Scenario: Scan timeout

```gherkin
Given the agent has been processing a scan for 4 minutes and 55 seconds
When the 5-minute timeout triggers
Then the agent publishes a ScanTimeout event with job_id and elapsed_seconds
And any partial graph writes are rolled back
```

## EARS Constraints

- While processing a scan, the agent shall not accept new ScanRequest messages.
- If a GitLab token appears in any log output, the agent shall halt immediately and emit a SecurityViolation event.
- The agent shall complete scanning within 300 seconds or emit a ScanTimeout event.
- If the SurrealDB write fails, the agent shall retry up to 2 times before emitting ScanFailed.

## Autonomy Limits

- Maximum actions per cycle: 1 repository scan
- Escalation threshold: 3 consecutive scan failures on different repositories
- Prohibited actions: writing to any graph table other than sbom_records; modifying existing scan records; logging credential values
- Human oversight required: Yes — when SecurityViolation is emitted

## Security Mapping

| Threat Category | Addressed By |
|---|---|
| Spoofing | CURVE authentication on ZeroMQ socket (STORY-001 dependency) |
| Tampering | SurrealDB write uses authenticated session with scoped credentials |
| Repudiation | ScanComplete/ScanFailed events logged with job_id and timestamp |
| Information Disclosure | GitLab tokens logged → halt scenario in EARS constraints |
| Denial of Service | 5-minute timeout + single-job-per-cycle limit |
| Elevation of Privilege | Agent credentials scoped to sbom_records table only |

## Standards Mapping

- SLSA Level: N/A (agent is a consumer, not producer of build artifacts)
- SSDF Practices: PW.4 (automated testing), RV.1 (incident response for SecurityViolation)
- SCVS Controls: BOM-1, BOM-3 (complete transitive inventory requirement)

## Dependencies

- Depends on: STORY-001 (ZeroMQ channel authentication)
- Related ADR: ADR-0012 (SBOM format selection — SPDX vs CycloneDX)
```

**What makes this work:** The context package tells the agent exactly what it needs. Prohibited actions are explicit, not vague. The security mapping addresses all six STRIDE categories because this story crosses multiple trust boundaries. The "so that" clause is testable — you can verify the dashboard shows SBOM coverage.

---

## Example 3: Job Story — Nightly Dependency Refresh

**Context:** Scheduled background process, no clear "who".

```markdown
# Story: Nightly Dependency Vulnerability Rescan

**Story ID:** STORY-055
**Status:** Draft
**Created:** 2026-03-15
**Actor type:** Scheduled

## Statement

When the nightly schedule triggers at 02:00 UTC,
I want a full rescan of all monitored repositories' dependencies,
so I can ensure the vulnerability dashboard reflects the current threat landscape by the start of the business day.

## Trigger

Scheduled cron job at 02:00 UTC daily.

## Acceptance Criteria

### Scenario: Successful nightly rescan

```gherkin
Given the system has 47 monitored repositories with SBOM records older than 12 hours
When the nightly scan job triggers at 02:00 UTC
Then a ScanRequest is queued for each monitored repository
And all queued scans complete before 06:00 UTC
And the dashboard reflects updated CVE counts by 06:30 UTC
```

### Scenario: Scan queue backlog from previous run

```gherkin
Given 12 scan jobs from the previous night are still in progress at 02:00 UTC
When the nightly scan job triggers
Then the scheduler logs a BacklogWarning with the count of pending jobs
And new scan requests are NOT queued for repositories already being scanned
```

## EARS Constraints

- The scan scheduler shall not queue more than 50 concurrent scan jobs.
- If any scan job fails 3 consecutive nightly scans, the scheduler shall emit a PersistentFailureAlert.
- The scheduler shall complete queue population within 60 seconds of trigger time.
```

**What makes this work:** Job Stories skip the forced persona ("As a system administrator...") and get straight to the triggering condition. The outcome — "reflects current threat landscape by start of business day" — is something a real stakeholder would want.
