# Phase 2: Failure Triage

Classify each blocking failure (`failed_jobs` and `failed_bridges` from
`mr_state.sh`). The goal is one question: **could the MR's changes have caused
this?** If yes, or if you can't rule it out, don't retry.

## Gather evidence

```bash
bash scripts/job_log_tail.sh "<project_encoded>" "<job_id>" 150   # project_encoded from mr_state.sh
```

- **Bridges** (`failed_bridges`): the real failure is in the downstream
  pipeline. List its failed jobs, then tail those logs using the downstream
  project ID:
  `glab api "projects/<downstream_project_id>/pipelines/<downstream_pipeline_id>/jobs?scope[]=failed"`
- **`failure_reason`** is the cheapest signal. `runner_system_failure`,
  `stuck_or_timeout_failure`, `scheduler_failure`, `api_failure`,
  `data_integrity_failure` point at infrastructure. `script_failure` means read the log.
- **The MR's changes**: `changed_files` from Phase 0. Compare against the failing
  spec path, the file:line in the backtrace, and the code under test.
- **Known flaky tests** (gitlab-org/gitlab uses the `failure::flaky-test` label):
  `glab issue list -R <project> --search "<spec file or test name>" --label "failure::flaky-test" --output json`
- **The target branch** (`target_branch` from `mr_state.sh`): did the same job
  fail on its recent pipelines? List them, then their failed jobs:
  `glab api "projects/<project_encoded>/pipelines?ref=<target_branch>&per_page=5"`
  `glab api "projects/<project_encoded>/pipelines/<id>/jobs?scope[]=failed"`
- **Incident signals**: `bash scripts/incident_status.sh` (see
  [incident-waiting.md](incident-waiting.md)).

## Classes

### TRANSIENT: retry now
Unrelated to the MR, no ongoing incident needed to explain it. On a test
failure, this class holds only for the **first** time the test fails. For a
repeat failure, see MR_RELATED.
- Infrastructure `failure_reason` (above), runner or Docker errors, `failed to pull image`
- Network: `connection reset`, `Could not resolve host`, `Net::ReadTimeout`,
  `fatal: unable to access`, one-off 5xx from a dependency
- A test the MR doesn't touch, in an area the MR doesn't touch, with an open
  `failure::flaky-test` issue, or that passes on the target branch

### INCIDENT: wait, then retry
Load or availability symptoms (5xx/429 from gitlab.com, Gitaly `DeadlineExceeded` /
`ResourceExhausted`, registry or package timeouts, jobs stuck pending, widespread
timeouts across unrelated jobs) **and** a matching live signal: status page not
operational for the relevant component, an active S1/S2 production incident
whose service matches, or a recent master-broken incident with a load or
infrastructure label: `master-broken::gitlab-com-overloaded`,
`master-broken::infrastructure*`, `master-broken::job-timeout`,
`master-broken::failed-to-pull-image`. Those labels make it INCIDENT even when
the incident names the failing job.
Symptoms without a live signal are TRANSIENT. A signal whose symptoms don't
match the failure is not evidence: several `Incident::Active` issues stay open for weeks.

### MASTER_BROKEN: wait for the fix, then new pipeline
The target branch itself is broken: a recent master-broken incident without a
load/infrastructure label names the failing job (titles read
`broken master with <job names>`; strip shard suffixes like ` 2/4` before
matching), or the same job fails on the target branch's own recent pipelines,
in code the MR didn't touch. Only a `merged_result` pipeline can pick up the
fix. On any other pipeline `kind`, alert straight away instead of waiting.

### MR_RELATED: alert, never retry
- Failing test, lint offense, or error location is in `changed_files`, or
  exercises code the MR changes
- Static checks on MR content: linters, schema/migration checks, docs lint,
  coverage (`undercoverage`), `danger` rules that block
- The same test fails the same way on two consecutive runs of this MR while
  passing on the target branch, even if it looked flaky the first time. The
  exceptions are an open `failure::flaky-test` issue for that test, or the
  test also failing on the target branch.

### UNKNOWN: treat as MR_RELATED
You can't tell from the logs, or the pipeline failed with no failed jobs to
look at (often a CI config error). Pull 300 log lines before deciding. If it's
still unclear, alert. A retry is cheap, but a wrong guess is the user's to make.

## Mixed results

Take the most severe class: MR_RELATED/UNKNOWN > MASTER_BROKEN/INCIDENT > TRANSIENT.
One MR-related failure means the pipeline cannot pass: alert without retrying
the others. Record every job's class and evidence for the alert.
