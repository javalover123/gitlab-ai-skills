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

Read the last 150 lines of the log and classify into one of:

### FLAKY
Random or infrastructure-related failures unrelated to the MR code:
- Connection timeouts, DNS failures, port conflicts (`Errno::EADDRINUSE`, `Net::ReadTimeout`, `SocketError`)
- "Could not connect", "connection refused", "connection reset"
- Test passes in other shards/jobs of the same type
- Intermittent Docker/runner issues
- `random seed` combined with failures that seem random
- "flaky" mentioned in the output

### MASTER_BROKEN
Shared code or infrastructure is broken for everyone, not specific to this MR:
- Error in code the MR did not touch (check `git diff origin/main --name-only`)
- Same root error in multiple unrelated jobs
- Database migration errors, gem version conflicts
- CI infrastructure errors (runner out of disk, registry unavailable)
- Missing fixtures or seed data that existed before

### LINT
Style/formatting violation:
- Job name contains: `rubocop`, `eslint`, `haml-lint`, `stylelint`, `prettier`
- RuboCop cop names: `Style/`, `Layout/`, `Metrics/`, `Lint/`
- ESLint format: `error  <rule>  <file>:<line>`
- "offenses detected", "x problems (y errors, z warnings)"

### COVERAGE
Code coverage below threshold:
- Job name contains: `coverage`, `code_coverage`
- Output: "Coverage (%) must be at least X%", `C0 coverage`

### REAL_FAILURE
Actual bug in MR code:
- Test failure in code the MR modified (correlate with `git diff origin/main --name-only`)
- Logic error, missing method, wrong behavior
- Expected/actual diff matches the MR's changes

### UNKNOWN
Cannot determine cause from log tail alone.

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

Instead of running lint fixes locally, delegate to Duo Developer by posting an MR comment. This triggers a remote AI workflow that pushes a fix commit.

**Step 1: Analyze the lint errors to build a clear instruction.**

From the job log tail, extract:
- Which files have violations (correlate with `git diff origin/main --name-only`)
- Which linter reported them (RuboCop cop names, ESLint rules, etc.)
- The specific violations (e.g. "Style/StringLiterals in app/models/foo.rb:42")

**Step 2: Post an MR comment mentioning Duo Developer.**

Compose a targeted instruction and post it as a **new top-level MR note** (not inside the babysitter discussion thread):

```bash
# Build the instruction from the lint errors found in Phase 2
DUO_INSTRUCTION="Fix the following lint violations in this MR:\n\n"
# Append each violation, e.g.:
# - RuboCop Style/StringLiterals in app/models/foo.rb:42 — use double quotes
# - ESLint no-unused-vars in app/assets/javascripts/bar.js:10
# Keep it specific: file paths, line numbers, rule names, and what to change.

glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/notes" \
  --method POST \
  --raw-field "body=@duo-developer-gitlab-org ${DUO_INSTRUCTION}"
```

**Guidelines for the instruction:**
- Be specific: include file paths, line numbers, and rule names
- Group by linter (RuboCop, ESLint, HAML-lint, Prettier, Stylelint)
- For RuboCop: include the cop name (e.g. `Style/StringLiterals`)
- For ESLint/Prettier: include the rule name and whether `--fix` can resolve it
- Limit to violations in files the MR actually changed (from `git diff origin/main --name-only`)
- If there are too many violations (>20), focus on the blocking ones and ask Duo to run the auto-formatter

Example instruction:
```
Fix these RuboCop offenses in this MR:
- Style/StringLiterals in app/models/user.rb:42,58 — use double quotes
- Layout/TrailingWhitespace in app/controllers/foo_controller.rb:15,23

Run `bundle exec rubocop --autocorrect` on the affected files.
```

**Step 3: Wait for Duo Developer to push a fix commit.**

After posting the comment, set `WAIT_FOR_PUSH=true` and loop back to Phase 1. The pipeline watcher will use `--wait-for-push` to detect Duo Developer's new commit and the resulting pipeline.

**Step 4: If Duo Developer's fix doesn't resolve all lint issues** (detected in a subsequent action round), classify remaining violations as REQUIRES_MANUAL_FIX. Do NOT post a second Duo Developer request for the same lint job — avoid a retry loop.

Track Duo Developer requests using a `DUO_LINT_REQUESTED` set (keyed by job name). Only request once per job:

```pseudocode
DUO_LINT_REQUESTED = {}   # persisted across action rounds, keyed by job name

for each LINT job:
    if job_name not in DUO_LINT_REQUESTED:
        # Post @duo-developer-gitlab-org comment with fix instructions
        DUO_LINT_REQUESTED[job_name] = true
        note: "Requested Duo Developer fix for lint violations"
    else:
        # Already requested once — Duo's fix didn't fully resolve it
        classify as REQUIRES_MANUAL_FIX
        note: "Duo Developer fix incomplete — requires manual attention"
```

If Duo Developer does not push a commit within 10 minutes (detected when pipeline-watch times out with no new pipeline), classify as REQUIRES_MANUAL_FIX.

