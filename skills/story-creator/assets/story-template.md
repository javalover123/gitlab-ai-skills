# Story Templates

## Standard Story Template

````markdown
# Story: [Title]

**Story ID:** STORY-[NNN]
**Status:** Draft
**Created:** [YYYY-MM-DD]
**Actor type:** [Human / Agent / System / Scheduled]

## Statement

As a <role>, I want <action>, so that <outcome>.

## Trigger

<What event or condition initiates this behavior>

## Acceptance Criteria

### Scenario: [Happy path name]

```gherkin
Given <precondition — system state>
When <triggering action>
Then <measurable observable outcome>
```

### Scenario: [Error case name]

```gherkin
Given <precondition>
When <trigger that causes the error>
Then <expected error handling behavior>
```

## EARS Constraints

- The <Actor> shall <ubiquitous invariant>.
- When <event>, the <Actor> shall <response>.
- While <state>, the <Actor> shall <behavior>.
- If <failure condition>, then the <Actor> shall <fallback>.

## Security Mapping

| Threat Category | Addressed By |
|---|---|
| Spoofing | [Scenario or EARS constraint] |
| Tampering | [Scenario or EARS constraint] |
| Repudiation | [Scenario or EARS constraint] |
| Information Disclosure | [Scenario or EARS constraint] |
| Denial of Service | [Scenario or EARS constraint] |
| Elevation of Privilege | [Scenario or EARS constraint] |

## Standards Mapping

- SLSA Level: [1 / 2 / 3 / N/A]
- SSDF Practices: [PS.1, PW.4, etc. / N/A]
- SCVS Controls: [BOM-3, CA-2, etc. / N/A]
- OpenSSF Scorecard: [branch-protection, signed-releases, etc. / N/A]

## Dependencies

- Depends on: [STORY-NNN or none]
- Blocks: [STORY-NNN or none]
- Related ADR: [ADR-NNNN or none]
- Related spec requirement: [FR-NNN or none]
- Related threat model entry: [TM-COMPONENT-NNN or none]

## Notes

[Open questions, negotiation points, out-of-scope items]
````

---

## Agent Story Template (with autonomy limits)

````markdown
# Story: [Agent Name] — [Capability]

**Story ID:** STORY-[NNN]
**Status:** Draft
**Created:** [YYYY-MM-DD]
**Actor type:** Agent

## Statement

As a <Agent Name> with <specific capability>,
I need <precise context: data sources, APIs, constraints, standards>,
to deliver <business-value outcome>,
so that <verification path is clear>.

## Trigger

<Message type, event, or schedule that activates this agent>

## Context Package

The agent requires access to:
- Data: <files, database records, API responses>
- Tools: <available tool list>
- Standards: <SLSA level, SCVS controls, coding standards>
- Constraints: <rate limits, timeouts, scope boundaries>

## Acceptance Criteria

### Scenario: [Normal operation]

```gherkin
Given the agent has received a <MessageType> with valid payload
And <any required upstream state>
When the agent processes the request
Then <measurable outcome 1>
And <measurable outcome 2>
```

### Scenario: [Upstream failure]

```gherkin
Given the agent has received a <MessageType>
When <upstream dependency is unavailable>
Then the agent sends a NACK with error code <code>
And the agent logs the failure with correlation ID
And the agent does not modify any persistent state
```

## EARS Constraints

- While processing a job, the agent shall not accept new job assignments.
- If the upstream API returns a 5xx, then the agent shall retry with exponential backoff up to 3 times.
- The agent shall complete processing within <N> seconds or emit a timeout event.
- If <prohibited condition> occurs, then the agent shall halt and escalate.

## Autonomy Limits

- Maximum actions per cycle: <N>
- Escalation threshold: <specific measurable condition>
- Prohibited actions: <explicit list>
- Human oversight required: [Yes — under what conditions / No]

## Security Mapping

| Threat Category | Addressed By |
|---|---|
| Spoofing | <authentication mechanism or scenario> |
| Tampering | <integrity check or scenario> |
| Repudiation | <audit logging requirement> |
| Information Disclosure | <data handling constraint> |
| Denial of Service | <rate limit or resource constraint> |
| Elevation of Privilege | <scope boundary enforcement> |

## Standards Mapping

- SLSA Level: [N/A for agent stories unless agent produces artifacts]
- SSDF Practices: [relevant practices]
- SCVS Controls: [relevant controls if agent analyzes dependencies]

## Dependencies

- Depends on: [STORY-NNN or none]
- Blocks: [STORY-NNN or none]
- Related ADR: [ADR-NNNN or none]
- Contract tests: [which agent-to-agent interfaces this story validates]

## Notes

[Open questions, behavioral assumptions that need validation]
````

---

## Job Story Template (event-driven, no persona)

````markdown
# Story: [Capability Description]

**Story ID:** STORY-[NNN]
**Status:** Draft
**Created:** [YYYY-MM-DD]
**Actor type:** [Scheduled / Event-driven]

## Statement

When <triggering situation or context>,
I want <motivation or capability>,
so I can <expected outcome>.

## Trigger

<Specific event, schedule, or condition — be precise>

## Acceptance Criteria

[Gherkin scenarios as in standard template]

## EARS Constraints

[EARS invariants as in standard template]

## Notes

[Use this template when the "who" is less important than the "when" and "why"]
````
