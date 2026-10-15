# Triage: review tiers

`scripts/triage.py` picks one tier for the change.
No model decides the tier.

## Tiers

Ordered `low` < `medium` < `high` < `severe`.

| Tier | Meaning | Examples | Human review |
|------|---------|----------|--------------|
| `low` | Cosmetic or mechanical. Cannot change what a reader understands or does. | Typos, grammar, punctuation, link and anchor fixes, formatting, list markers, front matter edits, reordering without rewording, removing an expired redirect | None required. A correctness pass still runs. |
| `medium` | Prose that changes meaning, but does not define how to use or configure a feature. | Concept rewording, new or expanded examples, notes, a new topic, a renamed heading, a changed code block, a non-reference table | Any team member |
| `high` | Defines how readers use or configure a feature, or adds new surface. | A new, deleted, renamed, or moved page; changed steps or prerequisites; reference tables; history, feature flags, availability details; deprecations; changed numbers, versions, commands, or UI labels | A technical writer is recommended and named without a ping |
| `severe` | Any change to a high-impact page, whatever its size. | Legal, privacy, pricing, billing, subscriptions, licensing, release and deprecation announcements, the docs landing page | A technical writer is required and mentioned |

The reader is never cut short. `scope: full` walks every task on each
changed page; its findings can quote any line of a changed page, and those
about old text go to the summary's "Existing issues" list
([scope](findings-schema.md#scope)). No reviewer has a cap on its findings.

**Low tier correctness pass.** A low tier change can still be wrong, so
`low` never means "skip". When the change has fewer than 20 changed docs
lines, `subagents` is `false`: the orchestrator runs the editor inline, in
one pass, and checks that every changed line is still correct (grammar,
spelling, link targets that resolve, no change in meaning). Larger low changes use a subagent as usual.

## First-time docs writer

A person new to the docs gets coaching, and the reader runs in full.
An author with fewer than `first_time_threshold` (default 3) earlier merged
docs MRs is a first-time docs writer. If the check fails, `value` is `null`
and the `source` says why.

When `first_time_writer.value` is true: the reader runs
with `scope: full`; every editor and reader finding has a one-sentence
`why` with the style guide link; and the summary note opens with a short,
friendly orientation of at most three sentences.

## Technical writer

`technical_writer` comes from the config, or else it is the writer who owns
the most changed lines in `CODEOWNERS` at the base revision. Only that writer
is named. Tier `high` names the writer in backticks without a ping
(`` `tw-example` ``). Tier `severe` mentions the writer with `@`
(`@tw-example`).

## Escalation

1. The orchestrator can only raise the tier. Never lower the script's tier.
1. If a reviewer reports a finding that matches a higher-tier signal (for
   example, the low tier pass finds that a "typo fix" changed a command, or
   `facts` finds a contradicted claim), raise the tier, run the full
   reviewers if the inline pass ran, and record `escalated: <old> -> <new>, <reason>` in
   the report. Escalate at most once per run. Pass the new tier to
   `combine_findings.py --tier <tier>` so the summary names or mentions the
   technical writer.
1. A `blocker` finding from any reviewer at the `low` or `medium` tier raises
   the tier to `high`, so a technical writer is named.
1. If `triage.py` fails (exit code 2), use `high`, and say why in the report.
1. Translation files (`doc-locale/`) are tiered like English docs. The
   reviewers check English rules only, so the report asks for a language
   reviewer when the tier is `high` or `severe`.

## Output

```json
{
  "tier": "high",
  "subagents": true,
  "signals": [{"id": "new-page", "tier": "high", "file": "doc/user/project/branch-rules.md",
               "line": null, "detail": "New page."}],
  "reader": {"scope": "full"},
  "first_time_writer": {"value": false, "source": "glab api", "threshold": 3, "merged_docs_mrs": 3},
  "technical_writer": "tw-example",
  "base": "origin/main",
  "head": "HEAD"
}
```

- `subagents` is `false` only for the low tier inline pass.
- `technical_writer`: see [Technical writer](#technical-writer).
- `combine_findings.py` takes the diff from `base` and `head`.
