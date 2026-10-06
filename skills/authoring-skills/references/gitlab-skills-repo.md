# Contributing to gitlab-org/ai/skills

These rules apply **only** when the skill lives in the `gitlab-org/ai/skills`
repository. Elsewhere, follow the target project's own conventions. If the repo
is checked out, its root `AGENTS.md` is authoritative over this summary.

- **Name:** kebab-case, lowercase; `name:` must equal the directory name. Prefix
  tool-specific skills by domain (`gitlab-`, `mr-`); no redundant verb
  (`commit-messages`, not `writing-commit-messages`).
- **Required frontmatter:** `name`, `description`, `version` (semver), `license`
  (`MIT`). Quote descriptions containing colons.
- **`version`:** bump on any change under the skill directory; CI compares to `main`.
- **`compatibility`:** convention is `opencode`.
- **`category`:** Title Case, reuse an existing label: `Development Workflow`,
  `Testing`, `Database`, `Agent Tooling`, `Shell & Environment`; this skill uses
  `Meta / Authoring`.
- **Length:** `SKILL.md` under 100 lines, hard ceiling 150; push detail into
  `references/`.
- **Shell scripts:** `set -Eeuo pipefail`; pass untrusted input as a field value,
  not interpolated into a command string; for GraphQL `String` variables use
  `-f`/`--raw-field` (`-F` turns integer-like values into numbers); never
  `[ -f glob* ]` (use a `for` loop or `compgen -G`); run `shellcheck`.
- **Tests:** optional `skills/<name>/tests/test_*.sh`; no arguments, no network or
  credentials (stub CLIs via `PATH`), non-zero exit on failure.
- **Synced skills:** skills listed in the repo's `synced-skills.yml` are edited
  upstream, not here; MRs touching them fail CI.
- **Workflow:** `bin/distribute-skill <name>`, then `lefthook run auto-fix`
  (regenerates README/catalog/manifests; don't hand-edit those), then
  `bin/ci-checks` before pushing.
