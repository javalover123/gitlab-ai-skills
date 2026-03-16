# GitLab AI Skills

![Pipeline Status](https://gitlab.com/gitlab-org/ai/skills/badges/main/pipeline.svg)

Reusable agent skills for GitLab projects. Skills are structured prompt files that AI coding assistants (like [OpenCode](https://opencode.ai) and [Claude Code](https://code.claude.com)) can load on demand to gain domain-specific knowledge and workflows.

## Table of Contents

<!-- TOC_START -->
  - [Table of Contents](#table-of-contents)
  - [What is a Skill?](#what-is-a-skill)
  - [Skills](#skills)
  - [Installing Skills](#installing-skills)
    - [Claude Code](#claude-code)
    - [OpenCode](#opencode)
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
| [`self-service-performance-testing`](skills/self-service-performance-testing/SKILL.md) | Help engineers write performance tests that detect regressions, using k6 for load testing and sitespeed.io for frontend Core Web Vitals. Use when the user is adding or changing API endpoints, database queries, critical paths, or frontend pages and needs to decide whether to write a performance test, what kind, or how to integrate it into CI. Also activate when the user mentions load testing, stress testing, response times, benchmarking, performance budgets, or wants to run tests against staging - this skill enforces shared infrastructure safety rules. Does not cover profiling, APM, or debugging production incidents. |
<!-- SKILLS_END -->

> The table above is auto-generated from skill frontmatter. Run `python3 scripts/update_skills_list.py` to regenerate after adding or modifying skills.

## Installing Skills

### Claude Code

This repo is a [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces). Install skills as plugins directly:

```shell
/plugin marketplace add https://gitlab.com/gitlab-org/ai/skills.git
/plugin install glab@gitlab-skills
```

### OpenCode

> [!warning]
> TODO: We should strongly consider creating `@gitlab/skills` or, better yet, upstream GitLab support to [`vercel-labs/skills`](https://github.com/vercel-labs/skills)

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

## Contributing

To add a new skill:

1. Create `skills/<skill-name>/SKILL.md` with required frontmatter (`name`, `description`, `license`, `compatibility`)
2. Run `lefthook run auto-fix` to regenerate all derived files (README table, ToC, catalog, plugin manifests)
3. Commit and push — six CI checks verify everything is in sync

See [doc/contributing.md](doc/contributing.md) for full details, frontmatter reference, and development setup (including lefthook installation).

## Related

- [Search Team AI Skills](https://gitlab.com/gitlab-org/search-team/ai/skills) — team-specific skills collection that inspired this repo's conventions
- [OpenCode Documentation](https://opencode.ai/docs)
- [Claude Code Plugin Marketplace Docs](https://code.claude.com/docs/en/plugin-marketplaces)
