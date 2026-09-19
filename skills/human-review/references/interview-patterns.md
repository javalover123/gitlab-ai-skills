# Interview Patterns — using AskUserQuestion effectively

The `AskUserQuestion` tool's contract is tight: 1-4 questions per call,
each with 2-4 options, an automatic "Other" option appended by the
tool itself, and an optional `preview` field for visual comparisons.

This reference covers how to use that contract well.

## One item per call (default)

For unrelated parked items, present them in separate `AskUserQuestion`
calls. Each call gets one item with its context bundle in the
preceding prose. Batching unrelated items collapses the context and
makes any one decision easy to mis-make.

### Worked example

Suppose `.bug-burndown/<id>/queue.jsonl` has two `needs_human` entries:

- `BUG-0042` — a panic in `crates/auth/src/jwt.rs` that the subagent
  couldn't reproduce after 3 attempts
- `BUG-0091` — a spec-drift finding where the spec says HS256 but
  ADR-005 says ES256

These aren't coupled. Two `AskUserQuestion` calls, one per bug, with
each bug's context bundle rendered as prose before the call.

## Coupled items — present together

When two items are coupled (cross-scope partners, shared `pattern_id`,
or one's resolution affects the other's framing), bundle them into one
call with up to 4 questions.

### Coupling signals

| Signal | Source |
|---|---|
| `cross_scope_partner: [<id>]` in either entry's `raw` field | iteratotron Phase 4a |
| Same `pattern_id` in both entries | bug-burndown Phase 4c |
| `blocked_by: [<id>]` linkage in either entry | iteratotron Phase 5 or bug-burndown Phase 5 |
| Manual flag from a prior decision record naming the related item | human-review prior session |

When coupling's present, the first question asks about the "anchor"
item (the higher-priority one or the one cited as `blocked_by`), then
the follow-up question(s) ask about the dependent items with options
phrased relative to the anchor's possible outcomes.

## Question phrasing — the four parts

Every question follows this shape:

```
question: "How should <item_id> (<short title>) be resolved?"
header:   "<≤12 chars>"
options:  [...]
multiSelect: false   (always false for resolution decisions — they're mutually exclusive)
```

### The `header` field

Max 12 characters, displayed as a chip/tag in the UI. Use the item ID
when short enough (`BUG-0042`, `SCOPE-AUTH`), or a 1-2 word descriptor
otherwise (`Auth JWT`, `JS Driver`).

### The `question` field

End it with `?`. Name the item. Don't ask vague questions like "what
do you want to do?" — name what kind of decision this is:

| Bad | Good |
|---|---|
| "What now?" | "How should BUG-0042 (panic in jwt.rs) be resolved?" |
| "Pick an option" | "Which design should SCOPE-AUTH adopt to resolve TM-AUTH-003?" |
| "Decision needed" | "Where should the cross-crate API boundary for SCOPE-DB sit?" |

### The `options` array

Each option has:

- `label` — 1-5 words. Action verb first. The recommended option ends with `(Recommended)`.
- `description` — citation + next action + trade-off. Aim for 60-200 chars.
- `preview` — optional, single-select only. Use for visual diffs.

### Recommended-first convention

The first option in the array is the one with "(Recommended)" in its
label. Don't shuffle the order for visual variety — the UI relies on
position.

## Option labels — verb-first

The label should start with an action verb so the user can read it
quickly:

| Bad | Good |
|---|---|
| "FR-12 alignment" | "Adopt FR-12 framing (Recommended)" |
| "Defer" | "Defer to milestone M2" |
| "Don't fix" | "Reject as won't-fix" |
| "Investigate" | "Investigate circuit breaker trigger" |

## Description content — citation + action + trade-off

The description gives the human enough context to choose without
re-reading the underlying artefact. The pattern:

```
<artefact citation>. <next concrete action>. <one-phrase trade-off>.
```

### Worked example

Item: `SCOPE-AUTH-jwt` — `needs_human` because the spec says HS256 but
ADR-005 says ES256.