### COVERAGE → Search for known coverage issues first
```bash
bash scripts/search_known_issues.sh "coverage" "<project>"
```
If found, retry. Otherwise classify as REQUIRES_MANUAL_FIX.

### REAL_FAILURE → No action. Document clearly in the report.

### UNKNOWN → Retry up to 2 times (same as FLAKY). If it fails a 3rd time, escalate to REQUIRES_MANUAL_FIX and diagnose in Phase 6.

---

## Phase 5: Post MR Comment (resolved discussion thread)

Post all reports inside a **single resolved discussion** so they stay collapsed and out of the way.

### First report: Create resolved discussion, then reply with report

**Step 1**: Create a small discussion and immediately resolve it.

```bash
# Create the discussion with a short placeholder body
DISCUSSION_RESPONSE=$(glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/discussions" \
  --method POST \
  --raw-field "body=Thread generated by \`/gitlab-babysit-mr\`")

DISCUSSION_ID=$(echo "$DISCUSSION_RESPONSE" | jq -r '.id')
FIRST_NOTE_ID=$(echo "$DISCUSSION_RESPONSE" | jq -r '.notes[0].id')

# Immediately resolve the discussion so it's collapsed
glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/discussions/${DISCUSSION_ID}" \
  --method PUT \
  --raw-field "resolved=true"
```

**Step 2**: Post the actual report as a reply, then re-resolve the discussion (GitLab unresolves a discussion when a new reply is added).

```bash
glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/discussions/${DISCUSSION_ID}/notes" \
  --method POST \
  --raw-field "body=$(cat <<'COMMENT'
## Pipeline Babysitter Report

**Pipeline**: <pipeline_url> | **Status**: <pipeline_status> | **Commit**: `<pipeline_sha>`
**Action round**: 1 of 5

### Failed Jobs

**`<job_name>`** · stage: `<stage>`
- **Failure summary**: <1-2 line description from log>
- **Classification**: FLAKY | MASTER_BROKEN | LINT | COVERAGE | REAL_FAILURE | UNKNOWN
- **Known issue**: <URL or "none found">
- **Action taken**: <description or "none — requires manual fix">

_(repeat for each failed job)_

### Summary

| Classification | Jobs | Action |
|----------------|------|--------|
| Flaky | N | Retried (attempt M of 2) / pipeline retried |
| Master broken | N | Pipeline retried / linked issue |
| Lint | N | Auto-fixed and pushed |
| Coverage | N | Retried / requires manual fix |
| Real failure | N | **Requires manual fix** |
| Unknown | N | Retried once |

_Waiting for pipeline to finish before next check._

---
*Generated by `/babysit-mr`*
COMMENT
)"

# Re-resolve the discussion (replying unresolves it)
glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/discussions/${DISCUSSION_ID}" \
  --method PUT \
  --raw-field "resolved=true"
```

### Subsequent reports: Reply to existing discussion

```bash
glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/discussions/${DISCUSSION_ID}/notes" \
  --method POST \
  --raw-field "body=<report body>"

# Re-resolve the discussion (replying unresolves it)
glab api "projects/${PROJECT_ENCODED}/merge_requests/${MR_IID}/discussions/${DISCUSSION_ID}" \
  --method PUT \
  --raw-field "resolved=true"
```

Store `DISCUSSION_ID` across action rounds so all updates form a single thread.

---

## Phase 6: Diagnose Blocking Failures

**Before posting the final blocked report**, attempt root-cause diagnosis for any failure classified as **REAL_FAILURE**, **MASTER_BROKEN**, **UNKNOWN**, or **REQUIRES_MANUAL_FIX**. This gives the MR author actionable information instead of just "requires manual fix".

For each blocking failure:

### REAL_FAILURE diagnosis
1. Correlate the failing test file with MR changes: `git diff origin/main --name-only`
2. Read the failing test to understand what it asserts
3. Read the relevant source code that the MR changed
4. Summarize: which MR change likely caused which assertion to fail, and suggest a fix direction

### MASTER_BROKEN diagnosis
1. Check if the same job/test fails on the `main` branch pipeline (use `glab api "projects/${PROJECT_ENCODED}/pipelines?ref=main&status=failed&per_page=3"`)
2. Search for related open issues: `bash scripts/search_known_issues.sh "<error>" "<project>"`
3. If confirmed broken on main: note the issue URL and whether a fix MR exists
4. Summarize: what's broken, who owns it (if identifiable from issue), and whether a workaround exists

### UNKNOWN diagnosis
1. Fetch more log context (increase to 300 lines): `bash scripts/job_log_tail.sh "<project_encoded>" "<job_id>" 300`
2. Re-attempt classification with the additional context
3. If still unclassifiable: note the job URL and the most distinctive error line for manual inspection

### REQUIRES_MANUAL_FIX diagnosis
1. If this was a lint auto-fix that failed: note what went wrong and which files need manual attention
2. If this was a coverage drop: identify which files lost coverage by reading the coverage report section of the log

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


