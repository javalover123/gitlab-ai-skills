# Before requesting a database review

Maps to GitLab's [database review guidelines](https://docs.gitlab.com/development/database_review/).

1. **List the queries** the change adds or modifies (watch for N+1).
   - CI: the `rspec:merge-auto-explain-logs` job in the MR pipeline records the queries the
     specs run with their plans, and shows which are new compared with the default branch.
   - Locally: load an `ActiveSupport::Notifications` subscriber on `sql.active_record` (for
     example with `rspec -r`) that logs distinct statements, or read `log/test.log`.
2. **Plan each one** on the clone: `joe plan`, then `joe explain` with realistic
   parameters (large project or namespace, not an empty one).
3. **Fix what's slow**: apply the loop in [plan-analysis.md](plan-analysis.md).
4. **Migrations**: test new indexes with `joe exec` (+ `ANALYZE`), then `joe reset`. Check them
   against the [migration guidelines](https://docs.gitlab.com/development/migration_style_guide/)
   (concurrent index creation, naming, need). Time limits for queries and migrations are in the
   database review docs above.
5. **Write up in the MR**: for each query, the SQL, a plan link, and timing/buffers
   (see [Linking plans](#linking-plans)). Replace real values with placeholders; no production data.
6. Request the review with that evidence attached.

## Linking plans

The CLI doesn't return a console URL. `joe <cmd> --json` has `command_id`, `plan_text`, `plan_execution_*`,
`stats` and no session ID. Text output prints `command <id>`, also without a session. `joe_sessions` and
`joe_session_commands` are `permission denied` for CLI API keys, so the CLI can't build the link for you.

Console URL format:

```text
https://console.postgres.ai/gitlab/projects/<alias>/sessions/<session>/commands/<command>
```

Recipe that works:

1. Open the console session history for the project (`<alias>` as in `postgresai projects`, such as
   `gitlab-production-main`). The CLI shares sessions with the console.
2. Find your command in the session and copy its URL. The command number there is the one to use.
3. Put that URL in the MR next to the sanitized summary.

- **Unconfirmed:** whether the CLI's `command_id` (for example 511294) resolves under `/commands/<id>`. The
  numbers are far from console command numbers (hundreds of thousands apart), which suggests separate
  sequences. Don't build URLs from `command_id` unless someone confirms it in a logged-in browser. Unauthenticated
  requests can't tell: the console returns its HTML shell with 200 for any path.
- A session ID can appear in an error string (``Session: `61473` ``). It identifies the session only, not a command.
- **Who can open it:** console pages show the raw query with production IDs and need Database Lab access, which
  community contributors usually lack. Keep the sanitized summary (timings, buffers, plan shape) in the MR next
  to the link.
- **Not a sanitized alternative by default:** pasting into explain.depesz.com or explain.dalibo.com creates a public
  object. Sanitize first and get the human's OK before posting.
