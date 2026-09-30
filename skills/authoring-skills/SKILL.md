---
name: authoring-skills
description: Author a new agent skill or improve an existing one - write the SKILL.md frontmatter and description, structure the body, and fix skills that under- or over-trigger. Use when asked to create/write a skill, make a SKILL.md, improve/refactor a skill, or fix a skill's description.
version: 0.3.0
license: MIT
category: Meta / Authoring
compatibility: opencode
metadata:
  audience: skill-authors
  workflow: local
---

# Authoring Skills

A workflow for writing a new skill or improving an existing one so it triggers
reliably, stays maintainable, and earns its place in context. Grounded in
Anthropic's "Lessons from building Claude Code: how we use skills" (Jun 2026)
and the conventions of well-written skills in this repository.

A skill is a **folder, not just a markdown file**: a `SKILL.md` plus optional
`references/` (load-on-demand markdown), `scripts/` (helpers), and `assets/`
(templates). Treat the whole folder as context engineering.

## When to use

- Turning a repeatable workflow, tool/API reference, verification procedure, or
  review checklist into a reusable skill.
- An existing skill under-triggers (never fires when it should) or over-triggers
  (fires for the wrong tasks) — usually a `description` problem.
- A `SKILL.md` has grown unwieldy and needs splitting into `references/`.

## When NOT to use

- The behaviour is a one-off — that belongs in a note, not a skill.
- The content just restates what the model already does well (see Anti-patterns).

## Step 0 — Is a skill the right vessel?

1. **Does it fit cleanly in one category?** The best skills fit one job; ones
   that straddle several confuse the agent. If your idea spans two, split it.
   See [references/skill-types.md](references/skill-types.md) for the nine-category
   taxonomy and a "which bucket?" decision aid.
2. **Does it push the model off its defaults?** If not, write nothing.
3. **Will it be reused?** One-off → note. Reused → skill.

## Step 1 — Write the description first (the discovery trigger)

The agent scans every skill's `description` to decide "is there a skill for this
request?" It is **not a summary — it is a description of *when to trigger*.**
Write it for the model: lead with the literal phrases a user would type,
enumerate the situations it covers, add a boundary clause if a sibling skill
could also match, keep it third-person present.

Litmus test: read *only* the description and predict which prompts fire it. If
you can't, neither can the agent — iterate before touching the body. Patterns,
worked before/after examples, and the full test are in
[references/descriptions.md](references/descriptions.md).

## Step 2 — Choose the body shape

Pick the smallest archetype that fits; grow it later (most good skills start as
a few lines and one gotcha):

| Archetype | Use for | Representative example |
|---|---|---|
| **Inline technique** (<80 lines, no subfolders) | A single self-contained procedure | `write-large-file` |
| **Phase / reference-table workflow** | A multi-step process where each step has depth | `gitlab-babysit-mr` |
| **Deep reference + guardrails** | A tool/API with many footguns, budgets, caveats | `glab` |

Don't pre-build a `references/` tree you don't yet need.

## Step 3 — Write the body

1. Open with one or two sentences on what the skill does and what it assumes.
2. **Lead with the gotchas** — the highest-signal content is what the agent gets
   wrong by default. Prefer concrete "X is actually Y" facts over generic advice;
   grow this section as new edge cases surface.
3. **Don't railroad.** Give facts and constraints, not a rigid transcript, unless
   order genuinely matters (destructive/safety steps).
4. **Store scripts; let the agent compose.** Ship helpers for boilerplate so the
   agent spends turns deciding what to do, not rebuilding scaffolding. Reference
   them by path relative to the skill root and say so.
5. End with an **Agent Guidelines / Rules** list if the skill has many discrete
   do/don't facts — a scannable contract the agent can re-check.

## Step 4 — Progressive disclosure: inline vs bundled

Keep `SKILL.md` to the trigger plus always-needed essentials (this repo enforces
a 150-line hard ceiling, <100 target). Push depth into files loaded on demand:

- **`references/<topic>.md`** when a section serves only a sub-case, or the body
  is creeping past the length budget. Link it inline so the agent knows it exists.
- **`scripts/`** for any deterministic step. **`assets/`** for output templates.

Rule of thumb: if a heading would only matter to a fraction of invocations, it
belongs in `references/`; if every time, keep it inline.

## Step 5 — Frontmatter

Required: `name` (kebab-case, equal to the directory name), `description`,
`version` (semver, bumped on every change), `license`. Common optional fields:
`compatibility`, `metadata.*`. Full field reference, allowed values, and a
linting checklist: [references/frontmatter.md](references/frontmatter.md).

To start from a skeleton, copy [assets/SKILL.template.md](assets/SKILL.template.md)
— it has frontmatter stubs and commented section placeholders for each archetype.

## Step 6 — Verify before shipping

1. **Trigger test:** write 3–5 prompts that should fire the skill and 2–3 that
   should not; read only the `description` and predict; adjust until correct.
2. **Cold-read test:** would an agent with no prior context follow the body
   without guessing at paths or commands? Resolve every relative path.

3. **Contributing Improvements:** the skill ends with a `## Contributing
   Improvements` section pointing at its source-of-truth repo — add it, or keep
   it when updating ([template](references/contributing-improvements.md)).

The `opencode-refine` skill drives the trigger and cold-read tests with `opencode run`.

## Improving an existing skill

Diagnose the symptom, then make the smallest fix:

- **Under-triggers** → description missing trigger phrases; add the literal words.
- **Over-triggers** → description too broad / overlaps a sibling; add a boundary.
- **Fires but underperforms** → missing gotcha, or railroading; add the failure
  to the gotchas section, loosen over-specific steps.
- **Too long / slow to load** → move sub-case sections into `references/`.

Always capture the failure as a gotcha so it can't recur — this is how skills
compound in value.

## Anti-patterns

- **Stating the obvious** — restating model defaults adds context cost, zero value.
- **Straddling categories** — one skill, one job.
- **Description-as-summary** — omits trigger words; the skill silently never fires.
- **Railroading** — a rigid transcript that breaks when reality differs.
- **Premature `references/`** — splitting before the skill is big enough.
- **Reconstructing boilerplate in prose** instead of shipping a script.
- **Baking in environment specifics** (paths, IDs) instead of config + ask-once.

## Contributing Improvements

This skill is maintained in
[`gitlab-org/ai/skills`](https://gitlab.com/gitlab-org/ai/skills). If you find
guidance here **inaccurate or outdated**, confirm with the user and open an MR
against that repository with the fix. Keep changes focused — one fix per MR.
