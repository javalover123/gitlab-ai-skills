# Agent guidance for gitlab-org/ai/skills

This repo hosts reusable agent **skills** — each is a `skills/<name>/SKILL.md`
with YAML frontmatter plus Markdown content, distributed to OpenCode, the
`.agents/skills/` convention, Claude Code, and pi. Most contributions add or
edit a skill. Read this before writing.
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
- **Quote values containing colons** — an unquoted `description: foo: bar` is
  invalid YAML and will silently break skill loading for consumers (pi.dev, Duo
  CLI). Wrap in double quotes: `description: "foo: bar"`.
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
- Pass untrusted content as a field value (`--field` or `--raw-field`). Do not
  build it into an interpolated command string.
- For a GraphQL `String` variable, use `-f`/`--raw-field`. `-F`/`--field`
  infers types: it sends an integer-like value as a JSON number, and GitLab
  rejects it ("Could not coerce value 2332 to String").
- Never use `[ -f glob* ]` — `[ ]` does not glob-expand, so it silently never
  matches. Use a `for` loop or `compgen -G`.

*Enforced:* `scripts/lint_shell.sh` runs `shellcheck` over every script under
`skills/` in CI (catches the glob-test footgun as `SC2144`, unquoted
expansions, and more).

### Skill test suites (`skills/**/tests/test_*.sh`)

A skill whose helper scripts are non-trivial may ship its own tests. They're
optional — most skills have nothing to test — but if present they must:

- live at `skills/<name>/tests/test_*.sh` (that glob is what CI discovers),
- run with no arguments and exit non-zero if any case fails,
- need **no network and no credentials** — stub out `glab`, `skopeo`, etc. by
  putting a fake on `PATH`, so the suite is reproducible even when a
  feature flag or registry is unavailable.

Keep fixtures beside them in `tests/`. Test scripts are exempt from the
`set -Eeuo pipefail` rule to the extent they need to count failures rather than
abort on the first one, but they are still shellcheck-linted.

*Enforced:* `scripts/run_skill_tests.sh` discovers and runs every suite in CI
and on pre-push.

### Synced skills (source of truth elsewhere)

Some skills are **synced in** from another repository — their source of truth
(SSoT) lives upstream and this repo is only the destination. They're listed in
[`synced-skills.yml`](synced-skills.yml).

- **Don't edit them here.** The `guard-synced-skills` MR-pipeline job fails any
  MR that touches a synced skill's directory. Fix the skill at its source
  (`source_project` / `source_path` in the manifest) instead.
- A scheduled pipeline (`SCHEDULE_TYPE=sync_skills`) runs
  `scripts/sync_external_skills.py`, mirrors the upstream copy (including
  deletions), runs `lefthook run auto-fix`, and opens an MR as the sync bot.
- The version comes from upstream — no manual bump for synced skills.

## Workflow

1. Create `skills/<name>/SKILL.md` with frontmatter (`name`, `description`,
   `version`, `license`); keep it lean (see above).
2. `bin/distribute-skill <name>` — register for OpenCode / `.agents/skills/` /
   Claude Code / pi.
3. `lefthook run auto-fix` — regenerate README table, ToC, catalog, manifests.
4. **Bump the `version`** field whenever any file under `skills/<name>/` changes
   (`check_version_bump.py` gates this against `main`).
5. `bin/ci-checks` — run all checks locally before pushing.

## Checks (run by `bin/ci-checks`, lefthook pre-push, and CI)

| Check | What it enforces |
|---|---|
| `validate_frontmatter.py` | Required fields, semver, **kebab name == dir name**, **strict YAML parse**¹ |
| `validate_skill_length.py` | SKILL.md length (warn-only: <100 target, 150 cap) |
| `validate_content_quality.py` | Broken relative links (**hard fail**); missing "When to Use"/"Use when"/"Triggers" cue, stray TODO/FIXME, and AGENTS.md-banned voice words (warn-only)² |
| `lint_shell.sh` (shellcheck) | Bash footguns in `skills/**/*.sh` |
| `run_skill_tests.sh` | Skill-shipped suites (`skills/**/tests/test_*.sh`) pass |
| `check_version_bump.py` | `version` bumped when a skill changes |
| `update_skills_list.py` / `update_toc.py` / `generate_catalog.py` / `update_claudecode_readme.py` | Generated README/catalog/manifests are in sync |
| `validate-{opencode,claudecode,pi}-distribution.py` | Per-channel distribution format |
| `sync_skill.py` / `bin/sync-skill` | SKILL.md versions synced into plugin manifests |
| `check_synced_skills_untouched.sh` | MR doesn't edit a synced skill (SSoT elsewhere) |

¹ The strict YAML parse requires PyYAML. CI always has it; locally the check
is best-effort — if PyYAML is missing the script prints a visible warning and
skips the strict pass. Install with `pip install PyYAML` for full local
coverage.

² Only broken relative links fail the build. Structure and voice findings are
warn-only for now (like `validate_skill_length.py`) so they surface offenders
without blocking unrelated MRs; the intent is to promote them to hard gates
once the corpus is clean. Links in every `SKILL.md` **and** its `references/*.md`
are checked. Unit tests: `scripts/tests/test_content_quality.py` (run via the
`validate-frontmatter` job's `unittest discover`).

If a generated file is out of sync, run `lefthook run auto-fix` and commit the
result — don't hand-edit generated files.

See `doc/contributing.md` for the full frontmatter reference and setup.
