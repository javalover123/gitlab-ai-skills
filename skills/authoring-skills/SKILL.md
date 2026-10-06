---
name: authoring-skills
description: Author a new agent skill or improve an existing one - write the SKILL.md frontmatter and description, structure the body, and fix skills that under- or over-trigger. Use when asked to create/write a skill, make a SKILL.md, improve/refactor a skill, or fix a skill's description.
version: 0.4.1
license: MIT
category: Meta / Authoring
compatibility: opencode
metadata:
  audience: skill-authors
  workflow: local
---

# Authoring Skills

Write or improve a skill so it triggers reliably and earns its place in context.
Grounded in Anthropic's published skill guidance and this repo's conventions;
where they disagree, the repo's `AGENTS.md` wins. A skill is a **folder**:
`SKILL.md` plus optional `references/`, `scripts/`, `assets/`.

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
Open with what the skill does in the verbs users type, then `Use when…` with the
situations; add a "do not use for…" boundary if a sibling could match. Hard
limits (length, point of view, characters) and worked before/after examples:
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
4. **Be concrete and decisive.** One default plus an escape hatch, not a menu;
   input/output examples; one term per concept; critical rules near the top;
   checkable wording instead of "validate properly". Details:
   [references/body-patterns.md](references/body-patterns.md).
5. **Store scripts; let the agent compose.** Ship helpers for boilerplate, say
   whether to *run* or *read* each one, list dependencies, use paths relative to
   the skill root. Script design: [references/scripts.md](references/scripts.md).
6. Many discrete do/don't facts? End with an **Agent Guidelines** list.

## Step 4 — Progressive disclosure: inline vs bundled

Keep `SKILL.md` to always-needed essentials (repo: <100 lines target, 150 hard
ceiling — stricter than Anthropic's 500). Push depth into files loaded on demand:

- **`references/<topic>.md`** when a section serves only a sub-case or the body
  nears the length budget. Heading useful only to some invocations → reference;
  every time → inline.
- **`scripts/`** for deterministic steps; **`assets/`** for output templates.
- Link every reference directly from `SKILL.md`; layout rules (one level deep,
  contents lists, file naming) are in
  [references/body-patterns.md](references/body-patterns.md#file-layout).

## Step 5 — Frontmatter

Required: `name` (kebab-case, equals the directory name), `description`,
`version` (semver, bumped on every change), `license`. Optional:
`compatibility`, `metadata.*`. Field limits and linting checklist:
[references/frontmatter.md](references/frontmatter.md). Skeleton to copy:
[assets/SKILL.template.md](assets/SKILL.template.md).

## Step 6 — Verify before shipping

Test the skill, not just the text, with any harness or by hand
([references/testing.md](references/testing.md): metrics, symptom-to-fix table).

1. **Trigger test:** prompts that should fire it (obvious *and* paraphrased) and
   prompts that should not; predict from the `description` alone, adjust.
2. **Cold-read test:** could an agent with no prior context follow the body
   without guessing at paths or commands? Resolve every relative path.
3. **Real-task test:** run representative tasks with and without the skill;
   write only what closes the observed gap; fix what the agent actually got wrong.
4. **Contributing Improvements:** end with a `## Contributing Improvements`
   section, add if missing ([template](references/contributing-improvements.md)).

## Improving an existing skill

Diagnose the symptom, make the smallest fix, and capture the failure as a
gotcha so it can't recur:

- **Under-triggers** → add the literal trigger phrases to the description.
- **Over-triggers** → add a "do not use for…" boundary.
- **Fires but underperforms** → missing gotcha or railroading; if rules are
  ignored, move them up, make them checkable, or enforce with a script.
- **Too long** → move sub-case sections into `references/`.

## Anti-patterns

- **Stating the obvious** — restating model defaults costs context, adds nothing.
- **Straddling categories** — one skill, one job.
- **Description-as-summary** — omits trigger words; the skill never fires.
- **Railroading** — a rigid transcript breaks when reality differs.
- **Premature `references/`** — don't split before the skill is big enough.
- **Boilerplate in prose** — ship a script instead.
- **Time-sensitive prose** — keep the current method; park legacy behaviour in a
  collapsed "old patterns" block.
- **Environment specifics** (paths, IDs) baked in — use config and ask once.

## Contributing Improvements

Maintained in [`gitlab-org/ai/skills`](https://gitlab.com/gitlab-org/ai/skills).
If guidance here is **inaccurate or outdated**, confirm with the user, then open
a focused MR there (one fix per MR).
