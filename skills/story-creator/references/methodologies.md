# Story Creation Methodologies

## INVEST Criteria (Bill Wake, 2003)

Each criterion matters, but they pull in different directions sometimes. Here's the practical guidance for each:

**Independent** — The hardest one for multi-agent systems. When two agent stories share infrastructure (a ZeroMQ socket, a shared database table), they aren't truly independent. The mitigation: define interface contracts and stub the dependency. The story tests against the stub; integration tests cover the real interaction.

**Negotiable** — Stories are conversation starters, not contracts. If the acceptance criteria prescribe an implementation ("uses Redis for caching"), that's a sign the story is over-specified. The HOW belongs in an ADR or design discussion, not the story.

**Valuable** — The "so that" clause is the test here. Does it describe a real outcome someone would care about? "So that the system functions correctly" fails. "So that the audit dashboard shows current CVE exposure without manual data entry" passes.

**Estimable** — If you can't scope it, the story is missing something: missing context, missing constraints, or missing acceptance criteria. Don't estimate blind — ask for the missing pieces first.

**Small** — More than 4 acceptance criteria is the smell. Stories with 6+ scenarios are trying to be epics. Split on capability boundaries, not technical layers.

**Testable** — "The system should be fast" fails. "The system shall respond within 500ms at the 95th percentile under 100 concurrent requests" passes. Measurability is non-negotiable.

## Gherkin / BDD

### Step Writing Rules

**Given** establishes state, not actions. If you're writing "Given the user has clicked..." you've started a When by mistake.

**When** describes one triggering action. One. If you need "and" in a When step, split the scenario or reconsider the story boundary.

**Then** describes observable outcomes — things you can assert against. Internal state changes ("the cache was updated") aren't observable unless you expose a way to verify them.

**And / But** are syntactic sugar for compound conditions of the same step type. Use them freely to keep steps readable. Don't use them to smuggle a new Given/When/Then type.

### Scenario Coverage Targets

- 1 happy-path scenario (always)
- 1-2 error/failure scenarios (always, except for trivially safe operations)
- 0-2 boundary/edge cases (for stories with numeric limits, rate constraints, or concurrency)

More than 6 scenarios total → split the story.

### Agent-Specific Gherkin Patterns

For multi-agent stories, the "When" step often describes a message, not a user action:

```gherkin
# Human story
When the user clicks "Run Scan"

# Agent story
When the scanner agent receives a ScanRequest message with job_id "abc123"
When the coordinator agent publishes a TaskComplete event
```

Keep the message schema out of Gherkin — that belongs in the EARS constraints or a contract test. Gherkin describes behavior, not wire format.

## EARS Templates

**Ubiquitous** — `The <system> shall <behavior>.`
Use for invariants that hold regardless of state or event. "The audit log shall be append-only."

**Event-Driven** — `When <trigger>, the <system> shall <response>.`
Use for behaviors triggered by discrete events. "When a ZeroMQ message arrives with an unknown schema, the agent shall log the message and send a NACK."

**State-Driven** — `While <state>, the <system> shall <behavior>.`
Use for continuous constraints during a particular system state. "While processing a scan job, the agent shall not accept new job assignments."

**Optional Feature** — `Where <feature is enabled>, the <system> shall <behavior>.`
Use for feature-flag-controlled behavior. "Where SLSA level 3 is configured, the build system shall produce signed provenance."

**Unwanted Behavior** — `If <condition>, then the <system> shall <fallback>.`
Use for explicit failure handling. "If the upstream API returns a 429, then the agent shall wait 60 seconds before retrying."

## Agent Story Pattern

For stories where the actor is an AI agent, extend the standard format with:

```
As a <Agent Name> with <specific capability>,
I need <precise context: data sources, APIs, constraints, standards>,
to deliver <business-value outcome>,
so that <verification path is clear>.
```

This matters because AI agents need explicit context packages — they can't ask clarifying questions mid-task the way a human developer can. The "precise context" section is the agent's brief.

## Job Stories (Contextual Alternatives)

When the user persona feels forced or artificial, Job Stories work better:

```
When <triggering situation>,
I want <motivation or capability>,
so I can <expected outcome>.
```

Good for: event-driven systems, scheduled jobs, background processes, and any story where "who" matters less than "when" and "why".

## Standards Integration

### SLSA v1.0 Build Track

Map stories to SLSA levels when the story involves build or artifact production:

| Level | Requirement | Story acceptance criterion |
|---|---|---|
| L1 | Provenance exists | System produces signed SLSA provenance for each build |
| L2 | Hosted build, signed provenance | Build runs on hosted CI; provenance is cryptographically signed |
| L3 | Hardened, tamper-resistant provenance | Build runs in isolated environment; provenance is unforgeable |

### OWASP SCVS Controls

Reference SCVS controls when stories involve dependency management, SBOM, or supply chain:

- **BOM generation** → SCVS BOM-3 (component inventory complete)
- **Vulnerability scanning** → SCVS CA-2 (automated component analysis)
- **Dependency pinning** → SCVS PM-1 (package manager lockfiles)

### NIST SSDF (SP 800-218)

Map to SSDF practice groups for security-critical stories:

- **Prepare** (PW) — Secure development environment stories
- **Protect** (PS) — Code integrity and signing stories
- **Produce** (PW) — Testing and review process stories
- **Respond** (RV) — Vulnerability disclosure and response stories
