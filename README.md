# GitLab AI Skills

![Pipeline Status](https://gitlab.com/gitlab-org/ai/skills/badges/main/pipeline.svg)

Reusable agent skills for GitLab projects. Skills are structured prompt files that AI coding assistants (like [OpenCode](https://opencode.ai) and [Claude Code](https://code.claude.com)) can load on demand to gain domain-specific knowledge and workflows.

## What is a Skill?

A skill is a directory containing a `SKILL.md` file with:
- **YAML frontmatter** — `name`, `description`, `license`, `compatibility`, and optional `metadata` fields
- **Markdown content** — step-by-step workflows, code examples, reference tables, checklists, and anything else the agent needs

Skills are loaded explicitly by the agent when relevant to a task (e.g. "load the `glab` skill") rather than being injected into every prompt. This keeps context lean and focused.

## Skills

<!-- SKILLS_START -->
| Skill | Description |
| ----- | ----------- |
| [`glab`](skills/glab/SKILL.md) | GitLab workflow automation using glab CLI |
<!-- SKILLS_END -->

> The table above is auto-generated from skill frontmatter. Run `python3 scripts/update_skills_list.py` to regenerate after adding or modifying skills.

## Installing Skills

<!-- TODO: replace @dgruzd/skills with @gitlab/skills once released, or upstream GitLab support to https://github.com/vercel-labs/skills -->

### Via `npx @dgruzd/skills` (Recommended)

[`@dgruzd/skills`](https://github.com/dgruzd/skills) is a fork of [`vercel-labs/skills`](https://github.com/vercel-labs/skills) that adds GitLab update detection — without it, `skills check` and `skills update` silently skip GitLab-hosted skills. It handles symlinking, multi-agent installs, updates, and discovery with no global install required.

```bash
# Install all skills from this repo globally
npx @dgruzd/skills add https://gitlab.com/gitlab-org/ai/skills/-/tree/main/skills --global --agent opencode

# Check for updates
npx @dgruzd/skills check

# Apply updates
npx @dgruzd/skills update

# List installed skills
npx @dgruzd/skills list -g
```

The `--agent opencode` flag installs to `~/.agents/skills/`, which is the standard location for OpenCode.

### Via Claude Code Plugin Marketplace

This repo is also a [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces). Install skills as plugins directly in Claude Code:

```shell
/plugin marketplace add https://gitlab.com/gitlab-org/ai/skills.git
/plugin install glab@gitlab-ai-skills
```

### Manual Symlink (Alternative)

If you prefer no external tooling:

```bash
# Run from your local clone of this repo
cd /path/to/ai-skills

mkdir -p ~/.config/opencode/skills
for skill in skills/*/; do
  name=$(basename "$skill")
  ln -s "$(pwd)/$skill" ~/.config/opencode/skills/"$name"
done
```

Symlinking the skill directory (rather than just `SKILL.md`) ensures any future additions to a skill folder are automatically picked up.

## Contributing

See [doc/contributing.md](doc/contributing.md) for how to add a new skill and development setup.

## Related

- [Search Team AI Skills](https://gitlab.com/gitlab-org/search-team/ai/skills) — team-specific skills collection that inspired this repo's conventions
- [OpenCode Documentation](https://opencode.ai/docs)
- [Claude Code Plugin Marketplace Docs](https://code.claude.com/docs/en/plugin-marketplaces)
