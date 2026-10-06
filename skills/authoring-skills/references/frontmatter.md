# Frontmatter field reference

Every `SKILL.md` opens with a YAML frontmatter block delimited by `---`. Anthropic's
spec requires only `name` and `description`; many projects also require
`version` and `license`; follow the target project. The rest are conventional
metadata. (Rules specific to `gitlab-org/ai/skills`:
[gitlab-skills-repo.md](gitlab-skills-repo.md).) `name` and `description` are
load-bearing for discovery, per Anthropic's *Lessons from building Claude Code:
how we use skills*: `name` identifies the skill, `description` is the trigger
the model scans.

## Contents

- Core and commonly required fields
- Optional fields (conventional)
- Linting checklist

```yaml
---
name: my-skill
description: <trigger-shaped sentence — see references/descriptions.md>
version: 1.0.0            # if the project requires it
license: MIT              # if the project requires it
# compatibility: <runtime or environment requirements; omit if none>
category: Development Workflow
argument-hint: <thing the skill takes>
metadata:
  audience: developers
  keywords: foo, bar, baz
  workflow: gitlab
  author: someone
allowed-tools: Bash(my-tool:*)
---
```

## Core and commonly required fields

### `name` (required)
- **What:** the skill's identifier; the value the `skill` tool is invoked with.
- **Convention:** **kebab-case**, and it **matches the skill's folder name**
  (`pdf-forms/` → `name: pdf-forms`). Well-written skills follow this.
- No spaces, no uppercase, no underscores. At most 64 characters. *(Anthropic upload validation:
  also no XML tags and no reserved words `claude`/`anthropic`.)*
- Anthropic's docs suggest gerund names (`processing-pdfs`); short
  `<domain>-<noun>` names without a redundant verb are also acceptable. Avoid vague names
  (`helper`, `utils`, `tools`) and inconsistent patterns across a collection.

### `description` (required)
- **What:** the single most important field — the model scans every skill's
  description to decide whether to trigger it. It is a *description of when to
  trigger*, not a summary.
- **Convention:** third-person present; lead with trigger verbs/phrases;
  enumerate situations; add a boundary clause if a sibling skill could also
  match. Hard limits are in `references/descriptions.md`. Length varies from
  one line to a packed multi-sentence trigger surface — longer is fine when the skill legitimately covers many
  phrasings.
- See **`references/descriptions.md`** for patterns, worked before/after
  examples, and the litmus test.

### `version` (commonly required)
- **What:** semver string (`X.Y.Z`) for the skill.
- **Convention:** start a new skill at `0.1.0` or `1.0.0`; bump it on every
  change to any file under the skill directory (some projects enforce this in CI).

### `license` (commonly required)
- **What:** SPDX license identifier. **Common:** `MIT`.

## Optional fields (conventional)

### `compatibility`
- **What:** the agent runtime the skill targets. Anthropic's guide describes it
  as environment requirements (product, system packages, network access;
  1–500 chars) and as the place to flag skills that rely on one platform's
  features. Some
  collections set a runtime name (e.g. `opencode`); others omit it. Follow the
  target project's convention.

### `category`
- **What:** free-text bucket for human browsing (not the 9-type taxonomy in
  `references/skill-types.md`, though they overlap).
- **Convention:** Title Case. Not standardised — reuse an existing label in the
  target collection, or add a new one when none fits.

### `argument-hint`
- **What:** a hint shown for skills invoked with an argument.
- **Example:** `argument-hint: <URL of the MR to babysit>`. Add it only when the skill expects a specific positional input.

### `allowed-tools`
- **What:** restricts which tools the skill may call (a permission scope), e.g.
  `allowed-tools: Bash(my-tool:*), Bash(npx my-tool:*)`. Use only when you want
  to constrain the skill to specific commands; most skills omit it
  and inherit the agent's tool access.

### `metadata.*` (nested map)
A free-form block of tags; useful for organisation and search. Observed keys:

| Key | What | Observed values |
|---|---|---|
| `audience` | who the skill is for | `developers`, `general`, `skill-authors` |
| `keywords` | extra search/discovery terms (comma-separated) | e.g. `migration, schema, rollback` |
| `workflow` | domain tag | `gitlab`, `gitlab-ci`, `database`, `git`, `local`, `browser-automation` |
| `author` | who wrote it | e.g. `dgruzd`, `gitlab`, `pedropombeiro` |

All `metadata` keys are optional and non-standardised — add what aids discovery,
omit the rest.

## Linting checklist

- [ ] `name` is kebab-case and equals the folder name.
- [ ] `description` is present and **trigger-shaped** (passes the
      `references/descriptions.md` litmus test), third-person present.
- [ ] `description` meets the hard constraints in `references/descriptions.md`.
- [ ] Entry file is named exactly `SKILL.md`.
- [ ] YAML is valid (the block is fenced by `---` on its own lines; no tabs).
- [ ] No secrets, tokens, or environment-specific absolute paths in frontmatter.
- [ ] `version` bumped if behaviour changed.
- [ ] `category` / `metadata.workflow` reuse an existing label where one fits.
