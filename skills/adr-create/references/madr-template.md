# MADR 4.0.0 Template — Full Version

This is the complete Markdown Architectural Decision Record template. All sections below "Decision Outcome" are optional — include them when they add value.

## Template

```markdown
---
status: {proposed | accepted | rejected | deprecated | superseded by ADR-NNNN}
date: YYYY-MM-DD
decision-makers: [list of people involved in the decision]
consulted: [list of people whose opinions were sought (RACI: Consulted)]
informed: [list of people who are kept up-to-date (RACI: Informed)]
---

# ADR-NNNN: [Short Title as Noun Phrase]

## Context and Problem Statement

[Describe the context and problem that motivates this decision. This section
should be value-neutral — describe forces at play without jumping to conclusions.
2-6 sentences.]

## Decision Drivers

- [Driver 1 — a force, concern, or constraint that influences the decision]
- [Driver 2]
- [Driver 3]
- [Driver 4]

## Considered Options

1. [Option 1 — title]
2. [Option 2 — title]
3. [Option 3 — title (if applicable)]

## Decision Outcome

Chosen option: "[Option N]", because [justification that connects back to
decision drivers. 1-4 sentences.]

### Consequences

**Good:**
- [Positive outcome or quality attribute improvement]
- [Another benefit]

**Bad:**
- [Negative outcome or quality attribute trade-off]
- [Risk accepted]

**Neutral:**
- [Side effect that is neither positive nor negative]

## Confirmation

[Describe how you'll verify the decision is correctly implemented.
Examples: code review checklist item, architectural fitness function,
specific test, metric threshold.]

## Pros and Cons of the Options

### [Option 1]

[1-2 sentence description of what this option entails.]

- **Good**, because [advantage]
- **Good**, because [advantage]
- **Bad**, because [disadvantage]
- **Neutral**, because [observation]

### [Option 2]

[1-2 sentence description.]

- **Good**, because [advantage]
- **Bad**, because [disadvantage]
- **Bad**, because [disadvantage]

## More Information

[Links to related ADRs, spec requirements, threat model entries,
meeting notes, spike results, benchmarks, or other evidence.

For cross-referencing:
- Spec: [SPEC-XXX](../specs/feature-spec.md#fr-xxx)
- Threat Model: [TM-XXX](../threat-models/system-tm.md#tm-xxx)
- Supersedes: [ADR-NNNN](NNNN-title.md)
- Related: [ADR-MMMM](MMMM-title.md)

If retroactively documented: "Decision originally made [date/context].
Retroactively documented on [today's date]."]
```

## Section Notes

**Context and Problem Statement** is the most important section after the decision itself. Without good context, future readers can't evaluate whether the decision still makes sense. Describe the situation as it was when the decision was being made, not as it is now.

**Decision Drivers** make explicit what's usually implicit. They're the criteria you used to evaluate options. Listing them up front makes the decision auditable — someone can check whether the drivers still hold.

**Consequences** must include bad ones. Every decision has trade-offs. If you can't articulate a downside, you haven't thought hard enough. Common bad consequences: increased complexity, maintenance burden, vendor lock-in, performance overhead, learning curve.

**Confirmation** is underused but valuable. It turns the ADR from a document into a commitment — here's how we'll know if we actually followed through.

**Pros and Cons** section gives detailed analysis. The "Decision Outcome" section states the choice; this section shows the work. Readers who agree with the outcome can skip it. Readers who want to challenge it will dig in here.

**More Information** is your catch-all for links, evidence, and cross-references. It's where you tie this ADR to specs, threat model entries, and other ADRs. For retroactive ADRs, note the original decision date here.

## Naming Conventions

**File names:** `NNNN-brief-kebab-case-title.md`
- Use zero-padded 4-digit numbers: `0001`, `0002`, ..., `0042`
- Keep the title part under 60 chars
- Use hyphens, not underscores
- Match the title to the heading inside the file

**Titles:** Short noun phrases, not sentences
- Good: "Use PostgreSQL for User Data"
- Good: "API Authentication via JWT"
- Bad: "We decided to use PostgreSQL because it supports JSONB"
- Bad: "Authentication"

**Numbering:** Sequential, never reused. If ADR-0005 is superseded, the next ADR is still 0006, not a new 0005.
