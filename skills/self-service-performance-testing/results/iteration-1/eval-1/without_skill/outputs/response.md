Hi! Yes, CPT (Component Performance Testing) is exactly the right tool for what you're describing. Your container registry service is a textbook fit: it's containerized, deployable in isolation, and exposes HTTP APIs, and CPT is the only GitLab Performance Toolkit tool that runs directly in your MR pipeline. Here's how it works and how to set it up.

Repo: https://gitlab.com/gitlab-org/quality/component-performance-testing
A real-world CPT test layout to copy from: https://gitlab.com/gitlab-org/gitlab/-/tree/master/qa/performance_test/k6_test

One heads-up before you invest time: **CPT is currently in alpha.** Please reach out in **#g_performance_enablement** on Slack before adopting it so the team knows you're onboarding and can help you through the rough edges.

## What CPT does

CPT runs automated load tests on your service inside your MR pipeline via a multi-project pipeline trigger. The flow:

1. Your MR pipeline triggers CPT as a downstream (multi-project) pipeline.
2. CPT provisions two GCP VMs, one for your system-under-test (SUT) and one to run k6.
3. It deploys your component via Docker Compose (or a full GitLab CNG instance if you need GitLab-specific APIs).
4. It validates your k6 test files (they must export a few required constants, more below).
5. It runs the tests with `k6 run --no-thresholds` and posts a comment on your MR with a metrics table.

Important mental model: **CPT reports variance, not pass/fail.** It doesn't gate your merge on a hard threshold. Instead it gives you an immediate answer to "did my change hurt performance?" via a metrics table, automated plain-language analysis, and a code-path analysis that checks whether the code your MR changed actually intersects the endpoints under test (this avoids false alarms when the test covers code you didn't touch). It can also do statistical baseline comparison (Z-score, 99% confidence) against historical runs.

## Prerequisites

You've already got most of these covered:

