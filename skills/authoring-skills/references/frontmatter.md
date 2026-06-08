# Frontmatter field reference

Every `SKILL.md` opens with a YAML frontmatter block delimited by `---`. This
repo's `validate_frontmatter.py` requires **four** fields — `name`,
`description`, `version`, `license` — and CI fails without them. The rest are
conventional metadata. Of the four, `name` and `description` are the ones
Anthropic's post calls out as load-bearing for discovery: `name` identifies the
skill, `description` is the trigger the model scans.

```yaml
---
name: my-skill
description: <trigger-shaped sentence — see references/descriptions.md>
version: 1.0.0
license: MIT
compatibility: opencode
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

## Required fields

### `name` (required)
- **What:** the skill's identifier; the value the `skill` tool is invoked with.
- **Convention:** **kebab-case**, and it **matches the skill's folder name**
  (`gitlab-babysit-mr/` → `name: gitlab-babysit-mr`). Well-written skills
  follow this.
- No spaces, no uppercase, no underscores.

### `description` (required)
- **What:** the single most important field — the model scans every skill's
  description to decide whether to trigger it. It is a *description of when to
  trigger*, not a summary.
- **Convention:** third-person present; lead with trigger verbs/phrases;
  enumerate situations; add a boundary clause if a sibling skill could also
  match. Length varies from one line (`write-large-file`, `commit-messages`)
  to a packed multi-sentence trigger surface (`playwright-cli`, `pushify`,
  `stack-changes`) — longer is fine when the skill legitimately covers many
  phrasings.
- See **`references/descriptions.md`** for patterns, worked before/after
  examples, and the litmus test.

### `version` (required)
- **What:** semver string (`X.Y.Z`) for the skill.
- **Convention:** start a new skill at `0.1.0` or `1.0.0`; **bump it on every
  change** to any file under the skill directory — `check_version_bump.py` gates
  this against `main` and CI fails otherwise.

### `license` (required)
- **What:** SPDX license identifier. **Common:** uniformly `MIT` across this
  repo's skills.

## Optional fields (conventional)

### `compatibility`
- **What:** the agent runtime the skill targets. **Observed:** `opencode` on
  skills that set it (`glab`, `playwright-cli`, `gitlab-babysit-mr`, …). Some
  skills omit it. Use `opencode` here.

### `category`
- **What:** free-text bucket for human browsing (not the 9-type taxonomy in
  `references/skill-types.md`, though they overlap).
- **Observed values in this repo:** `Development Workflow` (`glab`,
  `gitlab-pipeline-watch`, …), `Testing` (`playwright-cli`), `Database`
  (`gitlab-psql`, `gitlab-clickhouse`), `Agent Tooling` (`opencode-refine`),
  `Shell & Environment` (`run-in-tmux-pane`). Title Case. Not standardised —
  reuse an existing label, or add a new one when none fits (this skill uses
  `Meta / Authoring`).

### `argument-hint`
- **What:** a hint shown for skills invoked with an argument.
- **Observed:** `gitlab-babysit-mr` uses `argument-hint: <URL of the MR to
  babysit>`. Add it only when the skill expects a specific positional input.

### `allowed-tools`
- **What:** restricts which tools the skill may call (a permission scope), e.g.
  `allowed-tools: Bash(my-tool:*), Bash(npx my-tool:*)`. Use only when you want
  to constrain the skill to specific commands; the skills in this repo omit it
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
- [ ] YAML is valid (the block is fenced by `---` on its own lines; no tabs).
- [ ] No secrets, tokens, or environment-specific absolute paths in frontmatter.
- [ ] `version` bumped if behaviour changed.
- [ ] `category` / `metadata.workflow` reuse an existing label where one fits.
