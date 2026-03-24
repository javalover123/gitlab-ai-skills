# Contributing a New Skill

## Adding a Skill

1. Create a directory under `skills/` named after the skill (e.g. `skills/my-workflow/`)
2. Add a `SKILL.md` with YAML frontmatter:

   ```markdown
   ---
   name: my-workflow
   description: One-line description of what this skill provides
   version: 1.0.0
   license: MIT
   compatibility: opencode
   metadata:
     audience: developers
   ---

   # My Workflow Skill

   ...skill content...
   ```

3. Regenerate all derived files:

   ```bash
   lefthook run auto-fix
   ```

4. Commit everything: the new skill, updated README, and plugin manifest

The CI pipeline will fail if any generated files are out of sync with the skill files.

## Required Frontmatter Fields

| Field | Description |
|-------|-------------|
| `name` | Skill identifier (kebab-case, matches directory name) |
| `description` | One-line description — shown in README table and catalog |
| `version` | Semver version string (e.g. `1.0.0`) — **must be bumped** when any skill file changes |
| `license` | SPDX license identifier (typically `MIT`) |
| `compatibility` | Agent framework (`opencode`) |

Optional fields: `metadata` (with nested `audience`, `workflow`, etc.)

The `validate-frontmatter` CI job enforces these required fields. The `check-version-bump` job
verifies that the `version` field is incremented whenever files under `skills/<name>/` change.

## Claude.ai Compatibility

Skills are automatically packaged as [Claude Code plugins](https://code.claude.com/docs/en/plugin-marketplaces). The `check-claude-drift` CI job verifies that SKILL.md files remain structurally compatible with the claude.ai format.

Key differences between formats:
- **opencode** uses `name`, `license`, `compatibility`, `metadata` in frontmatter — claude.ai silently ignores these
- **claude.ai** requires `description` (which we also require) and optionally supports `disable-model-invocation`
- Both formats use the same `SKILL.md` content body

You don't need to do anything special — just ensure `description` is present and the CI handles the rest.

## Development

### Install lefthook (recommended)

```bash
brew install lefthook
lefthook install
```

With lefthook installed:
- **Pre-push**: all six checks run automatically (blocks push on failure)
- **Auto-fix**: `lefthook run auto-fix` regenerates all derived files

### Regenerate all derived files

```bash
lefthook run auto-fix
```

Or run each script individually:

```bash
python3 scripts/update_skills_list.py      # README skills table
python3 scripts/update_toc.py              # README table of contents
```

### Verify everything is up to date (CI mode)

```bash
python3 scripts/update_skills_list.py --ci
python3 scripts/update_toc.py --ci
python3 scripts/validate_frontmatter.py --ci
python3 scripts/check_claude_drift.py --ci
npx -y @anthropic-ai/claude-code plugin validate .
python3 scripts/check_version_bump.py --ci
```
