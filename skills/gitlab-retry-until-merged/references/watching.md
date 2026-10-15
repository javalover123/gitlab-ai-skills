# Phases 0–1: Preflight and Watching

## Phase 0: Resolve and preflight

The argument is the MR URL. Do **not** fall back to the current branch: the MR
belongs to someone else and is unlikely to be checked out. If no URL was
given, ask for one.

```bash
STATE=$(python3 "$WATCH/scripts/mr_state.py" --files "$MR_URL")   # $WATCH: the gitlab-pipeline-watch skill
```

Check before watching anything:

| Field | Required | If not |
|-------|----------|--------|
| `state` | `opened` | `merged` → report done. `closed` → alert and stop. |
| `auto_merge` | `true` | Alert and stop: the premise of this skill is that auto-merge is set. Don't set it yourself. |
| `sha` | — | Record it as `EXPECT_SHA`. Every later check compares against it. |
| `changed_files` | — | Keep it; Phase 2 correlates failures with it. |

`pipeline.sha` is **not** the MR head: a merged-results pipeline runs on a
temporary merge commit. Compare the MR's `sha`, never the pipeline's.

If the pipeline is already `failed`, go straight to Phase 2. Otherwise start
watching.

## Phase 1: Watch

```bash
python3 "$WATCH/scripts/watch_mr.py" --expect-sha "$EXPECT_SHA" --auto-merge --seen "$SEEN" "$MR_URL"
```

`--expect-sha` stops on a push and `--auto-merge` stops if auto-merge is
canceled, and keeps waiting through green until the MR merges. The full flag and
event list is in `gitlab-pipeline-watch`'s `references/watch-mr.md`. It polls
every 60 seconds and returns after about 8 minutes, so one call fits a
10-minute tool limit. If your agent can run longer blocking commands,
raise `--timeout`. `SEEN` is a comma-separated list of failed job and bridge
IDs already triaged.

After a `retry.py pipeline` call, pass `--grace 120`: a retried pipeline can
still read as `failed` for a moment, and without a grace period the watcher
returns the stale failure immediately.

## Events

| Event | Meaning | Reaction |
|-------|---------|----------|
| `MERGED` | Done. | Report success (Phase 5) and exit. |
| `TIMEOUT` | Nothing actionable yet. | Watch again. Not a failure; doesn't touch the budget. |
| `NEW_FAILURE` | A blocking job failed while other jobs still run. | Triage just the new failures (Phase 2). MR_RELATED or UNKNOWN → alert now; the pipeline cannot pass. Otherwise add their IDs to `SEEN` and keep watching. Retries wait for the pipeline to finish, so one retry covers every failure. |
| `PIPELINE_FAILED` | Pipeline finished red. | Phase 2 over **all** blocking failures (`failed_jobs` + `failed_bridges`). If both are empty (for example a CI config error, which the MR may have caused), classify UNKNOWN and alert. |
| `API_ERROR` | Three polls in a row failed. GitLab itself may be erroring. | Run `incident_status.py`, then watch again. Doesn't touch the budget. If the API still errors after 30 minutes, alert. |
| `SHA_CHANGED` | Someone pushed. GitLab canceled auto-merge and the new commits need review. | Alert and stop. |
| `AUTO_MERGE_OFF` | Auto-merge was canceled: by a person, or because a merge train pipeline failed and dropped the MR. | Alert and stop. Re-adding is the user's call. |
| `CLOSED` | MR closed. | Alert and stop. |
| `PIPELINE_CANCELED` | Somebody canceled the pipeline. | Alert and stop: don't override a person's decision. |
| `PIPELINE_SKIPPED` / `PIPELINE_MANUAL` / `NO_PIPELINE` | Nothing will run by itself. | Alert and stop. Don't play manual jobs. |

### Green but not merging

On `success` the watcher keeps waiting for `MERGED`. If two consecutive
`TIMEOUT`s show `pipeline.status == "success"` and the MR is still open, read
`detailed_merge_status` and `merge_error`:

- `mergeable`, `ci_must_pass`, `ci_still_running`, `checking`, `unchecked`:
  GitLab is still working, so watch again. With merge trains, a new
  `merge_train` pipeline appears as the latest pipeline; watch it.
- `need_rebase`, `conflict`: only a push can fix it. Alert; never rebase.
- Anything else (`not_approved`, `discussions_not_resolved`, `draft_status`,
  `blocked_status`, `requested_changes`, `commits_status`, …) or a non-null
  `merge_error`: a human gate. Alert.

Cap the wait: if the pipeline has been green for 30 minutes without a merge,
whatever the status says, alert. This is the one case where you stop waiting
without a failure.
