---
name: postgresai
description: "Run EXPLAIN / EXPLAIN ANALYZE, test indexes, and measure query cost on PostgresAI Database Lab thin clones with the PostgresAI CLI (postgresai, pgai, Joe). Use when asked to explain or optimize a query, check a plan at production scale, try an index on realistic data, or prepare a GitLab database review."
version: 1.0.0
license: MIT
category: Database
---

# PostgresAI CLI (Database Lab / Joe)

Run `EXPLAIN` and DDL experiments on ephemeral thin clones of production-sized data
from the terminal, instead of pasting into the Joe chat bot.

## When to Use

- Checking how a new or changed query plans at production scale.
- Testing an index or migration idea on a thin clone.
- Collecting queries and plans as evidence for a database review.

Not for local development databases (GitLab: use `gitlab-psql`).

## Install

Prefer npm: `npm i -g postgresai` (or `npx postgresai ...`). Binaries: `postgresai`, `pgai`.
A Homebrew tap may be documented elsewhere but may no longer exist; don't rely on it.

## Authenticate

`postgresai auth show-key` shows whether a key is stored. If not, run `postgresai login`
(browser OAuth; the callback listens on `127.0.0.1`, port selectable with `--port`).
Headless: `postgresai login --set-key <key>` or set `PGAI_API_KEY`. Never commit or print the key.

## Pick the target

```shell
postgresai projects        # JOE column shows which projects are ready
```

Pass `--project <id|alias>` (or `--instance-id <id>`) to `joe`, or store a default once with
`postgresai set-default-project <alias>`; `joe --help` wrongly says `--project` is always required.
Prefer entries with JOE `ready` (skips stale `-deprecated`/`-new` duplicates). Ask the user
which database to target if it's ambiguous.

## Core loop

Run `joe` through [scripts/joe.sh](scripts/joe.sh) (path relative to this skill): same arguments as
`postgresai joe`, but it waits for commands that outlive the CLI's poll budget and prints only the result.

```shell
J=scripts/joe.sh; P="--project <alias>"
$J plan     $P "SELECT ..."            # estimates only, never executes: default
$J explain  $P "SELECT ..."            # EXPLAIN + ANALYZE + buffers, executes on clone
$J describe $P <table>                 # \d-style metadata
$J exec     $P "CREATE INDEX ..."      # real DDL on the clone; prints only the duration
$J exec     $P "ANALYZE <table>"       # refresh stats so the planner sees the new index
$J explain  $P "SELECT ..."            # re-measure
$J reset    $P                         # discard experiments
```

Interpreting plans and iterating: [references/plan-analysis.md](references/plan-analysis.md).

## Gotchas

- **Budget:** plain `postgresai joe` returns exit 0 after `--budget` (default 25 s) with
  `started <id> · pending … resume: pgai joe result <id>`; the command keeps running.
  `joe result <id>` returns at once, exit 1 while pending. `joe.sh` polls for you
  (`JOE_WAIT_SECONDS`, default 600; exit 1 on timeout).
- **Don't `reset` to stop a slow command**: it kills pending work (`conn closed`). Use
  `joe activity` and `joe terminate <pid>` for a runaway query.
- **`hypo` (HypoPG) was not observed to persist between CLI calls**, so a later
  `plan` won't show it. Test indexes with `exec CREATE INDEX` +
  `exec ANALYZE` + `explain`. Its args omit the word `hypo` (`hypo $P "desc"`).
- `explain` and `exec` actually execute, so bound queries (`LIMIT`, scoped by tenant/project
  id). `exec` returns no rows.
  `joe.sh` is text-only; for JSON use the raw CLI with `--json` and poll
  `postgresai joe result <id> --json` (exit 1 and `"status":"pending"` while running).
- **Clone creation can fail** with an infra error (`failed to create a Database Lab clone`).
  Report it; don't retry in a loop. Switch target only if another database can answer the question.
- Explicit clones (`postgresai dblab clone create|list|status|reset|destroy`) are rarely
  needed. Never pass `--protected`; destroy yours if your role allows it (it needs Admin or
  AllFeaturesUser), otherwise let auto-deletion handle it.

## Safety rules

- Only experiment through the clone commands; never run writes or DDL against
  production or replicas by any other route.
- Always `joe reset` when finished.
- Clone data is real production data. **Never paste row values, emails, tokens or
  result sets** into public MRs, issues, or repos. Share SQL, plans with literals
  replaced by placeholders, and timings/buffer counts only.
- Clones may enforce statement timeouts; don't retry a timeout in a loop.

## GitLab-specific

For the GitLab monolith, see [references/gitlab.md](references/gitlab.md): which aliases to
target, and the database-review flow ([references/db-review-flow.md](references/db-review-flow.md)).

## CLI reference (live)

Flags change between releases; check the installed CLI:

!`postgresai joe --help 2>&1 | head -30`
