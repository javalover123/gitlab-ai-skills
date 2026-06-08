# Frontmatter field reference

Every `SKILL.md` opens with a YAML frontmatter block delimited by `---`. Only
two fields are required; the rest are conventional metadata commonly seen across
well-written skills. The two required fields are what Anthropic's post calls out
as load-bearing — `name` identifies the skill and `description` is the discovery
trigger.

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
  match. Length varies from one line (`gitlab-backport`,
  `write-large-file`) to a packed multi-sentence trigger surface
  (`agent-browser`, `playwright-cli`, `orbit`) — longer is fine when the skill
  legitimately covers many phrasings.
- See **`references/descriptions.md`** for patterns, worked before/after
  examples, and the litmus test.

## Optional fields (conventional)

### `version`
- **What:** semver string for the skill.
- **Observed:** `0.1.0` … `1.8.2`. Present on most skills; absent on a few
  (`jina-reader`, `agent-browser`). Bump it when you change behaviour. Optional
  but recommended.

### `license`
- **What:** license identifier. **Common:** uniformly `MIT` across the example
  skills. Optional; include for shareable skills.

### `compatibility`
- **What:** the agent runtime the skill targets. **Observed:** `opencode` on
  skills that set it (`glab`, `orbit`, `playwright-cli`, `jina-reader`,
  `gitlab-babysit-mr`, …). Some skills omit it. Use `opencode` here.

### `category`
- **What:** free-text bucket for human browsing (not the 9-type taxonomy in
  `references/skill-types.md`, though they overlap).
- **Observed values:** `Development Workflow` (`gitlab-pipeline-watch`,
  `glab`), `Testing` (`playwright-cli`), `Agent Tooling` (`opencode-refine`),
  `Shell & Environment` (`run-in-tmux-pane`), `Meta / Authoring`
  (this meta-skill). Title Case. Optional and not standardised — pick the
  clearest label or reuse an existing one.

### `argument-hint`
- **What:** a hint shown for skills invoked with an argument.
- **Observed:** `gitlab-babysit-mr` uses `argument-hint: <URL of the MR to
  babysit>`. Add it only when the skill expects a specific positional input.

### `allowed-tools`
- **What:** restricts which tools the skill may call (a permission scope).
- **Observed:** `agent-browser` uses
  `allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*)`. Use only
  when you want to constrain the skill to specific commands; most skills omit
  it and inherit the agent's tool access.

### `metadata.*` (nested map)
A free-form block of tags; useful for organisation and search. Observed keys:

| Key | What | Observed values |
|---|---|---|
| `audience` | who the skill is for | `developers`, `general`, `skill-authors` |
| `keywords` | extra search/discovery terms (comma-separated) | e.g. `orbit, knowledge-graph, gkg, query` |
| `workflow` | domain tag | `gitlab`, `gitlab-ci`, `gitlab-release`, `web-scraping`, `local`, `ai`, `browser-automation` |
| `author` | who wrote it | e.g. `dgruzd`, `pedropombeiro` |

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
