---
name: postgresai
description: "Run EXPLAIN / EXPLAIN ANALYZE, test indexes, and measure query cost on PostgresAI Database Lab thin clones with the PostgresAI CLI (postgresai, pgai, Joe). Use when asked to explain or optimize a query, check a plan at production scale, try an index on realistic data, or prepare a GitLab database review."
version: 1.0.0
license: MIT
---

# PostgresAI CLI (Database Lab / Joe)

Run `EXPLAIN` and DDL experiments on ephemeral thin clones of production-sized data
from the terminal, instead of pasting into the Joe chat bot.

## When to Use

- Checking how a new or changed query plans at production scale.
- Testing an index or migration idea on a thin clone.
- Collecting queries and plans as evidence for a database review.

Not for local development databases; use a plain `psql` workflow there.

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

Every `joe` subcommand except `result` needs `--project <id|alias>` or `--instance-id <id>`.
Ask the user which database to target if it's ambiguous.

## Core loop

```shell
P="--project <alias>"
postgresai joe plan     $P "SELECT ..."            # estimates only, never executes: default
postgresai joe explain  $P "SELECT ..."            # EXPLAIN + ANALYZE + buffers, executes on clone
postgresai joe describe $P <table>                 # \d-style metadata
postgresai joe hypo     $P "create index on <table> (<cols>)"   # HypoPG
postgresai joe exec     $P "CREATE INDEX ..." --budget 300      # real DDL, clone only
postgresai joe explain  $P "SELECT ..."            # re-measure
postgresai joe reset    $P                         # discard experiments
```

Interpreting plans and iterating: [references/plan-analysis.md](references/plan-analysis.md).

## Gotchas

- **Budget:** `--budget` (default 25 s) is only a poll limit. When it expires the command
  keeps running and prints `pgai joe result <id>`; fetch it with `postgresai joe result <id>`.
  Index builds on big tables take minutes: pass a large `--budget`.
- **Never `reset` while a command is pending**: it kills it (`conn closed`).
- **`hypo` args omit the word `hypo`** (`hypo $P "desc"`, not `"hypo desc"`) and print
  nothing on success. Confirm with `joe plan`, which shows whether the planner uses it.
- Start with `plan`; `explain` and `exec` actually execute, so bound queries
  (`LIMIT`, scoped by tenant/project id). `--json` gives parseable output.
- Explicit clones (`postgresai dblab clone create|list|status|reset|destroy`) are rarely
  needed; destroy any you create.

## Safety rules

- Only experiment through the clone commands; never run writes or DDL against
  production or replicas by any other route.
- Always `joe reset` (or destroy clones you created) at the end.
- Clone data is real production data. **Never paste row values, emails, tokens or
  result sets** into public MRs, issues, or repos. Share SQL, plans with literals
  replaced by placeholders, and timings/buffer counts only.
- Statement timeouts on clones still apply; don't retry a timeout in a loop.

## GitLab-specific

For the GitLab monolith, see [references/gitlab.md](references/gitlab.md): which aliases to
target, and the database-review flow ([references/db-review-flow.md](references/db-review-flow.md)).

## CLI reference (live)

Flags change between releases; check the installed CLI:

!`postgresai joe --help 2>&1 | head -30`
