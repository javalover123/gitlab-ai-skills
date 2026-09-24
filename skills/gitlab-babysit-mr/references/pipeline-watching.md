# Phase 1: Watch for Blocking Failures or Pipeline Completion

Use `pipeline_status.sh --blocking-only` as the babysitter's 60-second poll. Exit as soon as a blocking job fails, even if other jobs are still running, so retryable failures do not wait for pipeline completion. The script fetches only failed jobs and excludes `allow_failure: true` and superseded retried jobs from `blocking_failure_count`.

Do not substitute `pipeline-watch.py` for this poll: it waits for terminal MR pipeline transitions, not individual job failures. This poll already detects terminal states as well as early blocking failures.

```pseudocode
POLL_INTERVAL=60
EXIT_REASON=null
SEEN_EARLY_FAILURE_IDS=set()
PREV_PIPELINE_ID=null  # set to the previous pipeline ID immediately after pushing a fix

loop:
    result=$(bash scripts/pipeline_status.sh --blocking-only "$MR_URL")
    if PREV_PIPELINE_ID:
        if not result.pipeline_id or result.pipeline_id == PREV_PIPELINE_ID:
            sleep POLL_INTERVAL
            continue
        PREV_PIPELINE_ID=null

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

After pushing a fix, set `PREV_PIPELINE_ID` to the old run's ID before returning to the loop. Wait for a different ID before analyzing the new run, even if the old run was terminal. A job retry stays in the same pipeline and does not need this guard.

When the loop exits, fetch the complete job data for analysis and reporting:

```bash
bash scripts/pipeline_status.sh "$MR_URL"
```

Pass `EXIT_REASON` to Phase 4. If `blocking_failure_count` is 0 but the pipeline status is `failed`, all failures are non-blocking. Treat the pipeline as green.

After classifying a failure that is not flaky, add its job ID to `SEEN_EARLY_FAILURE_IDS` before returning to this loop. This prevents repeated analysis of the same failure while still detecting newly failed jobs. A retried flaky job is superseded by GitLab and is already excluded by `--blocking-only`.
