# Getting Started: Your First Performance Test

Guide for engineers new to performance testing. If you're already comfortable
with the tools, see quick-reference.md for k6 patterns or the individual
tool references (gpt.md, sitespeed-runway.md, cpt.md).

## Before You Start: Check for Existing Tests

Search before writing anything. Check `.gitlab-ci.yml` and `.gitlab/ci/**`
for references to `performance`, `component-performance-testing`,
`gitlab-performance-tool`, `sitespeed`, or `k6`. Also search for
`import.*k6` or `from 'k6'`. If tests exist, point the engineer to them —
don't write a new one.

## Decision Framework: Should I Write a Performance Test?

### Does This Change Need a Perf Test?

| Change Type | Perf Test? | Why |
|---|---|---|
| New user-facing API endpoint | Yes | Establish baseline before it reaches users |
| Changed SQL query on hot path | Yes | N+1 or missing index shows up under load |
| Added external service call | Yes | External calls add latency and failure modes |
| New background job (Sidekiq) | Yes | Test the API that enqueues it, not the job itself |
| New page or major layout change | Yes | LCP, CLS regression check |
| Containerized component change | Yes | Catches regressions before merge |
| Increased `per_page` default | Yes | More data = more serialization, DB, memory |
| Added authentication middleware | Yes | Auth is on every request — small change, big impact |
| Behind feature flag | Yes | Feature flags don't reduce the need for a perf baseline |
| Config change (ENV var only) | No | Unless it changes code paths under load |
| Documentation / UI copy only | No | No runtime impact |
| Dependency version bump | Maybe | Only if the dep is on the hot path |
| Database migration (add column) | Maybe | If column is selected in hot queries |

### Which Tool and Test Type?

| Change Type | Test Type | Tool |
|---|---|---|
| New API endpoint | Smoke + Baseline (target RPS, 5 min) | GPT or custom k6 |
| Critical path change | Baseline (target RPS, 5-10 min) | GPT or custom k6 |
| Scaling concern | Stress (ramp to 2-3x normal) | GPT or custom k6 |
| Incident follow-up | Spike (sudden burst) | Custom k6 |
| Containerized component change | MR-level load test | CPT |
| MR-level feedback against a GitLab instance | MR-level load test | CPT |
| New page or layout change | CWV budget check | Sitespeed Runway |

**Choosing between the tools:**

- **API/backend load testing** → **GPT**. Pre-built tests for common GitLab
  endpoints, handles data generation, execution, and reporting. See gpt.md.
- **Frontend page load / CWV** → **Sitespeed Runway**. Hosted service with
  Web UI and API. No local setup required. See sitespeed-runway.md.
- **Faster feedback in MR** → **CPT**. Runs in your MR pipeline against a
  Docker Compose or CNG GitLab instance. Currently in alpha. See cpt.md.
- **Custom k6 test in your repo** → When GPT doesn't cover the endpoint or
  the engineer needs a test embedded in their project. See quick-reference.md.

## Defining "Too Slow"

**CPT exception:** If the engineer is using CPT, skip this section. CPT test
files include `TTFB_THRESHOLD` and `RPS_THRESHOLD` as reference values, but
CPT runs with `--no-thresholds` and uses variance analysis rather than
pass/fail gates — don't walk the engineer through the baseline + budget
workflow below. See cpt.md for the constants and how CPT evaluates results.

**Sitespeed Runway exception:** If the engineer is using Sitespeed Runway,
the relevant metrics are Core Web Vitals (LCP, FCP, CLS). Skip Step 1 and
go straight to Step 2 — use the CWV budget rows.
See sitespeed-runway.md for how to configure and interpret results.

"Fast" is not a threshold. You need a number.

**Step 1:** Measure the current baseline (before the change):
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

**Absolute thresholds** (e.g., `p(95)<500`): Use when there's a defined SLO.
Preferred for CI — they don't drift with baseline changes.

**Relative thresholds** (e.g., "20% slower than last release"): Use when
there's no SLO but regression detection is needed. Require comparing against
stored baseline data — more complex to maintain.

For CI, absolute thresholds are simpler and more reliable. Store baseline
numbers in the test's `options.thresholds` and update them when intentionally
accepting a performance change. Document why in the commit message.

## Common Mistakes

| Mistake | Why It Matters | Fix |
|---|---|---|
| Testing against staging/production | Can take environment offline, breaks deployment pipeline | Dedicated perf environment only |
| Building from scratch instead of using the toolkit | Duplicates existing tooling, no shared reporting | Use GPT, Sitespeed Runway, or CPT first |
| No thresholds defined (GPT/k6) | Test always passes, catches nothing | Add p95/p99 + `http_req_failed` thresholds |
| `check()` without threshold on checks (GPT/k6) | Checks don't affect k6 exit code | Add `'checks': ['rate>0.99']` |
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
**Tool:** CPT — runs in MR pipeline against isolated registry.
**Test:** k6 load test against registry API endpoints via CPT.
