---
name: postgresai
description: "Run EXPLAIN / EXPLAIN ANALYZE, test indexes, and measure DB queries on GitLab Database Lab thin clones with the PostgresAI CLI (postgresai, pgai, Joe). Use when asked to explain/optimize a query, check a query plan at production scale, try an index, or prepare for a GitLab database review. Not for local GDK databases (use gitlab-psql)."
version: 1.1.0
license: MIT
---

# PostgresAI CLI (Database Lab / Joe)

Run `EXPLAIN` and DDL experiments on ephemeral thin clones of production-like
data from the terminal, instead of pasting into the Joe Slack bot. For local
GDK databases use `gitlab-psql` instead; this skill is for production-sized data.

## When to Use

- Checking how a new or changed query plans at production scale.
- Testing an index or migration idea on a thin clone.
- Preparing the queries and plans for a GitLab database review.

## Install

Prefer npm: `npm i -g postgresai` (or `npx postgresai ...`). Binaries: `postgresai`, `pgai`.
The Homebrew tap mentioned on postgres.ai may no longer exist; don't rely on it.

## Authenticate

`postgresai auth show-key` tells you whether a key is stored. If not, run `postgresai login`
(OAuth). The browser callback goes to `127.0.0.1`, so on a **remote VM** pin a port and forward it:

```shell
postgresai login --port 53682              # on the VM
ssh -L 53682:127.0.0.1:53682 <vm>          # on the laptop, then open the printed URL
```

Headless alternative: `postgresai login --set-key <key>` or `PGAI_API_KEY`.
Never commit or print the key.

## Pick the target

```shell
postgresai projects        # JOE column = ready; aliases can change
```

Every `joe` subcommand except `result` needs `--project <id|alias>` or `--instance-id <id>`.
The GitLab main and CI databases are `gitlab-production-main` and `gitlab-production-ci`;
other databases (registry, sec, ...) are listed by `projects`. Ignore `*-deprecated`
entries. See the
[GitLab Database Lab docs](https://docs.gitlab.com/development/database/database_lab/#use-the-postgresai-cli).

## Core loop

```shell
P="--project gitlab-production-main"
postgresai joe plan     $P "SELECT ..."            # estimates only, never executes: default
postgresai joe explain  $P "SELECT ..."            # EXPLAIN + ANALYZE + buffers, executes on clone
postgresai joe describe $P projects                # \d-style metadata
postgresai joe hypo     $P "create index on issues (project_id, state_id)"  # HypoPG
postgresai joe exec     $P "CREATE INDEX ..." --budget 300   # real DDL, clone only
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
  (`LIMIT`, scoped by `project_id`/`namespace_id`). `--json` gives parseable output.
- Explicit clones (`postgresai dblab clone create|list|status|reset|destroy`) are rarely
  needed; destroy any you create.

## Safety rules

- Only experiment on the clone. `exec` and `explain` run there; never run writes or DDL
  against production/replicas through any other route.
- Always `joe reset` (or destroy clones you created) at the end.
- Clone data is real production data. **Never paste row values, emails, tokens or
  result sets** into public MRs, issues, or this repo. Share SQL, plans with literals
  replaced by placeholders, and timings/buffer counts only.- Statement timeouts on clones still apply; don't retry a timeout in a loop.

## Before a database review

Follow [references/db-review-flow.md](references/db-review-flow.md): collect each new query,
its plan on the clone, and link them in the MR.

## CLI reference (live)

Flags change between releases; check the installed CLI:

!`postgresai joe --help 2>&1 | head -30`
