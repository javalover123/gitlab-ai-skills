---
name: authoring-skills
description: Author a new agent skill or improve an existing one - write the SKILL.md frontmatter and description, structure the body, and fix skills that under- or over-trigger. Use when asked to create/write a skill, make a SKILL.md, improve/refactor a skill, or fix a skill's description.
version: 0.4.0
license: MIT
category: Meta / Authoring
compatibility: opencode
metadata:
  audience: skill-authors
  workflow: local
---

# Authoring Skills

A workflow for writing or improving a skill so it triggers reliably and earns
its place in context. Grounded in
Anthropic's "Lessons from building Claude Code: how we use skills" (Jun 2026),
Anthropic's skill-authoring best practices and "Complete Guide to Building
Skills for Claude", and the conventions of well-written skills in this repo.
Where the sources and this repo's `AGENTS.md` disagree, the repo wins.

A skill is a **folder**: `SKILL.md` plus optional `references/`, `scripts/`, `assets/`.

## When to use

- Turning a repeatable workflow, tool/API reference, verification procedure, or
  review checklist into a reusable skill.
- A skill under-triggers or over-triggers — usually a `description` problem.
- A `SKILL.md` has grown unwieldy and needs splitting into `references/`.

Not for one-offs (write a note) or things the model already does well.

## Step 0 — Is a skill the right vessel?

1. **One job?** Split skills that straddle categories
   ([references/skill-types.md](references/skill-types.md) has the taxonomy).
2. **Does it push the model off its defaults?** If not, write nothing.

## Step 1 — Write the description first (the discovery trigger)

The agent scans every skill's `description` to decide "is there a skill for this
request?" It is **not a summary — it is a description of *when to trigger*.**
Lead with the literal phrases a user would type, enumerate situations, add a
boundary clause ("do not use for…") if a sibling could match, third-person
present. Say both **what** it does and **when** to use it; stay under 1,024
characters; no `<`/`>` (the text is injected into the system prompt).

Litmus test: read *only* the description and predict which prompts fire it.
Patterns, before/after examples, and the full test:
[references/descriptions.md](references/descriptions.md).

## Step 2 — Choose the body shape

Pick the smallest archetype that fits; grow it later:

| Archetype | Use for | Example |
|---|---|---|
| **Inline technique** (<80 lines) | One self-contained procedure | `write-large-file` |
| **Phase / reference-table workflow** | Multi-step process, each step with depth | `gitlab-babysit-mr` |
| **Deep reference + guardrails** | Tool/API with many footguns | `glab` |

Match instruction tightness to fragility: exact commands for fragile steps,
heuristics where many approaches work
([degrees of freedom](references/body-patterns.md)).

## Step 3 — Write the body

1. Open with one or two sentences on what the skill does and assumes.
2. **Lead with the gotchas** — what the agent gets wrong by default. Prefer
   concrete "X is actually Y" facts over generic advice.
3. **Don't railroad.** Give facts and constraints, not a rigid transcript, unless
   order matters (destructive/safety steps).
4. **Be concrete and decisive.** Give one default plus an escape hatch rather
   than a menu of options; show input/output examples; use one term per concept;
   keep critical rules near the top and replace vague words ("validate
   properly") with checkable ones. More in
   [references/body-patterns.md](references/body-patterns.md).
5. **Store scripts; let the agent compose.** Ship helpers for boilerplate, state
   whether to *run* or *read* each one, and list dependencies. Reference them by
   path relative to the skill root. Script design:
   [references/scripts.md](references/scripts.md).
6. End with an **Agent Guidelines / Rules** list if there are many discrete
   do/don't facts.

## Step 4 — Progressive disclosure: inline vs bundled

Keep `SKILL.md` to always-needed essentials (repo: <100 lines target, 150 hard
ceiling — stricter than Anthropic's 500). Push depth into files loaded on demand:

- **`references/<topic>.md`** when a section serves only a sub-case or the body
  nears the length budget.
- **`scripts/`** for any deterministic step. **`assets/`** for output templates.
- Link every reference **directly from `SKILL.md`** (one level deep; nested
  links get partially read), give files descriptive names, and add a contents
  list to any reference over ~100 lines.
- No `README.md` inside a skill folder; the file must be named exactly `SKILL.md`.

Heading useful only to some invocations → `references/`; every time → inline.

## Step 5 — Frontmatter

Required: `name` (kebab-case, equals the directory name, ≤64 chars, no
"claude"/"anthropic"), `description`, `version` (semver, bumped on every
change), `license`. Optional: `compatibility`, `metadata.*`. Field reference and
linting checklist: [references/frontmatter.md](references/frontmatter.md).

Skeleton to copy: [assets/SKILL.template.md](assets/SKILL.template.md).

## Step 6 — Verify before shipping

1. **Trigger test:** write 3–5 prompts that should fire the skill (obvious *and*
   paraphrased) and 2–3 that should not; read only the `description` and
   predict; adjust until correct. Quick probe: ask the agent "when would you use
   the `<name>` skill?" — it will paraphrase the description back.
2. **Cold-read test:** would an agent with no prior context follow the body
   without guessing at paths or commands? Resolve every relative path.
3. **Baseline test:** run a representative task with and without the skill;
   write only what closes the observed gap. Methodology, success metrics, and
   multi-model checks: [references/testing.md](references/testing.md).
4. **Contributing Improvements:** end with a `## Contributing Improvements`
   section, add if missing ([template](references/contributing-improvements.md)).

`opencode-refine` drives the first two tests with `opencode run`.

## Improving an existing skill

Diagnose the symptom, then make the smallest fix:

- **Under-triggers** → description missing trigger phrases; add the literal words.
- **Over-triggers** → description too broad / overlaps a sibling; add a boundary.
- **Fires but underperforms** → missing gotcha, or railroading; add the failure
  to the gotchas section, loosen over-specific steps. If rules are ignored, they
  are likely buried, vague, or too verbose — move them up, make them checkable,
  or enforce them with a script.
- **Too long / slow to load** → move sub-case sections into `references/`.

Always capture the failure as a gotcha so it can't recur.

## Anti-patterns

Stating the obvious; straddling categories; description-as-summary; railroading;
premature `references/`; boilerplate in prose instead of a script; time-sensitive
prose (keep the current method, park legacy in a collapsed "old patterns" block);
baked-in environment specifics (paths, IDs) instead of config + ask-once.

## Contributing Improvements

Maintained in [`gitlab-org/ai/skills`](https://gitlab.com/gitlab-org/ai/skills).
If guidance here is **inaccurate or outdated**, confirm with the user, then open
a focused MR there (one fix per MR).
