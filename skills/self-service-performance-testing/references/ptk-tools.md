# GitLab Performance Toolkit

GitLab maintains three performance testing tools. Use these rather than
building from scratch — they provide shared infrastructure, reporting, and
consistency across teams.

## Tool Selection

| What you're testing | Tool | Runs where |
|---|---|---|
| API endpoints, backend services, reference architectures | **GPT** | External repo, Docker |
| Frontend page load, Core Web Vitals | **Sitespeed Runway** | Hosted service |
| API endpoints, backend services — faster feedback at MR-level | **CPT** | Your MR pipeline |

## GPT — GitLab Performance Tool

**Repo:** https://gitlab.com/gitlab-org/quality/performance
**Quick start:** https://gitlab.com/gitlab-org/quality/performance/-/blob/main/docs/quick_start.md
**Existing tests:** https://gitlab.com/gitlab-org/quality/performance/-/tree/main/k6/tests

GPT is a Ruby orchestration layer around k6 with pre-built test suites for
GitLab API, web, and Git endpoints. It includes opinionated data generators,
version-aware thresholds, automatic scoring, and failure evaluation reports.

### How it works

GPT runs externally via Docker. You don't add test files to your project —
you configure and run tests from the GPT repo.

1. **Create admin user** on the target GitLab instance with API PAT (all
   permissions). Must be able to create groups.
2. **Configure environment** — JSON file with instance URL, user, Gitaly
   storage nodes
3. **Generate test data** — `docker run gitlab/gpt-data-generator` creates
   horizontal data (1000 subgroups × 10 projects) and vertical data (large
   projects with issues, MRs, pipelines, commits)
4. **Run tests** — `docker run gitlab/gitlab-performance-tool --environment
   <env>.json --options <load>.json`
5. **Interpret results** — Overall Results Score (target >90%), per-test
   RPS/TTFB/success rate, failure evaluation report with recommendations

### Test structure (k6 under the hood)

GPT tests are k6 scripts with GPT-specific metadata and helper modules:

- `k6/tests/api/` — REST API endpoint tests (100% of target RPS)
- `k6/tests/web/` — Web page response tests (10% of target RPS)
- `k6/tests/git/` — Git operation tests (10% of target RPS)
- `k6/tests/scenarios/` — Multi-step user journeys (excluded by default,
  require `--unsafe` flag as they create/delete data)

Each test file includes metadata comments that GPT uses for filtering:

```javascript
/*
@endpoint: `GET /api/v4/groups`
@description: Tests the groups list API endpoint
@gpt_data_version: 1
@flags: unsafe
@stressed_components: Rails, Postgres
@gitlab_version: 15.0
*/
import { logError, getRpsThresholds, getTtfbThreshold } from "../../lib/gpt_k6_modules.js"

// Version-aware thresholds — GPT selects based on target GitLab version
export let thresholds = {
  'rps': { '16.10.0': 0.6, 'latest': 0.6 },
  'ttfb': { '16.10.0': 2000, 'latest': 3000 },
};
```

**Helper modules:**
- `gpt_k6_modules.js` — `getRpsThresholds()`, `getTtfbThreshold()`,
  `getLargeProjects()`, `selectRandom()`, `logError()`, `adjustRps()`
- `gpt_git_functions.js` — Git protocol operations (clone, pull, push)
- `gpt_scenario_functions.js` — Group/project CRUD for scenario tests
- `gpt_data_helper_functions.js` — URL and pipeline helpers

### Scoring system

Per-test: `score = min((rps_achieved / rps_target) × success_rate, 100)`
Overall: average of per-test scores. Target: **>90%**.

Failed tests automatically retry once. Results output in JSON, CSV, TXT,
and a Markdown failure evaluation report with debugging recommendations.

### Load options

Predefined profiles mapped to GitLab reference architectures:

| Users | Target RPS | Option file |
|---|---|---|
| 1,000 | 20 | `60s_20rps.json` |
| 2,000 | 40 | `60s_40rps.json` |
| 5,000 | 100 | `60s_100rps.json` |
| 10,000 | 200 | `60s_200rps.json` |
| 25,000 | 500 | `60s_500rps.json` |
| 50,000 | 1000 | `60s_1000rps.json` |

