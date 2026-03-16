# GitLab CI Integration for Performance Tests

Pipeline configuration for performance testing in GitLab CI.

## Recommended: Use PTK Tools First

Before building custom CI jobs, check if GitLab's Performance Testing Kit
covers your needs:

- **CPT** — runs component load tests in your MR pipeline via multi-project
  trigger. The only PTK tool that runs in your project's CI. See ptk-tools.md.
- **GPT** — runs externally via Docker for full load testing. Typically on
  scheduled pipelines, not per-MR.
- **Sitespeed Runway** — hosted service for frontend CWV. Can be called from
  CI via API but doesn't require CI integration.

The custom CI configurations below are for teams that need tests embedded in
their project's pipeline (e.g., custom k6 tests, sitespeed.io budget checks).

## Strategy: Smoke in CI, Load on Schedule

This is k6's official recommendation for CI/CD integration:

| Test Type | When | Pipeline Behavior | Environment |
|---|---|---|---|
| **Smoke test** | Every MR | Fail pipeline on threshold breach | Perf env / ephemeral |
| **Baseline load** | Scheduled (nightly/2x weekly) | Fail pipeline on threshold breach (with consistent runner) | Dedicated perf env |
| **Stress test** | Pre-release (manual trigger) | `allow_failure: true` - intentionally pushes past limits | Dedicated perf env |
| **sitespeed.io budget** | MR (when frontend changes) | Fail pipeline on budget breach | Perf env |

**Do not run large load tests in auto-deploy pipelines.** They take 5-15+
minutes and can produce false positives. Use scheduled pipelines for load
and stress tests.

## k6 with GitLab Built-in Template

GitLab provides a built-in template that handles Docker setup and the MR
widget report (Premium/Ultimate):

```yaml
include:
  template: Verify/Load-Performance-Testing.gitlab-ci.yml

load_performance:
  variables:
    K6_TEST_FILE: tests/performance/smoke.js
    K6_OPTIONS: '--duration 30s --vus 5'
  rules:
    - if: $CI_MERGE_REQUEST_IID
  tags:
    - your-perf-runner-tag  # See "Runner Options" below
```

### Template variables

| Variable | Purpose |
|---|---|
| `K6_TEST_FILE` | Path to k6 test script |
| `K6_OPTIONS` | Additional CLI flags |
| `K6_DOCKER_OPTIONS` | Extra Docker flags (e.g., `--env-file`) |

### MR widget

The template generates a Load Performance report artifact. GitLab shows
comparison data in the MR widget (checks pass rate, TTFB p90/p95, RPS).
Requires at least one prior run on the target branch for baseline data.

### Dynamic environments

For review apps or ephemeral environments:

```yaml
include:
  template: Verify/Load-Performance-Testing.gitlab-ci.yml

deploy_review:
  stage: deploy
  script:
    - deploy_to_review_app
    - echo "ENVIRONMENT_URL=${CI_ENVIRONMENT_URL}" >> review.env
  artifacts:
    paths:
      - review.env
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    url: http://$CI_ENVIRONMENT_SLUG.perf.example.com

load_performance:
  dependencies:
    - deploy_review
  variables:
    K6_TEST_FILE: tests/performance/smoke.js
    K6_DOCKER_OPTIONS: '--env-file review.env'
  rules:
    - if: $CI_MERGE_REQUEST_IID
  tags:
    - your-perf-runner-tag  # See "Runner Options" below
```

## k6 Custom Job Configuration

When you need more control than the template provides:

### Smoke test (per MR)

```yaml
perf_smoke:
  stage: test
  image:
    name: grafana/k6:1.6.0
    entrypoint: ['']
  script:
    - k6 run
        --env BASE_URL=${PERF_ENV_URL}
        --env PRIVATE_TOKEN=${PERF_PRIVATE_TOKEN}
        --summary-export=summary.json
        tests/performance/smoke.js
  artifacts:
    paths:
      - summary.json
    reports:
      load_performance: summary.json
    when: always
  rules:
    - if: $CI_MERGE_REQUEST_IID
  tags:
    - your-perf-runner-tag  # See "Runner Options" below
```

### Baseline load test (scheduled)

```yaml
perf_load:
  stage: performance
  image:
    name: grafana/k6:1.6.0
    entrypoint: ['']
  script:
    # Run twice consecutively for reliability (k6 recommendation)
    - k6 run
        --env BASE_URL=${PERF_ENV_URL}
        --env PRIVATE_TOKEN=${PERF_PRIVATE_TOKEN}
        --summary-export=summary-run1.json
        tests/performance/load.js
    - k6 run
        --env BASE_URL=${PERF_ENV_URL}
        --env PRIVATE_TOKEN=${PERF_PRIVATE_TOKEN}
        --summary-export=summary-run2.json
        tests/performance/load.js
  artifacts:
    paths:
      - summary-run1.json
      - summary-run2.json
    when: always
  # If running on shared runners (temporary), uncomment the next line:
  # allow_failure: true  # TODO: Migrate to dedicated runner (contact #g_performance_enablement)
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
  tags:
    - your-perf-runner-tag  # See "Runner Options" below
```

### Stress test (manual trigger)

```yaml
perf_stress:
  stage: performance
  image:
    name: grafana/k6:1.6.0
    entrypoint: ['']
  script:
    - k6 run
        --env BASE_URL=${PERF_ENV_URL}
        --env PRIVATE_TOKEN=${PERF_PRIVATE_TOKEN}
        --summary-export=stress-summary.json
        tests/performance/stress.js
  artifacts:
    paths:
      - stress-summary.json
    when: always
  allow_failure: true   # Stress tests intentionally push past limits - failures are expected
  rules:
    - if: $CI_PIPELINE_SOURCE == "web"
      when: manual
  tags:
    - your-perf-runner-tag  # See "Runner Options" below
```

