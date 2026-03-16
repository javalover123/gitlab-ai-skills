---
name: self-service-performance-testing
description: Help engineers write performance tests that detect regressions, using k6 for load testing and sitespeed.io for frontend Core Web Vitals. Use when the user is adding or changing API endpoints, database queries, critical paths, or frontend pages and needs to decide whether to write a performance test, what kind, or how to integrate it into CI. Also activate when the user mentions load testing, stress testing, response times, benchmarking, performance budgets, or wants to run tests against staging - this skill enforces shared infrastructure safety rules. Does not cover profiling, APM, or debugging production incidents.
version: 0.1.0
license: MIT
compatibility: opencode
---

# Self-Service Performance Testing

Help engineers performance test their changes using GitLab's Performance
Testing Kit (PTK). Route to the right tool, enforce safety rules, and guide
through the workflow.

## DANGER: Shared Infrastructure

> **Performance tests can take environments offline.** If staging or production
> goes down, your entire deployment pipeline breaks. Every merge is blocked.
> Every release is delayed. Every team is affected.
>
> **NEVER run performance tests against staging or production.**
>
> Use a dedicated performance environment or a CI-aware isolated setup. There
> are no exceptions. "Just a quick smoke test" against staging is how outages
> start. If you don't have a dedicated environment, consider reaching out to
> **#g_performance_enablement** on Slack for help setting one up.

## Choose the Right Tool

GitLab maintains a **Performance Testing Kit (PTK)** — use these tools rather
than building from scratch:

| What you're testing | Tool | Where it runs | Status |
|---|---|---|---|
| API endpoints, backend load | [**GPT** (GitLab Performance Tool)](https://gitlab.com/gitlab-org/quality/performance) | External — separate repo, Docker | Stable |
| Frontend page load / Core Web Vitals | [**Sitespeed Runway**](https://gitlab.com/gitlab-org/quality/sitespeed-runway) | External — hosted service + API | Stable |
| Component in isolation (in your MR) | [**CPT** (Component Performance Testing)](https://gitlab.com/gitlab-org/quality/component-performance-testing) | In your MR pipeline — multi-project CI | Alpha |

**GPT and Sitespeed Runway are external to your repo.** You won't add test
files to your project — you'll configure and run tests from those tools'
repos or services. CPT is the exception: it runs in your MR pipeline via a
multi-project trigger.

For detailed setup, quick starts, and links: [ptk-tools.md](references/ptk-tools.md)

## How to Use This Skill

Match the engineer's situation to the right path:

| Situation | Go to |
|---|---|
| "Should I perf test this?" / Unsure what to do | [getting-started.md](references/getting-started.md) - decision framework, which tool, regression budgets |
| Need to set up GPT, Sitespeed Runway, or CPT | [ptk-tools.md](references/ptk-tools.md) - setup, quick starts, links |
| Writing or reviewing a k6 test (GPT or custom) | [quick-reference.md](references/quick-reference.md) - principles, patterns, output shape |
| Need deep k6 help (executors, thresholds, data) | [k6-patterns.md](references/k6-patterns.md) - comprehensive k6 guide |
| Adding perf tests to CI pipeline | [gitlab-ci-integration.md](references/gitlab-ci-integration.md) - CPT, GPT, custom CI |
| Stuck or need human input | **#g_performance_enablement** on Slack |

## Workflow

Follow this sequence. Do not skip steps or jump straight to authoring.

1. **Decide:** Does this change need a perf test? (see decision framework below)
2. **Choose the tool:** API/backend → GPT. Frontend/CWV → Sitespeed Runway. Component in MR → CPT. See [ptk-tools.md](references/ptk-tools.md).
3. **Define the target:** What user behavior is being tested? Map to a scenario, not an endpoint.
4. **Set the criterion:** What does "too slow" mean? Arrive at a number — baseline + regression budget. "Fast" is not a threshold.
5. **Author/configure the test:** Follow the tool's workflow. For GPT/custom k6, use quick-reference.md principles and examples/ as templates.
6. **Baseline:** Run the test at least twice against the current version (before the change). Record p95/p99 and error rate.
7. **Wire into CI:** CPT for MR-level. GPT for scheduled load tests. See gitlab-ci-integration.md.

If a test already exists for this path, skip to step 7 — run it and compare.

## Should I Write a Performance Test?

Use this decision framework before writing any code.

Write a test if any of these apply: touches a hot path or critical user journey, new user-facing API endpoint, changes DB queries or adds N+1 risk, adds heavy I/O or external calls, or anything else non-cosmetic.

**Background jobs (e.g. Sidekiq):** test the API endpoint that enqueues the job, not the job itself. k6 tests HTTP — if enqueueing adds latency to the triggering request, that's what matters.

**Test already exists:** run it and compare against the existing baseline. Do not write a new test.

**No test needed:** UI copy, docs, or config-only changes.

### What Type of Test?

| Change Type | Test Type | Tool |
|---|---|---|
| New API endpoint | Smoke + Baseline (target RPS, 5 min) | GPT or custom k6 |
| Critical path change | Baseline (target RPS, 5-10 min) | GPT or custom k6 |
| Scaling concern | Stress (ramp to 2-3x normal) | GPT or custom k6 |
| Incident follow-up | Spike (sudden burst) | Custom k6 |
| Component in isolation | MR-level load test | CPT |
| New page or layout change | CWV budget check | Sitespeed Runway |
