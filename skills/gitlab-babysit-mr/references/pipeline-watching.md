# Phase 1: Watch for Blocking Failures or Pipeline Completion

Use the **`gitlab-pipeline-watch`** skill's `watch_mr.py` as the babysitter's poll; `$WATCH` below is that skill's directory. It polls every 60 seconds and returns as soon as a blocking job fails, even if other jobs are still running, so retryable failures do not wait for pipeline completion. Its `failed_jobs` already excludes `allow_failure: true` and superseded retried jobs. Full flags and events: `$WATCH/references/watch-mr.md`.

Do not pass `--expect-sha` or `--auto-merge`: the babysitter pushes its own fixes, and it stops when the pipeline is green rather than waiting for a merge.

```pseudocode
SEEN_EARLY_FAILURE_IDS=set()
PREV_PIPELINE_ID=null       # record the old pipeline ID before pushing
NEW_PIPELINE_DEADLINE=null  # set to now + 15 minutes at the same time

WAITING_FOR_FIRST=false     # the MR had no pipeline yet

loop:
    args = --seen SEEN_EARLY_FAILURE_IDS
    if PREV_PIPELINE_ID:   args += --newer-than PREV_PIPELINE_ID
    if WAITING_FOR_FIRST:  args += --newer-than 0     # wait for any pipeline
    result = python3 $WATCH/scripts/watch_mr.py args "$MR_URL"

    case result.event:
        TIMEOUT, API_ERROR:  continue          # not a failure; watch again
        NO_NEW_PIPELINE:
            if PREV_PIPELINE_ID and now >= NEW_PIPELINE_DEADLINE:
                EXIT_REASON=NO_NEW_PIPELINE; break
            continue                           # no first pipeline yet: keep waiting
        NO_PIPELINE:         WAITING_FOR_FIRST=true; continue
        MERGED, CLOSED:      report the state and exit

    # Any other event means the watcher saw a newer (or first) pipeline.
    PREV_PIPELINE_ID=null; NEW_PIPELINE_DEADLINE=null; WAITING_FOR_FIRST=false

    case result.event:
        NEW_FAILURE:         EXIT_REASON=EARLY_FAILURE; break
        PIPELINE_SUCCESS, PIPELINE_FAILED, PIPELINE_CANCELED,
        PIPELINE_SKIPPED, PIPELINE_MANUAL:
                             EXIT_REASON=TERMINAL; break
```

The watcher only gets past `--newer-than` after it sees a newer pipeline, so any event other than `NO_NEW_PIPELINE`, `TIMEOUT`, `API_ERROR`, or `NO_PIPELINE` satisfies the push guard. `NO_PIPELINE` returns immediately, so never re-run the watcher on it without `--newer-than 0`; that would poll with no sleep.

Keep watching while the pipeline is running. A `TIMEOUT` is not a pipeline failure and does not consume an action round.

Before pushing, record the current `pipeline.id` (from the last watcher result, or `python3 $WATCH/scripts/mr_state.py "$MR_URL"`) as `PREV_PIPELINE_ID` so a fast new pipeline is not mistaken for the old one. After the push, set `NEW_PIPELINE_DEADLINE` to now + 15 minutes and return to the loop. A job or pipeline retry stays in the same pipeline and does not need this guard; pass `--grace 120` on the next watch instead, because the retried pipeline can still read as failed for a moment.

On `NO_NEW_PIPELINE` past the deadline, do not analyze or report the old run as the new one. If awaiting Duo Developer's fix, use the [local auto-fix fallback](lint-fix-delegation.md#step-5-fallback-local-auto-fix); otherwise report that the push produced no new pipeline and investigate. This deadline applies only to waiting for a *new* pipeline, not to a pipeline already running.

On `EARLY_FAILURE` or `TERMINAL`, the watcher's output is the full snapshot needed for analysis and reporting: the MR head `sha`, `pipeline` (`id`, `status`, `web_url`), `failed_jobs`, `failed_bridges` (failed trigger jobs), and `blocking_failure_count`. No second call is needed.

Pass `EXIT_REASON` to Phase 4. If `blocking_failure_count` is 0 but the pipeline status is `failed`, nothing blocking is listed to act on. `allow_failure` jobs alone never fail a pipeline, so this usually means a CI configuration error: classify it UNKNOWN and report it rather than treating the pipeline as green.

After classifying a failure that is not flaky, add its ID to `SEEN_EARLY_FAILURE_IDS` before returning to this loop. That includes entries from `failed_bridges`: a trigger job ID that is never marked seen makes every watch return `NEW_FAILURE` at once. This prevents repeated analysis of the same failure while still detecting newly failed jobs. A retried flaky job is superseded by GitLab and is already excluded from `failed_jobs`.
