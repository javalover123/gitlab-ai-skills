# Phase 1: Watch for Blocking Failures or Pipeline Completion

Poll the latest pipeline every 30 seconds. Exit the polling loop as soon as a blocking job fails, even if other jobs are still running, so retryable failures do not wait for the entire pipeline to finish.

`pipeline_status.sh --blocking-only` uses GitLab's `scope[]=failed` filter instead of fetching every job. It excludes `allow_failure: true` and superseded retried jobs from `blocking_failure_count`.

```pseudocode
POLL_INTERVAL=30
EXIT_REASON=null
SEEN_EARLY_FAILURE_IDS=set()

loop:
    result=$(bash scripts/pipeline_status.sh --blocking-only "$MR_URL")
    new_failures=result.failed_jobs excluding IDs in SEEN_EARLY_FAILURE_IDS

    if new_failures is not empty:
        EXIT_REASON=EARLY_FAILURE
        break

    if result.pipeline_status in [success, failed, canceled, skipped, manual]:
        EXIT_REASON=TERMINAL
        break

    sleep POLL_INTERVAL
```

Keep polling while the pipeline is running. A polling-tool timeout is not a pipeline failure; start another polling window.

After pushing a fix, use `pipeline-watch.py --wait-for-push` to wait for a new pipeline ID before returning to the loop above. A job retry stays in the same pipeline and does not need this step.

When the loop exits, fetch the complete job data for analysis and reporting:

```bash
bash scripts/pipeline_status.sh "$MR_URL"
```

Pass `EXIT_REASON` to Phase 4. If `blocking_failure_count` is 0 but the pipeline status is `failed`, all failures are non-blocking. Treat the pipeline as green.

After classifying a failure that is not flaky, add its job ID to `SEEN_EARLY_FAILURE_IDS` before returning to this loop. This prevents repeated analysis of the same failure while still detecting newly failed jobs. A retried flaky job is superseded by GitLab and is already excluded by `--blocking-only`.
