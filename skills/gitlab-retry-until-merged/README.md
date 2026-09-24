# gitlab-retry-until-merged

Shepherd someone else's approved, set-to-auto-merge MR until it merges by retrying its CI, **without ever changing its code**. Retries failures unrelated to the MR, waits out GitLab.com incidents and broken master, and alerts you on MR-caused failures or after 3 retries.

Use [`gitlab-babysit-mr`](../gitlab-babysit-mr/README.md) instead for your own MR, where pushing fixes is fine.

## Dependencies

- [`glab`](https://gitlab.com/gitlab-org/cli) CLI, authenticated
- Python 3.7+ (standard library only)

## Why "no code changes" is absolute

When new commits land on the source branch, GitLab cancels auto-merge and the new commits need a fresh review, so your approval no longer covers what would merge. The skill's only write path is `scripts/retry.py`, which can retry an MR pipeline or start a new MR pipeline, and nothing else. It re-reads the MR before every write and refuses if the MR closed, auto-merge was canceled, or the head SHA moved.

## Opinionated defaults

| Decision | What the skill does | Why you might change it |
|---|---|---|
| **Max 3 retries** | Counts every pipeline retry or new pipeline; after the 3rd fails, stops and alerts | More for a notoriously flaky suite, fewer to save CI minutes |
| **Retry at pipeline end** | Waits for the pipeline to finish, then retries all failed jobs in one go with no further delay. Early failures are only triaged, so an MR-caused failure alerts you before the pipeline finishes | You might prefer retrying transient jobs as soon as they fail (costs retries faster) |
| **Unsure means MR-caused** | An unclassifiable failure alerts rather than retries | You might accept one blind retry before alerting |
| **Incident wait: 15 min minimum, 2 h maximum** | Waits for the matched incident to clear, then retries; still active after 2 h → alerts without retrying | Longer for a big outage, shorter if you'd rather decide yourself |
| **Broken master → new pipeline** | After the master-broken fix lands, starts a new merged-results pipeline instead of retrying the stale one | — (retrying the old pipeline reuses the broken merge commit) |
| **Merge train drop → alert** | Doesn't re-add the MR to the train. Re-adding re-enables auto-merge, which the skill never does | — (re-add it yourself from the alert) |
| **Alerts stay local** | Reports in chat and sends a notification if available; comments on the MR only if you ask | You might want a plain note left for the author |
| **Green but not merging: 30 min** | If the pipeline passes and the MR still hasn't merged 30 minutes later, alerts with the blocking merge status | Longer if your merge trains are slow |

## Customizing with agent prompts

Override defaults when invoking:

```
/gitlab-retry-until-merged https://gitlab.com/gitlab-org/gitlab/-/merge_requests/123456
- Allow 5 retries
- Wait up to 4 hours for incidents
- Leave a plain note on the MR when you stop
```

Requests the skill will refuse however they're phrased: pushing, rebasing, applying suggestions, editing the MR, or asking a bot to push a fix.

## Tests

`bash tests/test_scripts.sh` (or `python3 tests/test_scripts.py`) runs offline against a stubbed `glab` and a local status-page fixture, and checks among other things that `retry.py` writes nothing when a precondition fails.
