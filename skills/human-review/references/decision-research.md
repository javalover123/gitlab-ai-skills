# Decision Research — drafting informed options for parked items

This reference covers what happens between Phase 2 (context loaded) and
Phase 4 (interview). The goal is to put 2-4 well-cited, mutually-distinct
resolution options in front of the human, ranked by consistency with the
project's current scope.

## The mental model

You're not the decision-maker. You're the briefing officer. The human
gets to choose, but only as well as the briefing you prepare. A weak
briefing — vague options, missing citations, no trade-off named —
produces a weak decision.

A strong briefing names:

- The artefact each option aligns with (or contradicts)
- The concrete next action the option triggers
- The trade-off that makes the option non-obvious
- The reason the recommended option is recommended

## Option drafting checklist

For each candidate option, work through this list:

- [ ] Does it cite at least one artefact ID? (FR-, ADR-, TM-, story-)
- [ ] Does it name the file path or queue field that changes?
- [ ] Does it name the trade-off?
- [ ] Is it materially different from the other options? (don't pad to fill 4 slots)
- [ ] Does it conflict with an `accepted` ADR? If yes, does the description flag supersession explicitly?
- [ ] Would the option re-introduce a stop-bias pattern (stub, placeholder, `Status: Partial`, deferred annotation)? If yes, drop it.

## Why the recommended option goes first

The `AskUserQuestion` tool convention is that the first option's labelled
"(Recommended)" and that's the one the human's eye lands on first. The
recommended option is the one most consistent with:

- The current session's in-flight work (other queue entries already `queued` or `in_flight`)
- The most recent accepted ADRs on this artefact
- The current branch's direction (recent commits, open MRs)
- The threat model's risk ratings for the affected components

If you can't pick a clear recommendation, that's a signal the item
shouldn't be in this skill yet — it should go through `/spec-review` or
`/adr-review` first. Flag that as a circuit-breaker condition.

## When to delegate research to a subagent

Sometimes the context bundle (Phase 2) is enough — the human can decide
from the artefact excerpts alone. Other times, the option space isn't
obvious and you'd benefit from a cold-context investigation. Spawn an
`Agent` subagent when:

- The item's linked artefact references a pattern from elsewhere in the codebase that you haven't seen
- The item has been through human-review before and the prior decision didn't stick
- The item's `last_error` mentions an external dependency or unfamiliar tool
- The item spans multiple scopes / cross-scope partners and the relationships need mapping

### Subagent prompt template

```
You're an investigator for the human-review skill. Your job:
research the parked item below and return 2-4 candidate resolution
options, each with citations.

ITEM:
  source_skill: <iteratotron|bug-burndown>
  item_id: <id>
  status: <needs_human|requires_human_review>
  kind: <scope.kind|bug.kind>
  title: <title>
  linked_artefacts: [<list>]
  last_error: <short string>

CONTEXT (load these files in this order; stop if you find what you need):
  1. The item's needs_human_dir contents (if non-null)
  2. Each linked artefact in linked_artefacts
  3. Recent commits touching the affected path(s)
  4. Sibling queue entries that are `queued` or `in_flight`

RETURN: a JSON array of 2-4 options, each shaped:
  {
    "label": "<1-5 word action verb>",
    "description": "<60-200 chars: cites artefact id, names next action, names trade-off>",
    "alignment_artefacts": ["<artefact_id1>", ...],
    "next_action_path": "<file path that changes, or queue-field name>",
    "tradeoff": "<one phrase>",
    "supersedes": "<ADR-id if option supersedes an accepted ADR, else null>",
    "reintroduces_stop_bias": false
  }

DO NOT propose an option that:
  - Contradicts an `accepted` ADR without setting supersedes
  - Reintroduces a stop-bias pattern (sets reintroduces_stop_bias to true)
  - Repeats another option's alignment_artefacts + next_action_path tuple

If you can find fewer than 2 distinct options, return what you found
plus the explanation `cannot_find_distinct_options: "<reason>"`.
```

The subagent's return shape converts directly into `AskUserQuestion`
options at Phase 4.

## Consistency with current scope — the four cross-checks

For each candidate option, before locking it in:

| Check | What to verify | If it fails |
|---|---|---|
| In-flight overlap | Does another `queued`/`in_flight` entry touch the same file? | Add `cross_scope_partner` note to the option's description |
| ADR alignment | Does the option contradict an `accepted` ADR? | Flag supersession in the description, or drop the option |
| Threat-model coverage | Does the option affect a path with a `Not Started` or `Partial` mitigation? | Note which SR-NNN the option pre-empts or unblocks |
| Spec FR linkage | Does the option implement, defer, or contradict a spec FR? | Cite the FR-id in the description |

The cross-checks don't all have to pass for an option to be valid — but
the human needs to know which ones didn't. That's what the description
field is for.

## When the artefact's missing entirely

A parked item whose linked artefact doesn't exist tells you the
parent skill's Phase 3a (or equivalent) tagged this for `/all-aboard`
but the bootstrap didn't complete. Don't paper over the gap — surface
it explicitly as an option:

```
label:       "Bootstrap missing artefact via /all-aboard"
description: "TM-AUTH-003 referenced but not found in docs/. Running
              /all-aboard creates it before re-queueing this item.
              Trade-off: blocks dispatch until artefact lands."
```

This option goes alongside the others, not in place of them — the human
might still want to make a provisional call.

## Honesty about uncertainty

The description field is the place to admit when you're guessing. Bad:

> "This option resolves the issue cleanly."

Better:

> "If the subagent re-runs cleanly with the new framing, this finishes
> the scope. If it returns needs_human again, the item's framing itself
> needs rework — surface to /spec-review."

The human is qualified to evaluate that trade-off. Hiding the uncertainty
isn't kindness; it's a lie of omission.
