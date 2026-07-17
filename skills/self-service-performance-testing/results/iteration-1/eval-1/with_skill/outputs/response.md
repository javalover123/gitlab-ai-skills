Yes, CPT (Component Performance Testing) is exactly the right tool for this. Your situation is basically the textbook case for it: a containerized service with HTTP APIs where you want performance feedback inside your MR pipeline. CPT is the only tool in GitLab's Performance Toolkit that runs in your project's own CI via a multi-project pipeline trigger, so nothing external gets bolted onto your repo. It runs a k6 load test against your component and posts a comment on the MR with the results.

Two upfront notes before you sink time into this:

- **CPT is currently in alpha.** Please reach out in **#g_performance_enablement** on Slack before adopting it so the Performance Enablement team can help you scope the setup and catch anything environment-specific. The repo is https://gitlab.com/gitlab-org/quality/component-performance-testing.
- **Never point performance tests at staging or production.** You don't have to worry about this with CPT specifically — it provisions its own throwaway GCP VMs and deploys your component in isolation — but it's worth stating since it's the one rule that causes real outages. CPT keeps you safe here by design.

Also worth doing first: check whether perf tests already exist. Search your `.gitlab-ci.yml` and `.gitlab/ci/**` for `performance`, `component-performance-testing`, or `k6`, and grep your test files for `import ... k6`. If something's already wired up, build on it rather than starting fresh.

## How CPT works

1. Your MR pipeline triggers CPT as a multi-project pipeline.
2. CPT provisions GCP VMs — one for your service (the system-under-test), one to run k6.
3. It deploys your component via Docker Compose (that's your path, since the registry is containerized and deployable in isolation).
4. It validates your k6 test files (they must export a few required constants — see below).
5. Tests run with `k6 run --no-thresholds`. **CPT reports performance variance, not pass/fail** — so it won't block your MR, it tells you whether your change moved the numbers.
6. Results land as a comment on your MR with a metrics table (VUS, RPS, TTFB avg/p90), plus a code-path analysis that flags whether your MR's changed code actually intersects the endpoints under test (this prevents false alarms).

Because CPT uses variance analysis rather than a pass/fail gate, you can skip the whole "measure a baseline and set a regression budget" exercise you'd normally do for a plain k6 test. The `TTFB_THRESHOLD` / `RPS_THRESHOLD` values in the test file are just reference points, not gates.

## Setup

### 1. Folder structure

```
your-project/
└── qa/
    └── performance_test/
        ├── k6_test/
        │   └── manifest_pull.js      # one file per endpoint you want to test
        └── setup/
            └── docker-compose.yml    # brings up the registry in isolation
```

### 2. A CPT k6 test stub

CPT tests follow specific conventions that differ from standalone k6 (different executor, a warmup scenario, thresholds on TTFB, and required exported constants). Here's a minimal, adaptable starting point — swap in your real registry endpoint:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

// Required — CPT's validator rejects files missing these
export const TEST_NAME = 'registry_manifest_pull';
export const TTFB_THRESHOLD = 25;   // p90 time-to-first-byte in ms (reference value)
export const RPS_THRESHOLD = 2;     // minimum requests/sec (reference value)

// Optional — CPT injects defaults (VUS=2, DURATION='50s') if omitted
export const LOAD_TEST_VUS = 2;
export const LOAD_TEST_DURATION = '50s';
export const WARMUP_TEST_VUS = 1;
export const WARMUP_TEST_DURATION = '10s';

export const options = {
  scenarios: {
    warmup: {
      executor: 'constant-vus',
      vus: WARMUP_TEST_VUS,
      duration: WARMUP_TEST_DURATION,
      gracefulStop: '0s',
      tags: { scenario: 'warmup' },
    },
    load_test: {
      executor: 'constant-vus',
      vus: LOAD_TEST_VUS,
      duration: LOAD_TEST_DURATION,
      startTime: '10s',           // starts after warmup finishes
      tags: { scenario: 'load_test' },
    },
  },
  thresholds: {
    'http_req_waiting{scenario:load_test}': [
      { threshold: `p(90)<${TTFB_THRESHOLD}`, abortOnFail: false },
    ],
    'http_reqs{scenario:load_test}': [
      { threshold: `rate>=${RPS_THRESHOLD}`, abortOnFail: false },
    ],
  },
};

export function setup() {
  const baseUrl = __ENV.GITLAB_URL || `http://${__ENV.AI_GATEWAY_IP}.nip.io`;
  return { baseUrl };
}

export default function (data) {
  const res = http.get(`${data.baseUrl}/v2/`);   // e.g. registry API base
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(1);
}
```

Start with your highest-traffic / most-changed registry endpoints — manifest pulls/pushes, blob operations, etc. One test file per endpoint keeps the reporting readable.

### 3. Wire it into your `.gitlab-ci.yml`

```yaml
# Job 1: export CI variables CPT needs
dotenv-vars:
  stage: test
  script:
    - echo "JOB_WITH_ARTIFACTS=${CI_JOB_NAME}" >> variables.env
    - echo "JOB_WITH_ARTIFACTS_ID=${CI_JOB_ID}" >> variables.env
  artifacts:
    expire_in: 1 hour
    reports:
      dotenv: variables.env

# Job 2: trigger CPT as a multi-project pipeline
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
    COMPONENT_SERVICE_NAME: "container-registry"       # <- your service
    TEST_FILE_LOCATION: "qa/performance_test/k6_test"
    DOCKER_COMPOSE_FILE_LOCATION: "qa/performance_test/setup"
```

## A couple of things to keep in mind

- **Prerequisites you already meet:** the component is containerized, deployable in isolation, and exposes testable HTTP interfaces. You'll just need a `docker-compose.yml` under `qa/performance_test/setup/` that brings the registry up on its own.
- **CNG option (probably not for you):** there's a `RUN_ON_CNG=true` mode that runs tests against a full GitLab instance instead of Docker Compose. That's meant for GitLab-specific APIs and uses a bigger VM with ~20-25 min setup. For an isolated registry component, stick with Docker Compose (~2-5 min setup).
- **What CPT won't catch:** integration bottlenecks between components, production-scale data-volume issues, or end-to-end system performance. Those are GPT's job, not CPT's. CPT is squarely about "did this MR regress my component's throughput/response times."

## Reference points

- Real-world CPT tests you can crib from: https://gitlab.com/gitlab-org/gitlab/-/tree/master/qa/performance_test/k6_test
- CPT repo: https://gitlab.com/gitlab-org/quality/component-performance-testing
- And again, since it's alpha — ping **#g_performance_enablement** on Slack before you go too deep. They'll happily help you get the first run green.
