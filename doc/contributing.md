# Contributing a New Skill

## Adding a Skill

1. Create a directory under `skills/` named after the skill (e.g. `skills/my-workflow/`)
2. Add a `SKILL.md` with YAML frontmatter:

   ```markdown
   ---
   name: my-workflow
   description: One-line description of what this skill provides
   license: MIT
   compatibility: opencode
   metadata:
     audience: developers
   ---

   # My Workflow Skill

   ...skill content...
   ```

3. Run the auto-fix to regenerate all derived files:

   ```bash
   python3 scripts/update_skills_list.py     # Update README skills table
   python3 scripts/generate_catalog.py        # Update catalog.json
   python3 scripts/generate_claude_plugin.py  # Update .claude-plugin/ manifests
   ```

   Or if you have lefthook installed: `lefthook run auto-fix`

4. Commit everything: the new skill, updated README, catalog.json, and .claude-plugin/ manifests

The CI pipeline will fail if any generated files are out of sync with the skill files.

## Required Frontmatter Fields

| Field | Description |
|-------|-------------|
| `name` | Skill identifier (kebab-case, matches directory name) |
| `description` | One-line description — shown in README table and catalog |
| `license` | SPDX license identifier (typically `MIT`) |
| `compatibility` | Agent framework (`opencode`) |

Optional fields: `metadata` (with nested `audience`, `workflow`, etc.)

The `validate-frontmatter` CI job enforces these required fields.

## Claude.ai Compatibility

Skills are automatically packaged as [Claude Code plugins](https://code.claude.com/docs/en/plugin-marketplaces). The `check-claude-drift` CI job verifies that SKILL.md files remain structurally compatible with the claude.ai format.

Key differences between formats:
- **opencode** uses `name`, `license`, `compatibility`, `metadata` in frontmatter — claude.ai silently ignores these
- **claude.ai** requires `description` (which we also require) and optionally supports `disable-model-invocation`
- Both formats use the same `SKILL.md` content body

You don't need to do anything special — just ensure `description` is present and the CI handles the rest.

## Development

### Regenerate all derived files

```bash
lefthook run auto-fix
```

Or run each script individually:

```bash
python3 scripts/update_skills_list.py      # README skills table
python3 scripts/generate_catalog.py         # catalog.json
python3 scripts/generate_claude_plugin.py   # .claude-plugin/ manifests
```

### Verify everything is up to date (CI mode)

```bash
python3 scripts/update_skills_list.py --ci
python3 scripts/validate_frontmatter.py --ci
python3 scripts/check_claude_drift.py --ci
python3 scripts/generate_catalog.py --ci
python3 scripts/generate_claude_plugin.py --ci
```

### Install lefthook (optional, for auto-fix on push)

```bash
gem install lefthook   # or: brew install lefthook
lefthook install
```

With lefthook installed:
- **Pre-push**: all five checks run automatically (blocks push on failure)
- **Auto-fix**: `lefthook run auto-fix` regenerates all derived files
