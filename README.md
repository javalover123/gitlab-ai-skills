# GitLab AI Skills

![Pipeline Status](https://gitlab.com/gitlab-org/ai/skills/badges/main/pipeline.svg)

Reusable agent skills for GitLab projects. Skills are structured prompt files that AI coding assistants (like [OpenCode](https://opencode.ai) and [Claude Code](https://code.claude.com)) can load on demand to gain domain-specific knowledge and workflows.

## Table of Contents

<!-- TOC_START -->
  - [Table of Contents](#table-of-contents)
  - [What is a Skill?](#what-is-a-skill)
  - [Skills](#skills)
  - [Installing Skills](#installing-skills)
    - [OpenCode (Native)](#opencode-native)
    - [Via `@dgruzd/skills` CLI](#via-dgruzdskills-cli)
    - [Claude Code Plugin Marketplace](#claude-code-plugin-marketplace)
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
| [`playwright-cli`](skills/playwright-cli/SKILL.md) | Automates browser interactions for web testing, form filling, screenshots, and data extraction. Use when the user needs to navigate websites, interact with web pages, fill forms, take screenshots, test web applications, or extract information from web pages. |
| [`run-in-tmux-pane`](skills/run-in-tmux-pane/SKILL.md) | Run commands in a temporary tmux pane with full interactive zsh environment (login shell, shims, PATH, aliases, TTY). |
| [`self-service-performance-testing`](skills/self-service-performance-testing/SKILL.md) | Help engineers write performance tests that detect regressions, using k6 for load testing and sitespeed.io for frontend Core Web Vitals. Use when the user is adding or changing API endpoints, database queries, critical paths, or frontend pages and needs to decide whether to write a performance test, what kind, or how to integrate it into CI. Also activate when the user mentions load testing, stress testing, response times, benchmarking, performance budgets, or wants to run tests against staging - this skill enforces shared infrastructure safety rules. Does not cover profiling, APM, or debugging production incidents. |
<!-- SKILLS_END -->

> The table above is auto-generated from skill frontmatter. Run `python3 scripts/update_skills_list.py` to regenerate after adding or modifying skills.

## Installing Skills

> [!NOTE]
> **Windows users:** this repo uses symlinks for skill distribution. Before cloning, ensure Git is configured to create real symlinks:
>
> ```bash
> git config --global core.symlinks true
> ```
>
> You may also need to enable [Developer Mode](https://learn.microsoft.com/en-us/windows/apps/get-started/enable-your-device-for-development) or run Git as Administrator for symlink creation to work.

### OpenCode (Native)

This repo ships `.opencode/skills/` with symlinks for each skill. Clone the repo and OpenCode discovers them automatically — no extra install step needed.

```bash
git clone https://gitlab.com/gitlab-org/ai/skills.git ~/gitlab-skills
# OpenCode picks up .opencode/skills/ from the cloned directory
```

Or symlink into your global OpenCode config:

```bash
for skill in ~/gitlab-skills/.opencode/skills/*/; do
  ln -s "$skill" ~/.config/opencode/skills/
done
```

### Via `@dgruzd/skills` CLI

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

### Claude Code Plugin Marketplace

This repo ships as a [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces):

```shell
/plugin marketplace add https://gitlab.com/gitlab-org/ai/skills.git
/plugin install glab@gitlab-skills
```

<!-- CLAUDECODE_PLUGINS_START -->
| Plugin | Skills | Description | Version |
| ------ | ------ | ----------- | ------- |
| [`glab`](.claude-plugin/plugins/glab) | [`glab`](skills/glab/SKILL.md) | GitLab workflow automation using glab CLI | 1.2.3 |
| [`run-in-tmux-pane`](.claude-plugin/plugins/run-in-tmux-pane) | [`run-in-tmux-pane`](skills/run-in-tmux-pane/SKILL.md) | Run commands in a temporary tmux pane with full interactive zsh environment (login shell, shims, PATH, aliases, TTY). | 1.1.0 |
| [`self-service-performance-testing`](.claude-plugin/plugins/self-service-performance-testing) | [`self-service-performance-testing`](skills/self-service-performance-testing/SKILL.md) | Help engineers write performance tests that detect regressions, using k6 for load testing and sitespeed.io for frontend Core Web Vitals. Use when the user is adding or changing API endpoints, database queries, critical paths, or frontend pages and needs to decide whether to write a performance test, what kind, or how to integrate it into CI. Also activate when the user mentions load testing, stress testing, response times, benchmarking, performance budgets, or wants to run tests against staging - this skill enforces shared infrastructure safety rules. Does not cover profiling, APM, or debugging production incidents. | 0.1.0 |
<!-- CLAUDECODE_PLUGINS_END -->

## Contributing

To add a new skill:

1. Create `skills/<skill-name>/SKILL.md` with required frontmatter (`name`, `description`, `version`)
2. Run `bin/distribute-skill <skill-name>` to register it in `.opencode/` and `.claude-plugin/`
3. Run `lefthook run auto-fix` to regenerate all derived files (README table, ToC, catalog, plugin manifests)
4. Run `bin/ci-checks` to verify CI checks locally.
5. Commit, push and open a MR

See [doc/contributing.md](doc/contributing.md) for full details, frontmatter reference, and development setup (including lefthook installation).

## Related

- [Search Team AI Skills](https://gitlab.com/gitlab-org/search-team/ai/skills) — team-specific skills collection that inspired this repo's conventions
- [OpenCode Documentation](https://opencode.ai/docs)
- [Claude Code Plugin Marketplace Docs](https://code.claude.com/docs/en/plugin-marketplaces)