## sitespeed.io in GitLab CI

### Per-MR budget check (triggered by frontend changes)

```yaml
frontend_perf:
  stage: test
  image:
    name: sitespeedio/sitespeed.io:39.4.2
    entrypoint: ['']
  script:
    - /start.sh
      --budget.configPath /sitespeed.io/budget.json
      --budget.output junit
      -c cable
      --browsertime.connectivity.engine throttle
      -n 5
      -b chrome
      ${PERF_ENV_URL}
  artifacts:
    paths:
      - sitespeed-result/
    reports:
      junit: sitespeed-result/**/junit.xml
    when: always
  rules:
    - if: $CI_MERGE_REQUEST_IID
      changes:
        - app/views/**/*
        - app/assets/**/*
        - app/javascript/**/*
  tags:
    - your-perf-runner-tag  # See "Runner Options" below
  variables:
    DOCKER_HOST: ""
```

### Scheduled CWV monitoring

```yaml
cwv_monitoring:
  stage: performance
  image:
    name: sitespeedio/sitespeed.io:39.4.2
    entrypoint: ['']
  script:
    - /start.sh
      --budget.configPath /sitespeed.io/budget.json
      --budget.output json
      -c cable
      --browsertime.connectivity.engine throttle
      -n 7
      -b chrome
      /sitespeed.io/urls.txt
  artifacts:
    paths:
      - sitespeed-result/
    when: always
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
  tags:
    - your-perf-runner-tag  # See "Runner Options" below
```

## Runner Options

Setting up a consistent runner takes 30 minutes. Running unreliable tests on
shared infrastructure for months wastes everyone's time. Get proper
infrastructure first.

**Need help? Contact `#g_performance_enablement`** - they have dedicated
performance infrastructure and can advise on provisioning for your team.

### Recommended: Dedicated or Consistent Runner

Register a GitLab Runner on a machine or VM with fixed CPU, memory, and
network. Tag it (`perf`, `performance`, `load-test` - your team's choice)
and target it with `tags:` in your CI jobs.

| Concern | Guidance |
|---|---|
| **Docker executor** | Required - k6 and sitespeed.io run via Docker images |
| **k6 resources** | ~1 GB RAM per 1000 VUs, adequate CPU for target RPS |
| **sitespeed.io resources** | 2+ cores (video recording), `--cap-add=NET_ADMIN` for throttle, `--shm-size 2g` for Firefox |
| **Network** | Runner must reach the perf test environment |
| **Consistency** | Same machine every run - comparable results over time |
| **Isolation** | Don't co-locate with other heavy workloads during test runs |

For large k6 tests: increase file descriptor limits, tune TCP settings
(see k6 "Fine-tune OS" documentation).

### Alternative: Ephemeral with Guaranteed Resources

For teams using Kubernetes runners or ephemeral VMs, set guaranteed resource
requests and limits (CPU, memory) on your pods. Results are reliable within
a resource profile but may drift if limits change. Tag the runner or use a
specific runner configuration.

### Temporary Fallback: Shared Runner (Code Smell)

If you truly cannot set up consistent infrastructure today, you can run on
shared runners with `allow_failure: true` so results don't block the
pipeline.

**This is a code smell.** It means you're running tests whose results you
can't trust. If you do this:

- Add a comment: `# TODO: Migrate to dedicated perf runner (contact #g_performance_enablement)`
- Review results manually - only compare within the same pipeline run, never
  across runs
- **Set a deadline to migrate to a dedicated or consistent runner.** This is
  not a permanent state.

## Result Storage

For GitLab CI, use `--summary-export=summary.json` with k6 and store as a
`load_performance` artifact (enables the MR widget comparison). For
sitespeed.io, use `--budget.output junit` and store as a `junit` artifact
report. Both tools support external outputs (Grafana Cloud, InfluxDB,
Prometheus, S3/GCS) - refer to their respective docs for configuration.

## Dealing with Noise and Flakiness

Performance tests in CI are inherently noisier than in dedicated environments.

### Strategies

1. **Run each test at least twice consecutively.** Ignore runs where results
   diverge significantly (k6 official recommendation).

2. **Use generous thresholds for CI gates.** Set p90 or p95, not p99 or max.
   Tail percentiles are sensitive to noise.

3. **Alert on consecutive failures, not single failures.** For scheduled tests,
   trigger alerts after 3+ consecutive threshold breaches.

4. **Use consistent runners.** Shared GitLab runners have variable resources.
   Set up a dedicated or resource-guaranteed runner - see "Runner Options"
   above. Contact `#g_performance_enablement` for guidance.

5. **Pin tool versions.** Pin k6 (`grafana/k6:1.6.0`) and sitespeed.io
   (`sitespeedio/sitespeed.io:39.4.2`). Version drift introduces variance.

6. **Separate infrastructure concerns from application concerns.** If a test
   fails, check runner health before investigating application code.

## Environment Rules

> **NEVER run performance tests against staging or production.**
> Performance tests generate significant load. Staging is shared infrastructure
> that supports the deployment pipeline. If it goes down, every merge is blocked.

| Environment | Allowed Tests | Notes |
|---|---|---|
| Dedicated perf env | All types (smoke, load, stress, spike, CWV) | Isolated, safe to push to limits |
| Ephemeral review app | Smoke tests only | Limited resources, not for load |
| Staging | **NEVER** | Shared infra, deployment pipeline dependency |
| Production | **NEVER** | Real users, real money, real consequences |
