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
5. **Write up in the MR**: for each query, the SQL, the sanitized plan inline (placeholders, not real
   IDs), and timing/buffers. Console links are an optional extra, see [Linking plans](#linking-plans).
   No production data.
6. Request the review with that evidence attached.

## Linking plans

**CLI runs can't be linked automatically today.** `joe <cmd> --json` returns `command_id`, `plan_text`,
`plan_execution_*`, `stats`, but no session ID and no console command number or URL. The CLI `command_id`
doesn't work in a console URL (`.../sessions/<session>/commands/<command_id>` returns 404), and
`joe_sessions` / `joe_session_commands` are `permission denied` for CLI API keys.

Inline sanitized plans stay the primary MR evidence. A console link is an optional extra for people with
Database Lab access; the page shows the raw query with production IDs, so community contributors most likely
can't open it. Keep the sanitized summary in the MR either way.

Manual recipe (verified on `gitlab-production-ci`):

1. Get the numeric session ID from an error string. Either shape works:
   ``Session: `61473` `` (use `61473`) or ``Session: `webui-i61418` `` (use `61418`, drop `webui-`).
2. Open `https://console.postgres.ai/gitlab/projects/<alias>/sessions/<session>` (`<alias>` as in
   `postgresai projects`, such as `gitlab-production-ci`). It opens with the command history.
3. Pick each run from the history by hand: match the query text (for example a root namespace ID in the SQL
   against your local log). Cold and warm runs share the same SQL, so compare the `Limit` `actual time`.
4. Copy the command URL, `.../sessions/<session>/commands/<console command number>`. A URL copied this way
   works. The console command number isn't exposed by the CLI or API.

Unverified:

- The session URL built from a plain ID on `gitlab-production-main` (`61473`): matches an existing console
  link, but nobody has opened one built this way.
- Whether other GitLab team members can open a link from someone else's session.
- Whether `joe reset` keeps the same session, so that all runs stay in one history.
- Pasting into explain.depesz.com or explain.dalibo.com creates a public object: sanitize first and get the
  human's OK.

Upstream gap: the CLI's `--json` output should include `session_id` and the console command ID or URL.