- Component must be containerized and deployable in isolation (you're good).
- Must expose testable interfaces, HTTP APIs or gRPC (you're good).
- A `docker-compose.yml` that stands up your registry component.
- k6 test files with the required exported constants (see below).

## Test file conventions

CPT tests differ from standalone k6 tests, so don't just drop in a generic k6 script. CPT's validator requires certain exported constants, and it expects a warmup + load-test scenario structure. A minimal test looks like this:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

// Required — CPT's validator rejects files missing these
export const TEST_NAME = 'registry_manifest_read';
export const TTFB_THRESHOLD = 25;   // p90 time-to-first-byte threshold in ms (reference value)
export const RPS_THRESHOLD = 2;     // minimum requests per second (reference value)

// Optional — CPT injects defaults if you omit them (VUS=2, DURATION='50s')
export const LOAD_TEST_VUS = 2;
export const LOAD_TEST_DURATION = '50s';
export const WARMUP_TEST_VUS = 1;
export const WARMUP_TEST_DURATION = '10s';

export const options = {
  scenarios: {
    // Warmup runs first to prime caches and connections
    warmup: {
      executor: 'constant-vus',
      vus: WARMUP_TEST_VUS,
      duration: WARMUP_TEST_DURATION,
      gracefulStop: '0s',
      tags: { scenario: 'warmup' },
    },
    // Load test starts after warmup
    load_test: {
      executor: 'constant-vus',
      vus: LOAD_TEST_VUS,
      duration: LOAD_TEST_DURATION,
      startTime: '10s',
      tags: { scenario: 'load_test' },
    },
  },
  thresholds: {
    // Scoped to the load_test scenario so warmup doesn't skew results
    'http_req_waiting{scenario:load_test}': [
      { threshold: `p(90)<${TTFB_THRESHOLD}`, abortOnFail: false },
    ],
    'http_reqs{scenario:load_test}': [
      { threshold: `rate>=${RPS_THRESHOLD}`, abortOnFail: false },
    ],
  },
};

export function setup() {
  const baseUrl = __ENV.GITLAB_URL || `http://gitlab.${__ENV.AI_GATEWAY_IP}.nip.io`;
  const token = __ENV.GITLAB_QA_ADMIN_ACCESS_TOKEN || '';
  return { baseUrl, token };
}

export default function registryTest(data) {
  // Hit your registry API endpoints here, e.g. manifest read/write, blob pulls
  sleep(1);
}
```

Key differences from a normal k6 test to keep in mind:

- Executor is `constant-vus` (not an arrival-rate executor).
- There's a dedicated warmup scenario.
- Thresholds are on `http_req_waiting` (TTFB) with `abortOnFail: false` (CPT won't hard-fail on a breach).
- The exported constants are mandatory: CPT reads them.

Note the `TTFB_THRESHOLD` and `RPS_THRESHOLD` are reference values only. Because CPT runs with `--no-thresholds` and uses variance analysis, you don't need to go through the usual "measure a baseline, set a regression budget" exercise you'd do for a standalone k6 or GPT test. Just set sensible reference numbers for your registry endpoints.

## Folder structure

```
your-project/
└── qa/
    └── performance_test/
        ├── k6_test/
        │   └── registry_manifest.js
        └── setup/
            └── docker-compose.yml
```

## Wiring it into your MR pipeline

Add two jobs to your `.gitlab-ci.yml` (or a `.gitlab/ci/*` include):

```yaml
# Job 1: Export CI variables CPT needs
dotenv-vars:
  stage: test
  script:
    - echo "JOB_WITH_ARTIFACTS=${CI_JOB_NAME}" >> variables.env
    - echo "JOB_WITH_ARTIFACTS_ID=${CI_JOB_ID}" >> variables.env
  artifacts:
    expire_in: 1 hour
    reports:
      dotenv: variables.env

# Job 2: Trigger CPT as a downstream multi-project pipeline
tests:performance:
  stage: test
  needs: [dotenv-vars]
  trigger:
    project: gitlab-org/quality/component-performance-testing
    strategy: depend
  variables:
    PROJECT_ID: $CI_PROJECT_ID
    PARENT_PIPELINE_COMMIT_BRANCH: $CI_COMMIT_BRANCH
    PARENT_PIPELINE_SOURCE: $CI_PIPELINE_SOURCE
    PARENT_PIPELINE_MR_IID: $CI_MERGE_REQUEST_IID
    COMPONENT_MR_CI_COMMIT_SHA: $CI_COMMIT_SHORT_SHA
    COMPONENT_SERVICE_NAME: "container-registry"   # your service name
    TEST_FILE_LOCATION: "qa/performance_test/k6_test"
    DOCKER_COMPOSE_FILE_LOCATION: "qa/performance_test/setup"
```

`strategy: depend` makes your pipeline wait on and reflect the CPT pipeline's status.

## Docker Compose vs. CNG

For a standalone service like the container registry, the **Docker Compose** path is the right one: you provide a `docker-compose.yml` that stands up your component, and setup takes roughly 2-5 minutes. (The alternative, a full GitLab CNG instance via `RUN_ON_CNG: "true"`, is for testing GitLab-specific APIs and uses a much larger VM with ~20-25 min setup, you don't need that here.)

## Scope check

CPT is good at component throughput and response times (TTFB, RPS), error-handling performance, config-related perf impacts, and MR-level regression detection. It does **not** cover integration bottlenecks between components, production-scale data volume, or end-to-end system performance, that's what GPT (the GitLab Performance Tool) is for, if you later need it.

## Suggested next steps

1. Ping **#g_performance_enablement** to flag that you're onboarding a new component (recommended given the alpha status).
2. Add a `qa/performance_test/setup/docker-compose.yml` that boots your registry.
3. Write one or two k6 test files under `qa/performance_test/k6_test/` targeting your key registry endpoints (manifest read/write, blob pull), following the conventions above.
4. Add the two CI jobs to your MR pipeline.
5. Open an MR and check the CPT comment it posts.

Happy to help draft the k6 test for specific registry endpoints or review your `docker-compose.yml` if you share them.