```yaml
- label: "Adopt ES256 per ADR-005 (Recommended)"
  description: |
    Aligns with accepted ADR-005. Re-queue with note to subagent:
    update spec FR-AUTH-12 to ES256 before implementing. Trade-off:
    spec FR-AUTH-12 needs a follow-up edit.

- label: "Adopt HS256 per spec FR-12"
  description: |
    Honours spec FR-AUTH-12 as written. Would require superseding
    ADR-005 (currently accepted). Trade-off: ADR supersession + new
    threat-model entry for HS256 key rotation.

- label: "Defer to ADR review session"
  description: |
    Mark blocked with reason "ADR vs spec contradiction". Schedule
    a /adr-review on ADR-005 + /spec-review on FR-AUTH-12. Trade-off:
    blocks dispatch until artefacts reconcile.

- label: "Reject as won't-fix"
  description: |
    The JWT path is being removed entirely per epic E-AUTH-2; the
    contradiction won't matter post-removal. Trade-off: requires
    confirming E-AUTH-2 is still active.
```

## Preview field — when to use it

The `preview` field renders monospace markdown next to the option list.
Use it when the human really benefits from seeing the shapes side-by-side:

- Two competing code snippets (different impl strategies)
- Two competing API signatures
- Two diff fragments showing what changes
- Two config layouts

Don't use previews for preference questions where labels and
descriptions already convey the difference.

### Preview example

```yaml
- label: "Adopt builder pattern (Recommended)"
  description: "Aligns with ADR-007 (builder-first APIs)..."
  preview: |
    let session = SessionBuilder::new()
        .with_timeout(30)
        .with_retries(3)
        .build()?;

- label: "Adopt config-struct pattern"
  description: "Matches existing config.rs style..."
  preview: |
    let config = SessionConfig {
        timeout: 30,
        retries: 3,
        ..Default::default()
    };
    let session = Session::new(config)?;
```

Previews are single-select only. The tool refuses them on
`multiSelect: true`.

## Multi-question calls — when coupling justifies it

For coupled items, one call with 2-4 questions in sequence works well:

```
questions:
  - header:   "AUTH-jwt"
    question: "How should SCOPE-AUTH-jwt resolve TM-AUTH-003 contradiction?"
    options:  [...]
    multiSelect: false
  - header:   "AUTH-cli"
    question: "Given the SCOPE-AUTH-jwt decision, how should the dependent SCOPE-AUTH-cli proceed?"
    options:  [
      label: "Adopt anchor's framing (Recommended)",
      label: "Diverge for CLI-specific reasons",
      ...
    ]
    multiSelect: false
```

The second question's options can reference "the anchor decision" — the
user has just made it, so the reference is meaningful.

## Handling "Other" responses

When the user picks "Other" and supplies free-form text:

- Capture their exact words in the decision record's `Rationale` field
- Don't paraphrase
- If their text suggests a status that's not in `ALLOWED_NEW_STATUSES` in `update-queue-status.py`, surface the mismatch and ask a follow-up question with the constrained set
- If their text suggests "investigate further", default to `re-evaluate` status

## What NOT to ask

Never ask:

- "Should I proceed?" — the user invoked /human-review to proceed. Just present the options.
- "Are you sure?" — you already asked the substantive question; nagging is friction
- "Is this option okay?" — you're already presenting it as recommended, that IS the okay signal
- Procedural meta-questions about the skill itself — those go in the SKILL.md prose, not interviews

The `AskUserQuestion` tool is for substantive decisions, not for
confirming you understood the previous one.

## Pacing — typical session shape

For a session with 8 parked items:

- 6 single-item questions (2-3 minutes each)
- 1 coupled-item question covering 2 items (4-5 minutes)
- Total: 8 items resolved in ~20-25 minutes

If the queue's > 30 items, the circuit breaker fires; split across
sessions. Decision fatigue degrades the per-item quality and the
later items end up with worse outcomes than the early ones.