Each option file defines ramp-up → sustained → ramp-down stages.

### Running GPT

```bash
# Docker (recommended)
docker run -it \
  -e ACCESS_TOKEN=<your-pat> \
  -v $(pwd)/config:/config \
  -v $(pwd)/results:/results \
  gitlab/gitlab-performance-tool \
  --environment 10k.json \
  --options 60s_200rps.json \
  --tests api

# Local (requires Ruby + k6)
./bin/run-k6 --environment 10k.json --options 60s_200rps.json --tests api
```

**Key flags:** `--tests api|web|git|scenarios`, `--unsafe` (enable
POST/PUT/DELETE tests), `--quarantined`, `--experimental`,
`--excludes <pattern>`.

**Key env var:** `ACCESS_TOKEN` (admin PAT with all permissions).

### When to use GPT

- Validating GitLab reference architectures
- Load testing API/web/git endpoints under realistic conditions
- Establishing performance baselines for backend changes
- Scheduled load tests (nightly/weekly)

### When NOT to use GPT

- Quick MR-level smoke test → use CPT or custom k6 in CI
- Frontend page load → use Sitespeed Runway
- You need a test embedded in your project's repo → custom k6

## Sitespeed Runway

**Repo:** https://gitlab.com/gitlab-org/quality/sitespeed-runway
**Self-service docs:** https://gitlab.com/gitlab-org/quality/sitespeed-runway/-/blob/main/docs/self-service.md
**Web UI:** https://sitespeed.runway.gitlab.net/
**Existing test configurations:** https://gitlab.com/gitlab-org/quality/sitespeed-runway/-/tree/main/tests

Sitespeed Runway is a hosted sitespeed.io service for measuring frontend
performance (FCP, LCP, TBT, CLS, SpeedIndex). It provides a Web UI for
manual testing and an API for automated testing.

### How to use it

**Option 1: Web UI** (quickest)
1. Go to https://sitespeed.runway.gitlab.net/
2. Enter the target URL
3. Configure: browser, iterations, connectivity (3g/4g/cable)
4. Run and view results

**Option 2: API via Docker** (recommended for automation)
```bash
docker run --cap-add=NET_ADMIN --shm-size=3g \
  -v "$(pwd):/sitespeed.io" \
  sitespeedio/sitespeed.io:37-plus1 \
  --api.hostname sitespeed.runway.gitlab.net \
  --api.port 443 \
  --api.location default \
  --api.action addAndGetResult \
  --api.key YOUR_API_KEY \
  -b chrome \
  https://your-app.example.com/page
```

**Option 3: Local Node.js**
```bash
sitespeed.io https://your-app.example.com/page \
  --api.hostname sitespeed.runway.gitlab.net \
  --api.port 443 \
  --api.location default \
  --api.action addAndGetResult \
  --api.key YOUR_API_KEY \
  --browsertime.browser chrome \
  --browsertime.iterations 3
```

### Key metrics and targets

| Metric | Target | What it measures |
|---|---|---|
| FCP (First Contentful Paint) | < 1.8s | Time until first content appears |
| LCP (Largest Contentful Paint) | < 2.5s | Time until largest element renders |
| TBT (Total Blocking Time) | < 200ms | Main thread blocking between FCP and TTI |
| CLS (Cumulative Layout Shift) | < 0.1 | Visual stability |
| SpeedIndex | < 3.4s | How quickly content visually populates |
| TTFB (Time to First Byte) | < 600ms | Server response time |

### When to use Sitespeed Runway

- Measuring Core Web Vitals for new or changed pages
- Comparing page load performance before/after a change
- Monitoring frontend performance trends over time

### When NOT to use Sitespeed Runway

- API/backend load testing → use GPT
- Component-level MR testing → use CPT

### Access

Login credentials are in 1Password under "Sitespeed Runway Production."
API key required for automated testing. Contact **#g_performance_enablement**
if you need access.

## CPT — Component Performance Testing

**Repo:** https://gitlab.com/gitlab-org/quality/component-performance-testing
**Status:** Alpha — reach out in **#g_performance_enablement** before adopting
**Existing tests (real-world example):** https://gitlab.com/gitlab-org/gitlab/-/tree/master/qa/performance_test/k6_test

