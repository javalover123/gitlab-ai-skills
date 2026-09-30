---
name: postgresai
description: "Use when measuring, EXPLAINing or optimizing PostgreSQL queries against GitLab's Database Lab thin clones with the PostgresAI CLI (postgresai/pgai, Joe), or before requesting a GitLab database review."
version: 1.0.0
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
postgresai projects        # shows which projects have Joe ready
```

Every `joe` subcommand except `result` needs `--project <id|alias>` or `--instance-id <id>`.
Use the GitLab main database project (see the
[GitLab Database Lab docs](https://docs.gitlab.com/development/database/database_lab/#use-the-postgresai-cli)
for which instance holds `main`, `ci`, etc.). Ask if it's ambiguous.

## Core loop

```shell
P="--project <alias>"
postgresai joe plan    $P "SELECT ..."     # plan only, never executes: default
postgresai joe explain $P "SELECT ..."     # EXPLAIN + ANALYZE, executes on clone
postgresai joe describe $P projects        # \d-style metadata
postgresai joe hypo    $P "create index on issues (project_id, state_id)"  # HypoPG
postgresai joe exec    $P "CREATE INDEX ..."   # real DDL on the clone only
postgresai joe explain $P "SELECT ..."     # re-measure
postgresai joe reset   $P                  # discard experiments
```

Start with `plan`, then `explain`. `--budget <s>` is a poll budget (default 25); if it
expires, fetch the output with `postgresai joe result <commandId>`. Add `--json` to parse.
Interpreting plans and iterating: [references/plan-analysis.md](references/plan-analysis.md).

Explicit clones (`postgresai dblab clone create|list|status|reset|destroy`) are rarely
needed; if you create one, destroy it when done.

## Safety rules

- Only experiment on the clone. `exec` and `explain` run there; never run writes or DDL
  against production/replicas through any other route.
- Always `joe reset` (or destroy clones you created) at the end.
- Clone data is real production data. **Never paste row values, emails, tokens or
  result sets** into public MRs, issues, or this repo. Share SQL, plans with literals
  replaced by placeholders, and timings/buffer counts only.
- Keep queries bounded (`LIMIT`, scoped by `project_id`/`namespace_id`); statement
  timeouts on clones still apply, so don't retry timeouts in a loop.

## Before a database review

Follow [references/db-review-flow.md](references/db-review-flow.md): collect each new query,
its plan on the clone, and link them in the MR.

## CLI reference (live)

Flags change between releases; check the installed CLI:

!`postgresai joe --help 2>&1 | head -30`
