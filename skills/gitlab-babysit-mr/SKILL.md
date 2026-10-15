---
name: gitlab-babysit-mr
description: Monitor a GitLab MR's pipeline until green. Classifies failures (flaky, master-broken, lint, coverage, real), retries jobs where appropriate, pushes light-touch auto-fix commits to the MR branch, and posts findings as an MR comment. Use when asked to babysit an MR, fix its CI, or get it green, and pushing to its branch is fine. If the MR must not be changed (someone else's, or one you approved for auto-merge), use gitlab-retry-until-merged; to only watch, use gitlab-pipeline-watch.
version: 0.13.0
category: Development Workflow
license: MIT
compatibility: opencode
argument-hint: <URL of the MR to babysit>
metadata:
  audience: developers
  workflow: gitlab
---

# gitlab-babysit-mr

Nurse a GitLab MR's pipeline to green by classifying failures, retrying flaky/broken jobs, making light-touch auto-fixes, and posting structured reports inside a resolved discussion thread on the MR.

## Dependencies

- **`gitlab-pipeline-watch` skill** — the shared MR watcher (`watch_mr.py`), snapshot (`mr_state.py`), and job log tail (`job_log_tail.py`). Load it first. `$WATCH` in the references is the directory holding its `SKILL.md`; set it in every shell command (variables don't persist). If the skill won't load or `$WATCH/scripts/watch_mr.py` is missing, stop and ask the user to install it.
- **Bundled script** — `scripts/search_known_issues.sh`

## Main Loop (max 5 action rounds)

The loop caps **action rounds** (classify + retry/fix), NOT status checks. The babysitter waits as long as the pipeline needs — it only counts a round when it takes action on failures.

```pseudocode
Phase 0: Resolve MR URL → PROJECT_PATH, MR_IID, PROJECT_ENCODED

ACTION_ROUND = 0, MAX_ROUNDS = 5
JOB_RETRY_COUNT = {}      # keyed by job name, persisted across rounds
DUO_LINT_REQUESTED = {}   # keyed by job name, tracks Duo Developer requests
SEEN_EARLY_FAILURE_IDS = set()  # failures already classified while the pipeline runs
DISCUSSION_ID = null      # set after first report, reused for thread replies

while ACTION_ROUND < MAX_ROUNDS:
    Phase 1: Poll until a blocking job fails or the pipeline reaches a terminal state
    Phase 2: Analyze each failed job (fetch log tail, classify)
    Phase 3: Search for known issues (FLAKY and MASTER_BROKEN only)
    Phase 4: Take action per classification
    Phase 5: Post report in resolved discussion thread
    Phase 6: Diagnose blocking failures before final report
    Phase 7: Loop back after an early classification or action; otherwise post final report and exit
```

## Phases — Reference Files

Each phase has detailed instructions in a reference file. Load on demand.

| Phase | Summary | Reference |
|-------|---------|-----------|
| **0** | Resolve MR from argument or current branch | [references/mr-resolution.md](references/mr-resolution.md) |
| **1** | Watch with `$WATCH/scripts/watch_mr.py` for blocking job failures or a terminal pipeline | [references/pipeline-watching.md](references/pipeline-watching.md) |
| **2–3** | Fetch job logs, classify failures, search known issues | [references/job-analysis.md](references/job-analysis.md) |
| **4** | Retry flaky jobs, retry pipelines, delegate lint to Duo Developer | [references/failure-actions.md](references/failure-actions.md) |
| **5** | Post report in a resolved discussion thread (collapsed by default) | [references/mr-reporting.md](references/mr-reporting.md) |
| **6** | Root-cause diagnosis for blocking failures | [references/failure-diagnosis.md](references/failure-diagnosis.md) |
| **7** | Keep watching after early classifications/actions, or exit when terminal with no action | — |

**Classification guide:** [references/failure-classification.md](references/failure-classification.md) — FLAKY, MASTER_BROKEN, LINT, COVERAGE, REAL_FAILURE, UNKNOWN.

**Lint fix delegation:** [references/lint-fix-delegation.md](references/lint-fix-delegation.md) — Duo Developer comment → wait → local fallback.

## Safety Rules

- **Max 2 retries per job** — track by name; 3rd failure → pipeline retry
- **Never retry REAL_FAILURE** — needs code fixes, not retries
- **Max 5 action rounds** — caps retries/fixes, NOT waiting time
- **Never give up on a running pipeline** — keep polling until it needs action or reaches a terminal state
- **Only blocking failures trigger action** — ignore `allow_failure: true` and superseded retried jobs
- **Only retry flaky jobs early** — use early detection for transient failures; handle other classes after pipeline completion
- **No force-push or amend** — always new commits for fixes
