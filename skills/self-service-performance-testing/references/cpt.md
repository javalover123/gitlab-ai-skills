# CPT — Component Performance Testing

**Repo:** https://gitlab.com/gitlab-org/quality/component-performance-testing
**Status:** Alpha — reach out in **#g_performance_enablement** before adopting
**Existing tests (real-world example):** https://gitlab.com/gitlab-org/gitlab/-/tree/master/qa/performance_test/k6_test

CPT runs automated load tests on individual services in your MR pipeline via
multi-project pipelines. It's the only GitLab Performance Toolkit tool that
runs in your project's CI — no external repo needed.

## How It Works

1. Your MR pipeline triggers CPT as a multi-project pipeline
2. CPT provisions GCP VMs — one for the system-under-test (SUT), one for k6
3. CPT deploys your component via Docker Compose (or CNG instance)
4. CPT validates your k6 test files (checks for required exported constants)
5. CPT injects a `handleSummary()` function if missing (for reporting)
6. Tests run with `k6 run --no-thresholds` — CPT reports performance variance,
   not pass/fail
7. Results are posted as a comment on your MR with a metrics table
8. Optional: baseline comparison using statistical significance (Z-score,
   99% confidence) against historical data stored in GitLab Package Registry

## Prerequisites

- If testing a component: it must be containerized and deployable in isolation
- If running against a GitLab instance: use the CNG instance option
- Must expose testable interfaces (HTTP APIs, gRPC)
- k6 test files in your repo with required exported constants
- `docker-compose.yml` for component setup, or set `RUN_ON_CNG=true` in CI
  to run tests against a GitLab CNG instance

## CPT Test Conventions

CPT tests follow specific conventions that differ from standalone k6 tests.
CPT's validator checks for required exported constants; its summary injector
adds defaults for optional ones:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

// Required — CPT validator rejects files missing these
export const TEST_NAME = 'your_test_name';
export const TTFB_THRESHOLD = 25;          // p90 TTFB threshold in ms
export const RPS_THRESHOLD = 2;            // Minimum requests per second

// Optional — CPT injects defaults if missing (VUS=2, DURATION='50s')
export const LOAD_TEST_VUS = 2;
export const LOAD_TEST_DURATION = '50s';
export const WARMUP_TEST_VUS = 1;
export const WARMUP_TEST_DURATION = '10s';

export const options = {
  scenarios: {
    // Warmup scenario runs first to prime caches and connections
    warmup: {
      executor: 'constant-vus',
      vus: WARMUP_TEST_VUS,
      duration: WARMUP_TEST_DURATION,
      gracefulStop: '0s',
      tags: { scenario: 'warmup' },
    },
    // Load test starts after warmup completes
    load_test: {
      executor: 'constant-vus',
      vus: LOAD_TEST_VUS,
      duration: LOAD_TEST_DURATION,
      startTime: '10s',
      tags: { scenario: 'load_test' },
    },
  },
  thresholds: {
    // Scoped to load_test scenario (excludes warmup)
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
  // Dynamic setup: search for test data by name rather than hardcoded IDs
  return { baseUrl, token };
}

export default function yourTest(data) {
  // Test implementation
  sleep(1);
}
```

### Key Differences from Standalone k6 Tests

| Convention | CPT tests | Standalone k6 tests |
|---|---|---|
| Executor | `constant-vus` | Arrival-rate executor preferred (e.g., `constant-arrival-rate`) |
| Warmup | Separate warmup scenario | Not typical |
| Thresholds | On `http_req_waiting` (TTFB), `abortOnFail: false` | On `http_req_duration`, fail on breach |
| Auth env var | `GITLAB_QA_ADMIN_ACCESS_TOKEN` | `PRIVATE_TOKEN` |
| Base URL env var | `GITLAB_URL` with nip.io fallback | `BASE_URL` |
| Console.log | Used for CPT reporting | Avoid in hot path |
| Exported constants | Required — CPT reads them | Not needed |

## Adding CPT to Your MR Pipeline

```yaml
# Job 1: Export CI variables for CPT
dotenv-vars:
  stage: test
  script:
    - echo "JOB_WITH_ARTIFACTS=${CI_JOB_NAME}" >> variables.env
    - echo "JOB_WITH_ARTIFACTS_ID=${CI_JOB_ID}" >> variables.env
  artifacts:
    expire_in: 1 hour
    reports:
      dotenv: variables.env

# Job 2: Trigger CPT as a multi-project pipeline
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
    COMPONENT_SERVICE_NAME: "your-service-name"
    TEST_FILE_LOCATION: "qa/performance_test/k6_test"
    DOCKER_COMPOSE_FILE_LOCATION: "qa/performance_test/setup"
```

## Folder Structure

```
your-project/
└── qa/
    └── performance_test/
        ├── k6_test/
        │   ├── group_merge_requests.js
        │   └── project_merge_requests.js
        └── setup/
            └── docker-compose.yml
```

## MR Reporting

CPT posts a comment on the MR with an immediate answer to "did my change
hurt performance?" It includes:

- **Performance metrics** — VUS, RPS, TTFB avg/p90 for each test
- **Code path analysis** — whether the MR's changed code intersects with the
  endpoints under test; prevents false alarms when the test covers code the
  MR didn't touch
- **Environment summary** — infrastructure context to rule out infra noise
- **Automated analysis** — interprets results and surfaces regressions or
  improvements in plain language

CPT reports variance, not pass/fail — automated analysis frames whether
the variance is significant.

## CNG Instance Option

For testing against a full GitLab CNG instance instead of Docker Compose,
useful for testing GitLab-specific APIs:

- Set `RUN_ON_CNG: "true"` and provide `GITLAB_HELM_CHART_REF`
- Optional: use `DATA_SEEDER_FILE_NAME` for data seeding via the
  data-seeder framework (`ee/db/seeds/data_seeder/` in gitlab-org/gitlab)
- Uses larger GCP VM (`n2-standard-8`) — ~20-25 min setup vs ~2-5 min
  for Docker Compose

## Scope

**What CPT tests:** Component throughput and response times (TTFB, RPS),
error handling performance, configuration-related performance impacts,
regression detection at the MR level.

**What CPT does NOT test:** Integration bottlenecks between components,
production-scale data volume issues, end-to-end system performance (use
GPT for that).
