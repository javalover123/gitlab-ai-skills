# Phase 1: Watch for Blocking Failures or Pipeline Completion

Use `pipeline_status.sh --blocking-only` as the babysitter's 60-second poll. Exit as soon as a blocking job fails, even if other jobs are still running, so retryable failures do not wait for pipeline completion. The script fetches only failed jobs and excludes `allow_failure: true` and superseded retried jobs from `blocking_failure_count`.

Do not substitute `pipeline-watch.py` for this poll: it waits for terminal MR pipeline transitions, not individual job failures. This poll already detects terminal states as well as early blocking failures.

```pseudocode
POLL_INTERVAL=60
EXIT_REASON=null
SEEN_EARLY_FAILURE_IDS=set()
PREV_PIPELINE_ID=null       # record the old pipeline ID before pushing
NEW_PIPELINE_DEADLINE=null  # set to now + 15 minutes at the same time

loop:
    result=$(bash scripts/pipeline_status.sh --blocking-only "$MR_URL")
    if PREV_PIPELINE_ID:
        if not result.pipeline_id or result.pipeline_id == PREV_PIPELINE_ID:
            if now >= NEW_PIPELINE_DEADLINE:
                EXIT_REASON=NO_NEW_PIPELINE
                break
            sleep POLL_INTERVAL
            continue
        PREV_PIPELINE_ID=null
        NEW_PIPELINE_DEADLINE=null

    new_failures=result.failed_jobs excluding IDs in SEEN_EARLY_FAILURE_IDS

    if new_failures is not empty:
        EXIT_REASON=EARLY_FAILURE
        break

    if result.pipeline_status in [success, failed, canceled, skipped, manual]:
        EXIT_REASON=TERMINAL
        break

    sleep POLL_INTERVAL
```

Keep polling while the pipeline is running. If a polling window times out, check the latest pipeline again and continue polling; a timeout is not a pipeline failure and does not consume an action round.

Before pushing, record the current `pipeline_id` as `PREV_PIPELINE_ID` so a fast new pipeline is not mistaken for the old one. After the push, set `NEW_PIPELINE_DEADLINE` to now + 15 minutes and return to the loop. Wait for a different ID before analyzing the new run, even if the old run was terminal. A job or pipeline retry stays in the same pipeline and does not need this guard.

On `NO_NEW_PIPELINE`, do not analyze or report the old run as the new one. If awaiting Duo Developer's fix, use the [local auto-fix fallback](lint-fix-delegation.md#step-5-fallback-local-auto-fix); otherwise report that the push produced no new pipeline and investigate. This deadline applies only to waiting for a *new* pipeline, not to a pipeline already running.

On `EARLY_FAILURE` or `TERMINAL`, fetch the complete job data for analysis and reporting:

```bash
bash scripts/pipeline_status.sh "$MR_URL"
```

Pass `EXIT_REASON` to Phase 4. If `blocking_failure_count` is 0 but the pipeline status is `failed`, all failures are non-blocking. Treat the pipeline as green.

After classifying a failure that is not flaky, add its job ID to `SEEN_EARLY_FAILURE_IDS` before returning to this loop. This prevents repeated analysis of the same failure while still detecting newly failed jobs. A retried flaky job is superseded by GitLab and is already excluded by `--blocking-only`.
