# Phase 4: Retrying

Every retry goes through `scripts/retry.py`. It is the skill's only write, and
it refuses (exit 3, nothing written) if the MR is no longer open, auto-merge was
canceled, the head SHA moved, or the pipeline isn't one of this MR's pipelines
or is a merge train pipeline. On exit 3, don't work around it: alert with the
`reason` it printed.

Any other non-zero exit (usually 1) means the API call failed, and the write
may or may not have happened. Run `mr_state.py`:
- If the pipeline is running again, or a new pipeline appeared, the retry went
  through. Count it.
- Otherwise it didn't. Don't count it; treat it like `API_ERROR` (check
  incidents, wait), then call `retry.py` again.

## Which retry

| Situation | Command | Why |
|-----------|---------|-----|
| TRANSIENT, or INCIDENT after it cleared | `retry.py --expect-sha "$EXPECT_SHA" "$MR_URL" pipeline <pipeline_id>` | Re-runs only the failed jobs of the same pipeline. Auto-merge stays set, and the MR merges when it goes green. |
| MASTER_BROKEN after the fix landed, pipeline `kind` is `merged_result` | `retry.py --expect-sha "$EXPECT_SHA" "$MR_URL" new-pipeline` | Retried jobs reuse the old merge commit, which still contains the broken target branch. A new MR pipeline merges the fixed target branch. The source branch is untouched. |
| MASTER_BROKEN, pipeline `kind` is `detached` or `branch` | none. Alert. | The pipeline tests the source branch alone, so only a rebase (a push) would pick up the fix. |
| Pipeline `kind` is `merge_train` | none. Alert. | GitLab removes an MR from the train when its train pipeline fails, and that pipeline can't be retried. Re-adding the MR to the train is the user's decision. |
| The same **infrastructure** failure (not a test failure) recurs in a job after a `pipeline` retry | `new-pipeline` | A fresh pipeline sometimes clears state a job retry doesn't (caches, stale merge ref). Still costs one retry. A repeating *test* failure is MR_RELATED; see [failure-triage.md](failure-triage.md). |

`pipeline` retries every failed and canceled job in the pipeline, so one call
covers all of its failures. GitLab doesn't document whether this also re-runs
failed trigger jobs (bridges). If a bridge is still failed once the retried
pipeline settles, report it in the alert. Don't retry the downstream pipeline
directly: `retry.py` only accepts the MR's own pipelines.

## Budget

- `RETRIES_USED` counts `retry.py` calls that went through (exit 0, or
  confirmed as above), whatever the mode. Exit 3 refusals don't count; they end
  the run.
- The default is 3. The user may set another number when invoking.
- Check **before** retrying: when `RETRIES_USED == MAX_RETRIES` and the pipeline failed
  again, alert "retried <max> times without success" and stop.
- Waiting (Phase 3) and watching never count.

## After retrying

- `pipeline` mode: watch again with `--grace 120`.
- `new-pipeline` mode: the new pipeline becomes the MR's latest; watch again
  normally. Its job IDs are all new, so `SEEN` needs no reset.
- Keep `EXPECT_SHA` unchanged: a retry never moves the MR head.
