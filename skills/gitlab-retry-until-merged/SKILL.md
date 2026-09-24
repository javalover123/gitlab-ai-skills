---
name: gitlab-retry-until-merged
description: Shepherd someone else's approved GitLab MR that is set to auto-merge (merge when pipeline succeeds) until it merges, without touching its code. Watches the pipeline, retries failures unrelated to the MR, waits out GitLab.com incidents and broken master before retrying, and alerts you on MR-caused failures or after 3 retries. Never commits, pushes, or rebases. Use when asked to retry until merged, keep an approved MR's pipeline going, or get an auto-merge MR over the line. For your own MR, where fixes may be pushed, use gitlab-babysit-mr instead.
version: 0.1.0
category: Development Workflow
license: MIT
compatibility: opencode
argument-hint: <URL of the approved, auto-merge MR>
metadata:
  audience: developers
  workflow: gitlab
---

# gitlab-retry-until-merged

Get an approved MR that is set to auto-merge merged by re-running its CI, and
nothing else. The MR belongs to someone else: any change to its source branch
cancels auto-merge and voids your approval, so this skill can only **retry
pipelines, wait, and alert you**.

## The hard rule: never change the MR

The **only** CI writes allowed are the two in `scripts/retry.py`: retry an MR
pipeline's failed jobs, or start a new MR pipeline. It re-checks, before every
write, that the MR is open, auto-merge is still set, and the head SHA is
unchanged. The one other write is a plain MR note, and only if the user asks.

Forbidden, even when the fix looks trivial or the user's tooling suggests it:

- `git commit` / `push` / force-push, or editing a checkout of the branch
- rebasing: `glab mr rebase`, the `/rebase` quick action, the Rebase button
- applying suggestions, or mentioning bots that push fixes (Duo Developer)
- editing the MR (title, description, target, labels, draft, reviewers),
  approving/unapproving, re-enabling auto-merge, merging by hand, canceling jobs
- posting MR comments uninvited, or ever with quick actions or bot mentions

If the only way to green needs any of these, **stop and alert the user**.

## When to use

- You approved an MR, set it to auto-merge, and want CI flakes retried until it lands.
- **Not** for your own MR where pushing fixes is fine: use `gitlab-babysit-mr`.

## Main loop

```pseudocode
Phase 0: Resolve MR → preflight (open, auto_merge true) → record EXPECT_SHA
RETRIES_USED = 0, MAX_RETRIES = 3, SEEN = []   # SEEN: triaged failed job IDs

loop:
    Phase 1: event = watch_mr.py --expect-sha EXPECT_SHA --seen SEEN
    MERGED                           → report success, exit
    TIMEOUT                          → not a failure; watch again
    API_ERROR                        → check incidents; watch again (alert after 30 min)
    NEW_FAILURE (pipeline running)   → triage it; MR_RELATED/UNKNOWN → alert, exit
                                       else add to SEEN, keep watching
    PIPELINE_FAILED                  → Phase 2 (no failed jobs listed → UNKNOWN)
    anything else                    → alert, exit   # closed, pushed, auto-merge off…

    Phase 2: classify every blocking failure
    any MR_RELATED or UNKNOWN        → alert, exit (retry nothing)
    RETRIES_USED == MAX_RETRIES      → alert "3 retries without success", exit
    MASTER_BROKEN on a non-merged-results pipeline → alert, exit (only a rebase helps)
    Phase 3: any INCIDENT / MASTER_BROKEN → wait for it to clear (max 2h), else alert, exit
    Phase 4: retry.py …; RETRIES_USED += 1; next watch uses --grace 120
```

## Phases: reference files

| Phase | Summary | Reference |
|-------|---------|-----------|
| **0–1** | Resolve and preflight the MR; watch events and what each means | [references/watching.md](references/watching.md) |
| **2** | Classify failures: TRANSIENT, INCIDENT, MASTER_BROKEN, MR_RELATED, UNKNOWN | [references/failure-triage.md](references/failure-triage.md) |
| **3** | Check GitLab.com incident signals and wait them out | [references/incident-waiting.md](references/incident-waiting.md) |
| **4** | Pick the retry (same pipeline vs new pipeline), spend the budget | [references/retrying.md](references/retrying.md) |
| **5** | Alert the user: what failed, why, what they can do | [references/alerting.md](references/alerting.md) |

## Scripts

Run with `python3` from the skill directory (stdlib only). Each prints JSON; only `retry.py` writes.

- `scripts/mr_state.py [--files] <mr-url>`: MR + latest pipeline + blocking failures
- `scripts/watch_mr.py --expect-sha <sha> [--seen IDS] [--grace N] [--mr-only] <mr-url>`: block until an event
- `scripts/job_log_tail.py <project-encoded> <job-id> [lines]`: cleaned log tail
- `scripts/incident_status.py [--hours N]`: status page, production and master-broken incidents
- `scripts/retry.py --expect-sha <sha> <mr-url> pipeline <id> | new-pipeline`

## Rules

- **Never change the MR.** See the hard rule above; no exceptions.
- **When unsure whether the MR caused it, it did.** UNKNOWN alerts, it doesn't retry.
- **Max 3 retries total** (default). A retry is one `retry.py` call that
  exited 0. Waiting is free. The user may change this and the incident-wait
  limits when invoking; nobody can relax the hard rule.
- **Merge train pipelines can't be retried.** A train failure drops the MR; alert.
- **Alert locally by default:** a final chat report, plus a desktop/push
  notification if your environment has one. Don't notify the MR author uninvited.
- **Never give up on a running pipeline.** `TIMEOUT` means "watch again".
  A green pipeline that doesn't merge is different: see [watching.md](references/watching.md).
