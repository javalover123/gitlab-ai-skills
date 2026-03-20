# Getting Started: Your First Performance Test

Guide for engineers new to performance testing. If you're already comfortable
with the tools, see the quick-reference via the main skill's routing table.

## Deciding What to Test

You've looked at the decision framework in the main skill and decided "yes,
write a test." Now: what *kind* of test, which tool, and what thresholds?

### Change type → tool and test type

| Change Type | Perf Test? | Tool | Test Type | Why |
|---|---|---|---|---|
| New user-facing API endpoint | Yes | GPT or custom k6 | Smoke + Baseline | Establish baseline before it reaches users |
| Changed SQL query on hot path | Yes | GPT or custom k6 | Baseline | N+1 or missing index shows up under load |
| Added external service call | Yes | GPT or custom k6 | Baseline + Stress | External calls add latency and failure modes |
| New background job (Sidekiq) | Yes | GPT or custom k6 | Smoke | Test the API that enqueues it, not the job itself |
| New page or major layout change | Yes | Sitespeed Runway | CWV budget | LCP, CLS regression check |
| Containerized component change | Yes | CPT | MR-level load | Faster feedback — catches regressions before merge |
| Increased `per_page` default | Yes | GPT or custom k6 | Baseline | More data = more serialization, DB, memory |
| Added authentication middleware | Yes | GPT or custom k6 | Baseline | Auth is on every request — small change, big impact |
| Config change (ENV var only) | No | - | - | Unless it changes code paths under load |
| Documentation / UI copy only | No | - | - | No runtime impact |
| Dependency version bump | Maybe | GPT or custom k6 | Smoke | Only if the dep is on the hot path |
| Database migration (add column) | Maybe | GPT or custom k6 | Baseline | If column is selected in hot queries |
| Behind feature flag | Yes | GPT or custom k6 | Smoke + Baseline | Feature flags don't reduce the need for a perf baseline |

### Choosing the right tool

- **API/backend load testing** → **GPT** (GitLab Performance Tool). GPT has
  pre-built tests for common GitLab endpoints and handles data generation,
  execution, and reporting. Runs externally via Docker.
- **Frontend page load / CWV** → **Sitespeed Runway**. Hosted service with
  Web UI and API. No local setup required.
- **Faster feedback in MR** → **CPT**. Runs in your MR pipeline.
  Runs against a Docker Compose or CNG GitLab instance. Currently in alpha.
- **Custom k6 test in your repo** → When GPT doesn't cover your endpoint or
  you need a test embedded in your project. Write k6 tests following the
  principles in quick-reference and the test samples in ptk-tools.md as templates.

For setup details and quick starts: see ptk-tools.md via the main skill's
routing table.

## Defining "Too Slow"

"Fast" is not a threshold. You need a number.

**Step 1:** Measure the current baseline (before your change):
- p50, p95, p99 response times
- Error rate
- Requests per second achieved

**Step 2:** Set a regression budget:

| Scenario Type | Default Budget | Rationale |
|---|---|---|
| Critical path (login, checkout) | 10% regression on p95 | User-facing, high sensitivity |
| Standard API endpoint | 20% regression on p95 | Reasonable tolerance |
| Background/async operations | 30% regression on p95 | Less user-visible |
| Frontend CWV (LCP, FCP) | Absolute: LCP < 2.5s, FCP < 1.8s | Google's "good" thresholds |
| Frontend CWV (CLS) | Absolute: CLS < 0.1 | Google's "good" threshold |

**Step 3:** Encode as k6 thresholds (for GPT or custom k6):

```javascript
// If baseline p95 is 200ms and budget is 20%:
thresholds: {
  'http_req_duration': ['p(95)<240'],  // 200ms * 1.2 = 240ms
}
```

**Absolute thresholds** (e.g., `p(95)<500`): Use when you have a defined SLO. Don't drift with baseline changes — preferred for CI.

**Relative thresholds** (e.g., "20% slower than last release"): Use when you don't have an SLO but want to detect regressions. Require comparing against stored baseline data — more complex to maintain.

For CI, absolute thresholds are simpler and more reliable. Store baseline
numbers in your test's `options.thresholds` and update them when you
intentionally accept a performance change. Document why in the commit message.