CPT runs automated load tests on individual services in your MR pipeline via
multi-project pipelines. It's the only GitLab Performance Toolkit tool that runs in your project's
CI — no external repo needed.

### How it works

1. Your MR pipeline triggers CPT as a multi-project pipeline
2. CPT provisions GCP VMs — one for the system-under-test (SUT), one for k6
3. CPT deploys your component via Docker Compose (or CNG instance)
4. CPT validates your k6 test files (checks for required exported constants)
5. CPT injects a `handleSummary()` function if missing (for reporting)
6. Tests run with `k6 run --no-thresholds` — CPT reports performance variance, not pass/fail
7. Results are posted as a comment on your MR with a metrics table
8. Optional: baseline comparison using statistical significance (Z-score,
   99% confidence) against historical data stored in GitLab Package Registry

### Prerequisites

- If testing a component: it must be containerized and deployable in isolation
- If running against a GitLab instance: use the CNG instance option
- Must expose testable interfaces (HTTP APIs, gRPC)
- k6 test files in your repo with required exported constants
- `docker-compose.yml` for component setup, or set `RUN_ON_CNG=true` in CI to run tests against a GitLab CNG instance

### CPT test conventions

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
  // Return data for default function
  return { baseUrl, token };
}

export default function yourTest(data) {
  // Test implementation
  sleep(1);
}
```

**Key differences from standalone k6 tests:**

| Convention | CPT tests | Standalone k6 tests |
|---|---|---|
| Executor | `constant-vus` | `constant-arrival-rate` preferred |
| Warmup | Separate warmup scenario | Not typical |
| Thresholds | On `http_req_waiting` (TTFB), `abortOnFail: false` | On `http_req_duration`, fail on breach |
| Auth env var | `GITLAB_QA_ADMIN_ACCESS_TOKEN` | `PRIVATE_TOKEN` |
| Base URL env var | `GITLAB_URL` with nip.io fallback | `BASE_URL` |
| Console.log | Used for CPT reporting | Avoid in hot path |
| Exported constants | Required — CPT reads them | Not needed |

### Adding CPT to your MR pipeline

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

### Folder structure

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

### MR reporting

CPT posts a comment on your MR with an immediate answer to "did my change hurt performance?" It includes:

- **Performance metrics** — VUS, RPS, TTFB avg/p90 for each test
- **Code path analysis** — whether the MR's changed code intersects with the endpoints under test; prevents false alarms and unnecessary investigation when the test covers code the MR didn't touch
- **Environment summary** — infrastructure context to rule out "was it just infra noise?" as an explanation for variance
- **Automated analysis** — interprets results and surfaces regressions or improvements in plain language

CPT reports variance, not pass/fail — automated analysis of job results frames whether the variance is significant.

### CNG instance option

For testing against a full GitLab CNG instance instead of Docker Compose,
useful for testing GitLab-specific APIs:

- Set `RUN_ON_CNG: "true"` and provide `GITLAB_HELM_CHART_REF`
- Optional: use `DATA_SEEDER_FILE_NAME` for data seeding via the
  data-seeder framework (`ee/db/seeds/data_seeder/` in gitlab-org/gitlab)
- Uses larger GCP VM (`n2-standard-8`) — ~20-25 min setup vs ~2-5 min
  for Docker Compose

### What CPT tests

- Component throughput and response times (TTFB, RPS)
- Error handling performance
- Configuration-related performance impacts
- Regression detection at the MR level

### What CPT does NOT test

- Integration bottlenecks between components
- Production-scale data volume issues
- End-to-end system performance (use GPT for this)

## Future Tools (Not Yet Available)

The handbook outlines additional approaches under development:

- **Performance unit testing** — rspec-benchmark assertions in unit tests
  (e.g., `expect { method }.to perform_under(50).ms`)
- **Profiling tools** — ruby-prof, stackprof, memory_profiler for
  development-time analysis
- **Observability-based testing** — using production metrics to validate
  performance improvements

These are not part of GitLab Performance Toolkit yet. For current needs, use GPT, Sitespeed
Runway, or CPT.

## Need Help?

Contact **#g_performance_enablement** on Slack for:
- Help choosing the right tool
- Provisioning a dedicated performance environment
- CPT onboarding (alpha)
- Sitespeed Runway access
- Any performance testing question
