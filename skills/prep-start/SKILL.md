---
name: prep-start
description: "Start a GitLab Platform Readiness Enablement Process (PREP) assessment for a new feature, service, or infra change. Use when asked whether a feature needs PREP, to kick off/begin a PREP or readiness assessment, to create a PREP tracking issue, or to set up the first PREP merge request. Do not use for checking the status of, reviewing, or responding to feedback on an already-started PREP; use prep-review for that instead."
version: 0.1.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: gitlab
  keywords: PREP, readiness assessment, platform readiness, production readiness, infrastructure platforms
---

# prep-start

PREP (Platform Readiness Enablement Process) evaluates whether a GitLab feature is ready for production across GitLab.com, Dedicated, and Self-Managed. It lives entirely in [`gitlab-org/architecture/readiness`](https://gitlab.com/gitlab-org/architecture/readiness), a private repo: the process narrative sits in its `README.md`, blank questionnaires live under `templates/<category>/`, and filled-in assessments live under `features/<feature>/<category>/`. Handbook overview: [PREP](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production/prep/).

## Step 1: decide if PREP applies

Ask whether the feature introduces a new service or component, new infra dependencies (a database, an external service, a storage backend, networking), significant compute, storage, or scaling needs, new install, config, or deployment steps, platform-specific behavior, or new security, monitoring, backup, or upgrade concerns. Any yes means PREP applies. Pure additions inside an existing service usually don't need it.

If the work needs Infrastructure Platforms support for packaging or rolling out a genuinely new internal component, check with the requester whether a **Platforms Dependency Intake** issue (`.gitlab/issue_templates/Platforms Dependency Intake.md` in the readiness repo) needs completing first. It's a separate, earlier gate some teams require before the PREP Assessment issue.

## Step 2: create the tracking issue

```bash
glab issue create -R gitlab-org/architecture/readiness --template Assessment \
  --title "Readiness Assessment: <Feature Name>"
```
Fill in overview, business context, target platforms, and current development stage. This issue coordinates every MR you open below, so link it from all of them.

## Step 3: clone, branch, and copy templates for your stage

```bash
git clone git@gitlab.com:gitlab-org/architecture/readiness.git && cd readiness
git checkout -b <feature_name>
mkdir -p features/<feature_name>
cp templates/README.md features/<feature_name>/README.md   # feature status file, no CODEOWNERS entry
```
Copy only templates you can meaningfully answer now, matched to your stage:

| Stage | Categories to start with |
|---|---|
| PoC / Early Design | `service_architecture`, `security_compliance`, `platform_strategy`, `build` |
| Experimental / Beta | + `installation_configuration`, `performance_scalability`, `observability` |
| Pre-GA | all applicable categories, thorough evidence, no open gaps without a remediation plan |

Not every category applies to every feature. Mark genuinely inapplicable ones `NOT APPLICABLE` with a one-line reason, but see [references/review-and-splitting.md](references/review-and-splitting.md) for why reviewers scrutinize blanket N/A answers.

## Step 4: open one MR per CODEOWNERS owner, not per category

**The category folder name is not the owner.** Several categories share one team, and per-file overrides put a single file under a different owner than the rest of its folder, sometimes requiring two approvals at once. Always resolve ownership from the live `CODEOWNERS` file before deciding how to split your MRs. The exact split logic and the invite gotcha that silently makes a team's approval optional live in [references/review-and-splitting.md](references/review-and-splitting.md).

```bash
glab mr create -R gitlab-org/architecture/readiness \
  --template "Initial Assessment" --draft \
  --title "Initial Feature Readiness Assessment: <Feature Name>"
```
Scope each MR to one owning team's files, plus your feature `README.md`, which has no owner of its own. Mark it `Draft` if incomplete: an incomplete initial MR can still merge to establish a baseline.

## Step 5: answer with evidence, iterate with PREP Assistant

Every answer needs a link: an issue, an MR, a doc, a metric. Reframe "does X work well?" into "here's the analysis result for X." Unresolved gaps need a tracking issue with an owner and a target stage, not a bare TODO. [PREP Assistant](https://gitlab.com/gitlab-org/architecture/readiness/-/automate/agents/535/) can pre-fill answers from your GitLab issues, MRs, and epics, but it only reads GitLab resources (never arbitrary URLs or handbook pages), and it slows down once you feed it too much context. Work one category at a time, and commit each round to your MR before asking it to continue.

## Agent Guidelines

1. Don't invent reviewer handles: resolve them from the live `CODEOWNERS`, not from memory or this skill's examples.
2. Don't bundle every category into one giant MR to save time. CODEOWNERS review requires one approval per distinct owner touched, so an unsplit MR just waits longer for all of them.
3. Never fabricate evidence links or claim a category is complete without a real link per question.
4. Don't skip the Platforms Dependency Intake check for genuinely new internal infrastructure. Missing it is a common reason PREP assessments stall before they even start.

## References

| Topic | Location |
|---|---|
| CODEOWNERS resolution, MR splitting, the invite gotcha, a real-world example | [references/review-and-splitting.md](references/review-and-splitting.md) |