## Writing a Custom k6 Test

If GPT doesn't cover your endpoint, or you need a test embedded in your
project, you'll write a custom k6 test.

**Test data:** If your test writes data (comments, issues, etc.), use a
dedicated test project in your perf environment. Never target real projects —
test artifacts pollute real review threads and confuse other engineers.


## Frontend Testing with Sitespeed Runway

For pages and layout changes, use Sitespeed Runway to measure Core Web
Vitals. The quickest path:

1. Go to https://sitespeed.runway.gitlab.net/
2. Enter your page URL
3. Configure: Chrome, cable connectivity, 5 iterations
4. Compare results before/after your change

For automated testing via API or Docker, see ptk-tools.md via the main
skill's routing table.

## Adding to CI

**CPT for MR-level testing. GPT for scheduled load tests.**

- **CPT:** Add a multi-project pipeline trigger to your `.gitlab-ci.yml`.
  See ptk-tools.md for the CI config.
- **Custom k6 smoke test per MR:** Use the GitLab built-in template:

```yaml
include:
  template: Verify/Load-Performance-Testing.gitlab-ci.yml

load_performance:
  variables:
    K6_TEST_FILE: tests/performance/smoke.js
  rules:
    - if: $CI_MERGE_REQUEST_IID
  tags:
    - your-perf-runner-tag
```

For full pipeline examples including scheduled load tests, sitespeed.io jobs,
and runner setup, see the CI integration guide via the main skill's routing
table.

## Common Mistakes

| Mistake | Why It Matters | Fix |
|---|---|---|
| Testing against staging/production | Can take environment offline, breaks deployment pipeline | Dedicated perf environment only |
| Building from scratch instead of using GitLab Performance Toolkit | Duplicates existing tooling, no shared reporting | Use GPT, Sitespeed Runway, or CPT first |
| No thresholds defined | Test always passes, catches nothing | Add p95/p99 + `http_req_failed` thresholds |
| `check()` without threshold on checks | Checks don't affect k6 exit code | Add `'checks': ['rate>0.99']` |
| Duplicate threshold keys in `options` | JS silently drops duplicates | Use array: `['p(95)<500', 'p(99)<1000']` |
| Hardcoded URLs in test body | Test only works in one environment | Use `__ENV.BASE_URL` |
| `console.log` on every iteration | Serializes output, distorts timing | Log failures only |
| sitespeed.io without throttling | Results reflect network jitter | Always use `-c cable` or `-c 3g` |
| Running 1 iteration for timing data | High variance, unreliable | 5-11 runs for stable metrics |
| Only running tests once | Can't distinguish regression from noise | Run at least twice consecutively |

## Real-World Examples

### Adding pagination to project list API

**Change:** `/api/v4/projects` now supports `per_page` up to 100 (was 20).
**Decision:** Yes — more rows, more serialization, more memory.
**Tool:** GPT (if endpoint is in GPT's test suite) or custom k6.
**Test:** Baseline with varied `per_page` values (20, 50, 100).
**Threshold:** p95 should scale roughly linearly. If 100 is >5x slower than
20, investigate.

### Redesigned project dashboard page

**Change:** New layout with lazy-loaded components and updated JS bundle.
**Decision:** Yes — layout and bundle changes affect CWV.
**Tool:** Sitespeed Runway.
**Test:** Run before/after comparison in Runway Web UI, cable connectivity.
**Threshold:** LCP < 2.5s, CLS < 0.1.

### New Sidekiq job for email notifications

**Change:** Background job sends email when MR is approved.
**Decision:** Test the API endpoint that triggers the job, not the job
itself. If enqueueing adds measurable latency to the API response, that's a
problem.
**Tool:** GPT or custom k6.
**Test:** Smoke test on the approval API endpoint under moderate load.

### Registry service response time regression

**Change:** Updated image manifest parsing in the container registry.
**Decision:** Yes — registry is containerized and testable in isolation.
**Tool:** CPT (if adopted) — runs in MR pipeline against isolated registry.
**Test:** k6 load test against registry API endpoints via CPT.
