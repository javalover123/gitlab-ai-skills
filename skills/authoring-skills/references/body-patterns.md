# Body patterns

Distilled from Anthropic's skill-authoring best practices and its skills guide.
Agent-neutral unless marked *(Claude-specific)* or *(Anthropic)*.

## Contents

- Concise by default
- Degrees of freedom
- Defaults over menus
- Workflows and feedback loops
- Templates and examples
- Terminology and time-sensitivity
- Making rules stick
- File layout

## Concise by default

The skill shares the context window with the conversation and every other
loaded skill. For each paragraph ask: does the agent already know this? Does it
justify its token cost? A one-line tool choice plus a snippet beats a
paragraph explaining what the file format is.

## Degrees of freedom

Match specificity to how fragile the task is.

| Freedom | Use when | Form |
|---|---|---|
| High | Many valid approaches, context decides | Prose heuristics, a checklist |
| Medium | A preferred pattern exists, some variation is fine | Template or parameterised script |
| Low | Fragile, consistency critical, order matters | Exact command, "do not add flags" |

Narrow bridge with cliffs → exact steps. Open field → direction and trust.

## Defaults over menus

Name one default and one escape hatch ("Use X. For case Y, use Z instead")
instead of listing five equivalent tools. Menus make the agent stall or pick
arbitrarily.

## Workflows and feedback loops

- Number the steps for multi-step tasks; for long ones, give the agent a
  checklist it can copy and tick off.
- Use **validate → fix → repeat**: run a checker (a script, or a style guide /
  checklist the agent compares against), fix findings, re-run, and proceed only
  when clean.
- For batch or destructive work use **plan → validate → execute → verify**: the
  agent writes a structured plan file, a script checks it with specific error
  messages ("field X not found; available: A, B"), then it is applied.
- Add a conditional branch ("creating new? → …; editing existing? → …") when
  there are distinct paths, rather than one muddled flow.

## Templates and examples

- Give a template for strict output formats; say "adapt as needed" when the
  format is flexible.
- Show 2–3 input → output examples for style-sensitive output (commit messages,
  reports). Concrete examples teach more than descriptions.
- Optional sections worth including when a skill touches tools: *Examples*
  (user says → actions → result) and *Troubleshooting* (error → cause → fix).

## Terminology and time-sensitivity

- One term per concept throughout (always "endpoint", never a mix of
  "URL"/"route"/"path").
- Avoid statements that rot ("before August 2025 use the old API"). State the
  current method; put legacy behaviour in a collapsed "old patterns" block.
- Use forward slashes in every path.

## Making rules stick

When an agent loads the skill but ignores rules, the usual causes are:

1. **Too verbose** — trim, use lists, move depth to references.
2. **Buried** — put critical rules at the top; repeat only the few that matter.
3. **Vague** — replace "validate things properly" with the concrete checks.
4. **Unenforceable in prose** — bundle a script; code is deterministic,
   interpretation is not.

## File layout

- The entry file is exactly `SKILL.md`. Keep agent-facing content in `SKILL.md`
  and `references/`; a `README.md` is for humans and is never auto-loaded.
  *(Anthropic's guide says to omit it; several repo skills ship one for
  maintainers, which is fine.)*
- Link every reference directly from `SKILL.md`. Nested chains
  (SKILL → a.md → b.md) can get partially read *(observed with Claude, which
  previews with `head`)*.
- Add a contents list at the top of any reference longer than ~100 lines.
- Name files by content (`finance-metrics.md`, not `doc2.md`); group by domain
  (`references/finance.md`, `references/sales.md`) so the agent loads only what
  the request needs.
- Size: Anthropic suggests under 500 lines / ~5,000 words; this repo's budget
  (<100 target, 150 ceiling) is stricter and wins.
