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

   This creates the necessary symlinks and manifests in `.opencode/` and `.claude-plugin/`, and verifies pi package discovery.
   To target a specific environment only: `--env=opencode`, `--env=claudecode`, or `--env=pi`. See more in `bin/distribute-skill` manual.

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

The `validate-frontmatter` CI job enforces these required fields, that `name` is
kebab-case, that it matches the directory name, and that the frontmatter is
**valid YAML** (parsed with `yaml.safe_load`). Quote `description` values that
contain colons (e.g. `description: "Use when: planning, reviewing"`).
The `check-version-bump` job
verifies that the `version` field is incremented whenever files under
`skills/<name>/` change. See [`AGENTS.md`](../AGENTS.md) for the full list of
conventions and their enforcing checks (skill length, shell-script linting,
`AGENTS.md`/`CLAUDE.md` sync).

## Distribution

Skills are distributed to editor-specific directories using `bin/distribute-skill`:

```bash
bin/distribute-skill SKILLNAME                          # all environments
bin/distribute-skill SKILLNAME --env=opencode           # opencode only
bin/distribute-skill SKILLNAME --env=claudecode         # ClaudeCode only
bin/distribute-skill SKILLNAME --env=pi                 # pi only
bin/distribute-skill SKILLNAME --env=claudecode --plugin=PLUGINNAME  # custom plugin name
bin/distribute-skill SKILLNAME --env=opencode --overwrite  # remove from all other envs
```

**opencode** (`.opencode/skills/`): creates a symlink to `skills/<name>/`.

**ClaudeCode** (`.claude-plugin/plugins/<name>/`): writes a `plugin.json` manifest, creates a symlink under `skills/`, and registers the plugin in `marketplace.json`.

**pi** (root `package.json`): no per-skill symlinks needed. Pi discovers all skills under `skills/` via the `pi.skills` manifest in `package.json`. The distribute command verifies the manifest is correctly configured.

CI jobs verify the distributed skills are format-compatible:

- `validate-opencode-distribution` — checks `.opencode/skills/*/SKILL.md` for required opencode fields
- `validate-claudecode-distribution` — checks `.claude-plugin/**/skills/*/SKILL.md` for required ClaudeCode fields
- `validate-distribution-pi` — checks `package.json` manifest and all `skills/*/SKILL.md` against pi's Agent Skills spec

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
