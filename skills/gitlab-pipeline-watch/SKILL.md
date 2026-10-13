---
name: gitlab-pipeline-watch
description: Watch GitLab MR pipelines and return when their state changes. Watches one MR at the job level (returns as soon as a blocking job fails, a push lands, auto-merge is canceled, or the MR merges) or many MRs for finished pipelines, merges, and new MRs. Also snapshots an MR's merge and pipeline state and tails CI job logs. Use when asked to watch, wait on, or poll an MR or its pipeline; also the shared watcher that gitlab-babysit-mr and gitlab-retry-until-merged load. Read-only; to act on failures use gitlab-babysit-mr (MRs you may push to) or gitlab-retry-until-merged (MRs you must not change).
version: 1.1.0
category: Development Workflow
license: MIT
metadata:
  audience: developers
  workflow: gitlab-ci
---

# gitlab-pipeline-watch

Block until a GitLab MR needs attention, then return so you can react: the
**watch, react, repeat** loop. Read-only: nothing here retries, pushes, or
comments. Acting on an event is the caller's job.

## When to use

- Wait for CI on an MR and react to the result.
- Another skill needs to watch an MR: `gitlab-babysit-mr` and
  `gitlab-retry-until-merged` depend on this skill's scripts.
- **Not** for fixing or retrying failures: use `gitlab-babysit-mr` (your own MR)
  or `gitlab-retry-until-merged` (someone else's approved auto-merge MR).

## Prerequisites

- `glab` CLI installed and authenticated (`glab auth status`) to the MR's GitLab instance. Scripts that take an MR URL query that URL's host; the others use glab's default (the current checkout's host, or gitlab.com) unless given `--hostname`.
- Python 3.7+ (standard library only)

## Pick a watcher

| Need | Script | Reference |
|------|--------|-----------|
| One MR, job level: react to the first blocking job failure, a push, auto-merge cancellation, or a merge | `scripts/watch_mr.py` | [references/watch-mr.md](references/watch-mr.md) |
| Many MRs in a project: react to finished pipelines, merges, conflicts, new MRs | `scripts/pipeline-watch.py` | [references/pipeline-watch.md](references/pipeline-watch.md) |

`pipeline-watch.py` waits for *terminal* pipeline transitions only, so it
cannot see a failed job while the rest of the pipeline runs. Use `watch_mr.py`
whenever early failures matter.

## Scripts

Run with `python3` from this skill's directory. Each prints JSON except
`pipeline-watch.py`, which prints event lines and a summary.

- `scripts/watch_mr.py [--expect-sha SHA] [--auto-merge] [--newer-than ID] [--seen IDS] [--grace N] [--mr-only] <mr-url>`
- `scripts/mr_state.py [--files] <mr-url>`: one snapshot (MR, latest pipeline, blocking failures)
- `scripts/job_log_tail.py [--hostname HOST] <project_encoded> <job_id> [lines]`: cleaned log tail
- `scripts/pipeline-watch.py <project> [mr ...] [--no-all] [--wait-for-push] [--hostname HOST] …`
- `scripts/glab_helpers.py`: the shared `glab api` wrapper the others import (not run directly)

## Quick start

```bash
# One MR you're pushing to: return on the first blocking failure or when green
python3 scripts/watch_mr.py https://gitlab.com/gitlab-org/gitlab/-/merge_requests/123

# Someone else's auto-merge MR: also stop on a push or a canceled auto-merge
python3 scripts/watch_mr.py --expect-sha "$SHA" --auto-merge <mr-url>

# Every open MR in a project
python3 scripts/pipeline-watch.py gitlab-org/gitlab
```

## Gotchas

- **`TIMEOUT` is not a failure.** Both watchers return before a 10-minute tool
  limit; run them again.
- **After a push, pass `--newer-than <old pipeline.id>`**, recorded *before*
  pushing; otherwise the old pipeline's result looks like the new one's.
- **After a retry, pass `--grace 120`**; the retried pipeline can briefly still
  read as failed.
- **Compare the MR's `sha`, not `pipeline.sha`**: merged-results pipelines run
  on a temporary merge commit.
- **Blocking failures only.** `failed_jobs` drops `allow_failure` jobs and
  superseded retries. A `PIPELINE_FAILED` with no failed jobs usually means a CI
  config error.
- **Don't over-poll**: 60s (`watch_mr.py`) and 20s (`pipeline-watch.py`) defaults;
  below 10s risks API rate limits.
