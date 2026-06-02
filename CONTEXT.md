# GitLab AI Skills

The shared language for this repository: a catalog of reusable agent **skills**
and the pipeline that validates and distributes them to multiple agent
environments.

## Language

**Skill**:
A self-contained, named unit of agent instructions — a directory under `skills/`
whose `SKILL.md` carries YAML frontmatter plus Markdown, loaded on demand by an
agent to gain a domain-specific workflow. The directory is the unit that is
versioned, validated, and distributed; sibling files (references, scripts) are
part of the Skill.
_Avoid_: prompt, plugin, command, tool.

**Environment**:
A target agent platform a Skill is distributed to — currently opencode,
ClaudeCode, and pi. Each has its own discovery format.
_Avoid_: editor, assistant, channel, framework, target.

**Distribution**:
The maintainer-side act of registering a Skill into the per-Environment formats
each agent expects (opencode symlink, ClaudeCode plugin manifest, pi package
manifest), so the agent can discover it. Done in-repo via `bin/distribute-skill`;
produces committed artifacts. Distinct from Installation.
_Avoid_: install, deploy, publish, export.

**Installation**:
The consumer-side act of pulling a published Skill into one's own agent setup
(via GitLab Duo CLI, the pi package, the `@dgruzd/skills` CLI, or the Claude Code
marketplace). Consumes the artifacts that Distribution produces.
_Avoid_: distribute, setup.

**SKILL.md**:
The lean entry point of a Skill — a single file carrying YAML frontmatter
(`name`, `description`, `version`, `license`) plus Markdown workflow content.
Kept under ~100 lines; detail is offloaded to Reference files. Distinct from the
Skill, which is the whole directory.
_Avoid_: manifest, prompt file.

**Reference file**:
A sibling Markdown file under `skills/<name>/references/` holding detail
offloaded from `SKILL.md` to keep the entry point lean. Linked from `SKILL.md`,
loaded on demand.
_Avoid_: doc, appendix, attachment.

**Helper script**:
An executable script under a Skill directory (`skills/**/*.sh`) that the Skill's
workflow invokes. Subject to `shellcheck` in CI.
_Avoid_: util, tool, command.
