# GitLab CI Integration for Performance Tests

Pipeline configuration for performance testing in GitLab CI. Before building
custom CI jobs, check if CPT covers the use case — it's the only toolkit tool
that runs in your project's CI. See cpt.md.

The custom CI configurations below are for teams that need tests embedded in
their project's pipeline (e.g., custom k6 tests, sitespeed.io budget checks).

## Strategy: Smoke in CI, Load on Schedule

This strategy applies to GPT and custom k6 tests. For CPT pipeline setup,
see cpt.md.

| Test Type | When | Pipeline Behavior | Environment |
|---|---|---|---|
| **Smoke test** | Every MR | Fail pipeline on threshold breach | Perf env / ephemeral |
| **Baseline load** | Scheduled (nightly/2x weekly) | Fail pipeline on threshold breach | Dedicated perf env |
| **Stress test** | Pre-release (manual trigger) | `allow_failure: true` | Dedicated perf env |
| **sitespeed.io budget** | MR (when frontend changes) | Fail pipeline on budget breach | Perf env |

Don't run large load tests in auto-deploy pipelines — they take 5-15+
minutes and can produce false positives.

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
    - your-perf-runner-tag
```

**Template variables:** `K6_TEST_FILE` (path to test script), `K6_OPTIONS`
(additional CLI flags), `K6_DOCKER_OPTIONS` (extra Docker flags).

The template generates a Load Performance report artifact. GitLab shows
comparison data in the MR widget. Requires at least one prior run on the
target branch for baseline data.

### Dynamic environments (review apps)

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
    - your-perf-runner-tag
```

## k6 Custom Job Snippets

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
    - your-perf-runner-tag
```

### Baseline load test (scheduled)

```yaml
perf_load:
  stage: performance
  image:
    name: grafana/k6:1.6.0
    entrypoint: ['']
  script:
    # Run twice consecutively for reliability
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
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
  tags:
    - your-perf-runner-tag
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
  allow_failure: true
  rules:
    - if: $CI_PIPELINE_SOURCE == "web"
      when: manual
  tags:
    - your-perf-runner-tag
```

## sitespeed.io in GitLab CI

### Per-MR budget check

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
    - your-perf-runner-tag
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
    - your-perf-runner-tag
```

## Runner Considerations

Performance tests need consistent infrastructure to produce comparable
results. Use a dedicated runner with fixed CPU, memory, and network if
possible. If using shared runners as a temporary fallback, add
`allow_failure: true` and a `# TODO: Migrate to dedicated perf runner`
comment.

For k6: ~1 GB RAM per 1000 VUs. For sitespeed.io: 2+ cores,
`--cap-add=NET_ADMIN` for throttle, `--shm-size 2g` for Firefox.

Contact **#g_performance_enablement** for help provisioning dedicated
performance infrastructure.

## Result Storage

Use `--summary-export=summary.json` with k6 and store as a
`load_performance` artifact (enables the MR widget comparison). For
sitespeed.io, use `--budget.output junit` and store as a `junit` artifact
report.

## Dealing with Noise

Performance tests in CI are inherently noisier than in dedicated environments.
Key strategies: run each test at least twice consecutively, use p90/p95
thresholds (not p99 or max), apply ramp-up and ramp-down periods to avoid
cold-start and abrupt-stop outliers, alert on consecutive failures rather
than single ones, pin tool versions (`grafana/k6:1.6.0`,
`sitespeedio/sitespeed.io:39.4.2`), and use consistent runners. If a test fails, check runner health before
investigating application code.
