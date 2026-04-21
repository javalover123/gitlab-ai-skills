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

3. Register the skill for distribution to editor environments:

   ```bash
   bin/distribute-skill my-workflow
   ```

   This creates the necessary symlinks and manifests in `.opencode/` and `.claude-plugin/`.
   To target a specific environment only: `--env=opencode` or `--env=claudecode`. See more in `bin/distribute-skill` manual.

4. Regenerate all derived files:

   ```bash
   lefthook run auto-fix
   ```

5. Commit everything: the new skill, updated README, catalog.json, and distribution manifests

The CI pipeline will fail if any generated files are out of sync with the skill files.

## Required Frontmatter Fields

| Field | Description |
|-------|-------------|
| `name` | Skill identifier (kebab-case, matches directory name) |
| `description` | One-line description — shown in README table and catalog |
| `version` | Semver version string (e.g. `1.0.0`) — **must be bumped** when any skill file changes |
| `license` | SPDX license identifier (typically `MIT`) |

Optional fields: `compatibility` (agent framework, e.g. `opencode`), `metadata` (with nested `audience`, `workflow`, etc.)

The `validate-frontmatter` CI job enforces these required fields. The `check-version-bump` job
verifies that the `version` field is incremented whenever files under `skills/<name>/` change.

## Updating an Existing Skill

1. Edit files under `skills/<name>/` (e.g. `SKILL.md`, files in `references/`)
2. Bump the `version` field in `SKILL.md` frontmatter — the `check-version-bump` CI job will fail if you forget
3. Regenerate all derived files:

   ```bash
   bin/sync-skill <name>                        # sync version into plugin.json
   python3 scripts/update_claudecode_readme.py  # update README plugins table
   python3 scripts/generate_catalog.py          # update catalog.json
   ```

   Or run everything at once: `lefthook run auto-fix`

4. Commit the skill files and all regenerated files together

## Distribution

Skills are distributed to editor-specific directories using `bin/distribute-skill`:

```bash
bin/distribute-skill SKILLNAME                          # all environments
bin/distribute-skill SKILLNAME --env=opencode           # opencode only
bin/distribute-skill SKILLNAME --env=claudecode         # ClaudeCode only
bin/distribute-skill SKILLNAME --env=claudecode --plugin=PLUGINNAME  # custom plugin name
bin/distribute-skill SKILLNAME --env=opencode --overwrite  # remove from all other envs
```

**opencode** (`.opencode/skills/`): creates a symlink to `skills/<name>/`.

**ClaudeCode** (`.claude-plugin/plugins/<name>/`): writes a `plugin.json` manifest, creates a symlink under `skills/`, and registers the plugin in `marketplace.json`.

CI jobs verify the distributed skills are format-compatible:

- `validate-opencode-distribution` — checks `.opencode/skills/*/SKILL.md` for required opencode fields
- `validate-claudecode-distribution` — checks `.claude-plugin/**/skills/*/SKILL.md` for required ClaudeCode fields

## Development

### Install lefthook (recommended)

```bash
brew install lefthook
lefthook install
```

With lefthook installed:

- **Pre-push**: all checks run automatically (blocks push on failure)
- **Auto-fix**: `lefthook run auto-fix` regenerates all derived files

### Regenerate all derived files

```bash
lefthook run auto-fix
```

Or run each script individually:

```bash
python3 scripts/update_skills_list.py      # README skills table
python3 scripts/update_toc.py              # README table of contents
python3 scripts/generate_catalog.py        # catalog.json
bin/sync-skill                             # sync SKILL.md versions into plugin.json
```

### Verify everything is up to date (CI mode)

```bash
bin/ci-checks
```

This runs all checks in sequence and reports any failures at the end.
