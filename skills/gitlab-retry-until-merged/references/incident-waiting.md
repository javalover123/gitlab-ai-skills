# Phase 3: Waiting Out Incidents and Broken Master

Retrying into a live incident burns one of the three retries on a run that
will almost certainly fail again. Wait for the cause to clear first. Waiting
costs no retries.

## Signals

```bash
python3 scripts/incident_status.py            # --hours N widens the master-broken window (default 12)
```

| Field | Source | Notes |
|-------|--------|-------|
| `status_page` | status.gitlab.com | `operational`, `degraded_components`, `active_incidents` with links |
| `production_incidents` | `gitlab-com/gl-infra/production`, `Incident::Active` | S1/S2 only by default (`--all-severities` for S3/S4). Some stay open for weeks; match on title and `Service::` label, not presence alone. |
| `master_broken_incidents` | `gitlab-org/quality/engineering-productivity/master-broken-incidents` | Opened in the window. Titles name the broken jobs; `master-broken::*` labels give the triage cause. |

A signal that couldn't be fetched shows `{"error": ...}`. Treat it as unknown,
not as "all clear". An incident matched through that signal hasn't cleared,
so keep waiting; MAX_WAIT still bounds the wait.

Write down the **specific** incidents that matched in Phase 2: their IDs, links, or
component names. You're waiting for those to clear, not for GitLab.com to be
spotless.

## Wait loop

Keep watching the MR while waiting, so a push, closure, or cancellation still
stops you. `--mr-only` makes the watcher ignore the already-failed pipeline and
return `TIMEOUT` after about 8 minutes unless the MR itself changes:

```pseudocode
WAIT_START = now, MIN_WAIT = 15 min, MAX_WAIT = 2 h   # defaults; the user may change them
loop:
    event = $WATCH/scripts/watch_mr.py --expect-sha EXPECT_SHA --auto-merge --mr-only MR_URL
    if event == API_ERROR: expected during an incident, so keep waiting
    elif event != TIMEOUT: handle it per watching.md (usually alert and stop)
    signals = incident_status.py
    if now - WAIT_START >= MIN_WAIT and matched incidents have cleared: break → Phase 4
    if now - WAIT_START >= MAX_WAIT: alert "incident still active after 2h", stop
```

## When is it "cleared"?

- **Status page**: the matched component is back to `Operational` and the
  matched incident is no longer in `active_incidents`.
- **Production incident**: closed, or no longer labeled `Incident::Active`:
  `glab api "projects/gitlab-com%2Fgl-infra%2Fproduction/issues/<iid>"` (read `state` and `labels`)
- **Master-broken incident**: closed, meaning the fix or revert has landed:
  `glab api "projects/gitlab-org%2Fquality%2Fengineering-productivity%2Fmaster-broken-incidents/issues/<iid>"` (read `state` and `labels`)
  Load-labeled ones (`gitlab-com-overloaded`) often stay open after the load
  passes. For those, use the status page and production incidents instead.
- **Broken master with no incident**: the same job has passed on a target-branch
  pipeline that started after the failure.

MIN_WAIT gives queues time to drain after an incident is marked resolved.
