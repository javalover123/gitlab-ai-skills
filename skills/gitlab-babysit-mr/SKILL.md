---
name: gitlab-babysit-mr
description: Monitor a GitLab MR's pipeline until green. Classifies failures (flaky, master-broken, lint, coverage, real), retries jobs where appropriate, makes light-touch auto-fixes, and posts findings as an MR comment.
version: 0.10.0
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

- **Bundled scripts** — `scripts/` directory next to this file (pipeline_status.sh, job_log_tail.sh, search_known_issues.sh)
- **gitlab-pipeline-watch skill** — provides `pipeline-watch.py` for blocking pipeline polling

## Phase 0: Resolve the MR

Use the argument if provided. Otherwise detect from the current branch:

```bash
MR_URL="${ARGUMENT:-}"
if [[ -z "$MR_URL" ]]; then
  MR_URL=$(glab mr view --output json 2>/dev/null | jq -r '.web_url // empty')
fi

if [[ -z "$MR_URL" ]]; then
  echo "Error: no MR URL provided and none detected for current branch." >&2
  exit 1
fi
```

Parse the URL to extract project and MR IID:

```bash
# https://gitlab.com/group/[subgroup/]project/-/merge_requests/123
path="${MR_URL#https://gitlab.com/}"
PROJECT_PATH="${path%%/-/*}"
MR_IID="${MR_URL##*/}"
PROJECT_ENCODED="${PROJECT_PATH//\//%2F}"
```

---

## Main Loop (max 5 ACTION rounds)

The loop caps **action rounds** (classify + retry/fix), NOT status checks. The babysitter waits as long as the pipeline needs — it only counts a round when it takes action on failures.

```pseudocode
ACTION_ROUND=0
MAX_ROUNDS=5
JOB_RETRY_COUNT={}        # keyed by job name, persisted across rounds
DUO_LINT_REQUESTED={}     # keyed by job name, tracks Duo Developer lint fix requests
DISCUSSION_ID=null        # set after first discussion creation, used for thread replies

while ACTION_ROUND < MAX_ROUNDS:
    1. Wait for pipeline to reach terminal state (Phase 1)
    2. If success → post report (as reply in discussion thread), exit
    3. If failed → analyze, classify, act, report (Phases 2-5)
    4. If action taken → ACTION_ROUND++, go to 1
    5. If no action possible → diagnose blocking failures (Phase 6), post final report (Phase 5), exit
```

---

## Phase 1: Wait for Pipeline to Finish

Use `pipeline-watch.py` (from the `gitlab-pipeline-watch` skill) in a polling loop. Each invocation blocks for up to 15 minutes (staying within tool-call timeout limits), then re-invoke if the pipeline is still running. **Never give up on a running pipeline.**

Locate pipeline-watch.py from the installed `gitlab-pipeline-watch` skill's `scripts/` directory.

```pseudocode
WAIT_FOR_PUSH=false   # set to true after pushing a fix or retrying

loop:
    if WAIT_FOR_PUSH:
        output=$(python3 pipeline-watch.py "$PROJECT_PATH" \
          --no-all --no-watch-new "$MR_IID" \
          --wait-for-push --timeout 900)
    else:
        output=$(python3 pipeline-watch.py "$PROJECT_PATH" \
          --no-all --no-watch-new "$MR_IID" \
          --timeout 900)

    if output contains "SUCCESS" → pipeline green, proceed to report
    if output contains "FAILED"  → proceed to Phase 2
    if output contains "CANCELED" → post comment, exit
    if timeout (no event)        → loop again
```

**CRITICAL**: Use `timeout=960000` (16 min) on the Bash tool call so it outlasts the 900s script timeout. The script exits cleanly on timeout — it's not an error, just means the pipeline is still running.

After the watcher reports a terminal state, get the structured JSON:

```bash
bash scripts/pipeline_status.sh "$MR_URL"
```

Check `blocking_failure_count`: if 0 but status is `failed`, all failures are `allow_failure: true` (non-blocking). Treat as green.

---

## Phase 2: Analyze Each Failed Job

For each entry in `failed_jobs` where `allow_failure != true`:

```bash
bash scripts/job_log_tail.sh "<project_encoded>" "<job_id>" 150
```

If the log tail is insufficient to classify, gather more context:
- Run `git diff origin/main --name-only` to see which files the MR changed — compare against files mentioned in the error
- Check if the same job name failed in other recent pipelines (indicates FLAKY or MASTER_BROKEN, not REAL_FAILURE)
- Read the job's `failure_reason` field from the pipeline_status output (e.g. `script_failure` vs `stuck_or_timeout_failure`)

**Classify** the failure using the guide below. Record the classification for each job.

**Skip** jobs where `allow_failure: true` — they do not block the pipeline.

