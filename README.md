# GitLab AI Skills

![Pipeline Status](https://gitlab.com/gitlab-org/ai/skills/badges/main/pipeline.svg)

Reusable agent skills for GitLab projects. Skills are structured prompt files that AI coding assistants (like [OpenCode](https://opencode.ai) and [Claude Code](https://code.claude.com)) can load on demand to gain domain-specific knowledge and workflows.

## Table of Contents

<!-- TOC_START -->
  - [Table of Contents](#table-of-contents)
  - [What is a Skill?](#what-is-a-skill)
  - [Skills](#skills)
  - [Installing Skills](#installing-skills)
    - [Claude Code Plugin (Experimental)](#claude-code-plugin-experimental)
  - [Contributing](#contributing)
  - [Related](#related)
<!-- TOC_END -->

## What is a Skill?

This repo follows the [Agent Skills](https://agentskills.io) open format ([spec](https://agentskills.io/specification)).

A skill is a directory containing a `SKILL.md` file with:
- **YAML frontmatter** — `name`, `description`, `license`, `compatibility`, and optional `metadata` fields
- **Markdown content** — step-by-step workflows, code examples, reference tables, checklists, and anything else the agent needs

Skills are loaded explicitly by the agent when relevant to a task (e.g. "load the `glab` skill") rather than being injected into every prompt. This keeps context lean and focused.

## Skills

<!-- SKILLS_START -->
| Skill | Description |
| ----- | ----------- |
| [`glab`](skills/glab/SKILL.md) | GitLab workflow automation using glab CLI |
| [`opencode-refine`](skills/opencode-refine/SKILL.md) | Iteratively test and refine prompts, skills, and agent configurations using opencode run |
| [`run-in-tmux-pane`](skills/run-in-tmux-pane/SKILL.md) | Run commands in a temporary tmux pane with full interactive zsh environment (login shell, shims, PATH, aliases, TTY). |
<!-- SKILLS_END -->

> The table above is auto-generated from skill frontmatter. Run `python3 scripts/update_skills_list.py` to regenerate after adding or modifying skills.

## Installing Skills

[`@dgruzd/skills`](https://github.com/dgruzd/skills) is a fork of [`vercel-labs/skills`](https://github.com/vercel-labs/skills) that adds GitLab update detection — without it, `skills check` and `skills update` silently skip GitLab-hosted skills. It handles symlinking, multi-agent installs, updates, and discovery with no global install required.

> [!NOTE]
> We should strongly consider creating `@gitlab/skills` or, better yet, upstream GitLab support to [`vercel-labs/skills`](https://github.com/vercel-labs/skills).

```bash
# Install all skills from this repo globally (for OpenCode)
npx @dgruzd/skills add https://gitlab.com/gitlab-org/ai/skills/-/tree/main/skills --global --agent opencode

# Install all skills from this repo globally (for Claude Code)
npx @dgruzd/skills add https://gitlab.com/gitlab-org/ai/skills/-/tree/main/skills --global --agent claude-code

# Check for updates
npx @dgruzd/skills check

# Apply updates
npx @dgruzd/skills update

# List installed skills
npx @dgruzd/skills list -g
```

### Claude Code Plugin (Experimental)

> [!WARNING]
> The Claude Code plugin marketplace integration is **experimental** and may change. The `npx @dgruzd/skills` method above is recommended for all agents.
> The experimental `gitlab-org/ai/marketplace` project can be used to install this project as a [Claude Code plugin](https://code.claude.com/docs/en/plugins-reference).

```shell
/plugin marketplace add https://gitlab.com/gitlab-org/ai/marketplace.git
/plugin install skills@gitlab-org-ai
```

## Contributing

To add a new skill:

1. Create `skills/<skill-name>/SKILL.md` with required frontmatter (`name`, `description`, `license`, `compatibility`)
2. Run `lefthook run auto-fix` to regenerate all derived files (README table, ToC, catalog, plugin manifests)
3. Commit and push — six CI checks verify everything is in sync

See [doc/contributing.md](doc/contributing.md) for full details, frontmatter reference, and development setup (including lefthook installation).

## Related

- [Search Team AI Skills](https://gitlab.com/gitlab-org/search-team/ai/skills) — team-specific skills collection that inspired this repo's conventions
- [OpenCode Documentation](https://opencode.ai/docs)
- [Claude Code Plugin Docs](https://code.claude.com/docs/en/plugins-reference)
