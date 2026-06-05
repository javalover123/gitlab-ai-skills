# Agent guidance for gitlab-org/ai/skills

This repo hosts reusable agent **skills** — each is a `skills/<name>/SKILL.md`
with YAML frontmatter plus Markdown content, distributed to OpenCode, Claude
Code, and pi. Most contributions add or edit a skill. Read this before writing.
See [`CONTEXT.md`](CONTEXT.md) for the canonical glossary of domain terms.

> `CLAUDE.md` is a copy of this file. Keep the two **byte-identical** — edit
> `AGENTS.md` and copy it over (`cp AGENTS.md CLAUDE.md`).

## Conventions reviewers keep asking for

These came up repeatedly in past reviews. Several are now enforced mechanically
(see *Checks* below); follow them up front so the pipeline stays green.

### Skill naming

- **kebab-case**, lowercase, hyphen-separated: `commit-messages`, `mr-review`.
- The `name:` frontmatter field **must equal the directory name**.
- Prefix by domain when the skill is tool-specific: `gitlab-` for
  GitLab-internal tooling (`gitlab-clickhouse`, `gitlab-psql`,
  `gitlab-babysit-mr`), `mr-` for merge-request workflows.
- Don't bake a redundant verb into the name — the `description` already says
  what it does. Prefer `commit-messages` over `writing-commit-messages`.

*Enforced:* `scripts/validate_frontmatter.py` fails CI on a non-kebab name or a
name/directory mismatch.

### Keep SKILL.md lean

- Aim for **under 100 lines**; treat **150 as a hard ceiling**. A long
  `SKILL.md` burns agent context on every load.
- Push detail into sibling reference files (`skills/<name>/references/*.md`) and
  link to them. The `SKILL.md` should be the lean entry point.
- Don't list the skill's own files inline "for reference" — the agent already
  has them in context. Link to references instead.

*Enforced:* `scripts/validate_skill_length.py` reports skills over 100/150 lines
(currently **warn-only** — a few legacy skills exceed the ceiling). New skills
should land under it.

### Descriptions

- One line, written so an agent can decide *when* to load the skill.
- Avoid embedding facts that go stale (version numbers, "currently in alpha",
  handbook specifics) — link to the source of truth instead of restating it.
- Keep generic where the detail belongs in the body; the description is a router.

### Dynamic context injection (DCI)

Claude Code can run a shell command at skill-load time and splice its output into
the `SKILL.md`. Write `` !`command` `` inline (the `!` must be at the start of a
line or after whitespace) or a ` ```! ` fenced block for multi-line commands. See
the [Claude Code docs](https://code.claude.com/docs/en/skills#inject-dynamic-context).

- **Use it for context that goes stale** — CLI `--help` output, version strings,
  environment info. It replaces a hand-maintained flag list with the live one.
- **Safe for multi-agent.** On non-Claude-Code agents (OpenCode, pi) the markup
  isn't expanded; the agent sees the literal placeholder and runs the command
  itself. Validated across haiku/sonnet/opus with zero hallucinations.
- **Use judgment.** Inject where help output replaces a manually-maintained list.
  Keep non-discoverable gotchas/traps (confusing arg order, wrong-flag warnings)
  as **static** text — a `--help` dump won't surface them.
- **Mind the length budget.** If injecting help would push a `SKILL.md` over the
  150-line ceiling, put the DCI in a reference file and link to it instead.

### Bash helper scripts (`skills/**/*.sh`)

- Start with `set -Eeuo pipefail` (add an `ERR` trap for non-trivial scripts).
- Prefer `glab ... --field key=val` over `--raw-field` with shell interpolation
  of untrusted content (avoids shell-expansion of `$`, backticks, etc.).
- Never use `[ -f glob* ]` — `[ ]` does not glob-expand, so it silently never
  matches. Use a `for` loop or `compgen -G`.

*Enforced:* `scripts/lint_shell.sh` runs `shellcheck` over every script under
`skills/` in CI (catches the glob-test footgun as `SC2144`, unquoted
expansions, and more).

## Workflow

1. Create `skills/<name>/SKILL.md` with frontmatter (`name`, `description`,
   `version`, `license`); keep it lean (see above).
2. `bin/distribute-skill <name>` — register for OpenCode / Claude Code / pi.
3. `lefthook run auto-fix` — regenerate README table, ToC, catalog, manifests.
4. **Bump the `version`** field whenever any file under `skills/<name>/` changes
   (`check_version_bump.py` gates this against `main`).
5. `bin/ci-checks` — run all checks locally before pushing.

## Checks (run by `bin/ci-checks`, lefthook pre-push, and CI)

| Check | What it enforces |
|---|---|
| `validate_frontmatter.py` | Required fields, semver, **kebab name == dir name** |
| `validate_skill_length.py` | SKILL.md length (warn-only: <100 target, 150 cap) |
| `lint_shell.sh` (shellcheck) | Bash footguns in `skills/**/*.sh` |
| `check_version_bump.py` | `version` bumped when a skill changes |
| `update_skills_list.py` / `update_toc.py` / `generate_catalog.py` / `update_claudecode_readme.py` | Generated README/catalog/manifests are in sync |
| `validate-{opencode,claudecode,pi}-distribution.py` | Per-channel distribution format |
| `sync_skill.py` / `bin/sync-skill` | SKILL.md versions synced into plugin manifests |

If a generated file is out of sync, run `lefthook run auto-fix` and commit the
result — don't hand-edit generated files.

See `doc/contributing.md` for the full frontmatter reference and setup.