---

## Failure Classification Guide

**Classify** each failure using the detailed guide: **[references/failure-classification.md](references/failure-classification.md)**

Categories: FLAKY, MASTER_BROKEN, LINT, COVERAGE, REAL_FAILURE, UNKNOWN.

---

## Phase 3: Search for Known Issues

For **FLAKY** and **MASTER_BROKEN** failures, search for known issues:

```bash
# Use the most distinctive part of the error — test name, class name, or error message
bash scripts/search_known_issues.sh "<failure-keyword>" "<project>"
```

Good search terms (in order of specificity):
1. Exact test name: `FooSpec#bar_method`
2. Error class + method: `NoMethodError undefined method foo`
3. Job name if it's a known flaky job: `rspec-ee-unit`

---

## Phase 4: Take Action

### FLAKY → Retry job (up to 2 retries per job; on 3rd failure, retry pipeline)

Track retry counts per job across action rounds using a `JOB_RETRY_COUNT` map (keyed by job name, since job IDs change on retry).

```pseudocode
JOB_RETRY_COUNT = {}   # persisted across action rounds, keyed by job name

for each FLAKY job:
    count = JOB_RETRY_COUNT.get(job_name, 0)
    if count < 2:
        # Retry the individual job
        glab api --method POST "projects/<project_encoded>/jobs/<job_id>/retry"
        JOB_RETRY_COUNT[job_name] = count + 1
        note: "Retried job (attempt #{count + 1} of 2)" + (known_issue_url or "no known issue found")
    else:
        # 3rd failure — escalate to full pipeline retry
        glab api --method POST "projects/<project_encoded>/pipelines/<pipeline_id>/retry"
        note: "Job failed 3 times — retried entire pipeline"
        break   # pipeline retry supersedes remaining individual retries
```

Search for known issues regardless of retry count (for reporting):
```bash
bash scripts/search_known_issues.sh "<failure-keyword>" "<project>"
```

### MASTER_BROKEN + known issue found → Retry pipeline (not just the job)
```bash
glab api --method POST "projects/<project_encoded>/pipelines/<pipeline_id>/retry"
```

### MASTER_BROKEN + no known issue → Check if the error is really master broken by inspecting code history. If confirmed, retry pipeline.

### LINT → Delegate fix to Duo Developer via MR comment

Follow the full lint fix delegation workflow: **[references/lint-fix-delegation.md](references/lint-fix-delegation.md)**

Summary: Post a `@duo-developer-gitlab-org` MR comment with specific violations, wait for Duo to push a fix, fall back to local auto-fix if incomplete. Track requests in `DUO_LINT_REQUESTED` to avoid retry loops.

### COVERAGE → Search for known coverage issues first
```bash
bash scripts/search_known_issues.sh "coverage" "<project>"
```
If found, retry. Otherwise classify as REQUIRES_MANUAL_FIX.

### REAL_FAILURE → No action. Document clearly in the report.

### UNKNOWN → Retry up to 2 times (same as FLAKY). If it fails a 3rd time, escalate to REQUIRES_MANUAL_FIX and diagnose in Phase 6.

---

## Phase 5: Post MR Comment (resolved discussion thread)

Post all reports inside a **single resolved discussion** so they stay collapsed and out of the way. See **[references/mr-reporting.md](references/mr-reporting.md)** for the full API workflow, report template, and re-resolve pattern.

Store `DISCUSSION_ID` across action rounds so all updates form a single thread.

---

## Phase 6: Diagnose Blocking Failures

**Before posting the final blocked report**, attempt root-cause diagnosis for any blocking failure. See **[references/failure-diagnosis.md](references/failure-diagnosis.md)** for per-classification diagnosis steps.

Include the diagnosis in the final report under each job's entry as a **Root cause** field.

---

## Phase 7: Wait and Loop

If any jobs were retried or a fix was pushed:
```bash
WAIT_FOR_PUSH=true   # so Phase 1 uses --wait-for-push to ignore stale pipeline
# → Loop back to Phase 1
```

If no actions could be taken (all failures are REAL_FAILURE or REQUIRES_MANUAL_FIX):
```bash
# Post final blocked report (as reply in discussion thread) with diagnosis and exit
```

---

## Retry Safety Rules

- **Max 2 retries per job** — track by job name across rounds; on 3rd failure, escalate to pipeline retry
- **Never retry REAL_FAILURE jobs** — they need code fixes, not retries
- **Max 5 action rounds** — caps retries/fixes, NOT waiting time
- **Never give up on a running pipeline** — keep re-invoking pipeline-watch.py in 15-min windows until terminal
- **Do not retry `allow_failure: true` jobs** — they are non-blocking by design
- **Do not force-push or amend commits** — always new commits for lint fixes


