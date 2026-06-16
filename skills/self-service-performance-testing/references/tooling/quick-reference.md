# k6 Test Quick Reference

Reference for writing and reviewing k6 performance tests. Applies to both
custom k6 tests and GPT test suites (GPT uses k6 under the hood).

**CPT is an exception** — it manages thresholds, execution, and result
interpretation itself. These principles apply to the k6 test files CPT runs,
but not to how CPT evaluates results. See cpt.md for CPT-specific conventions.

For common mistakes and the decision framework, see getting-started.md.

## Before Writing Any Test

Resolve these four questions — ask the engineer or infer from context:

1. **What user behavior is being tested?** Map to a scenario ("user opens MR
   with 500 comments"), not an endpoint ("GET /notes").
2. **What does "too slow" mean?** Arrive at a number: baseline measurement +
   regression budget. See getting-started.md for default budgets.
3. **What load profile?** Baseline (steady-state, default), stress (breaking
   point), spike (burst recovery), or smoke (single iteration).
4. **What environment constraints?** Containers, shared infra, CI runner
   limits. These determine whether stable, repeatable measurement is possible.

## Principles

- **Every test has thresholds.** A test without thresholds only proves the
  server responded. Use p95/p99 percentiles scoped per scenario. Include an
  error rate threshold (`http_req_failed rate < 1%`). Checks alone do NOT
  affect k6 exit codes — add `'checks': ['rate>0.99']` as a threshold.
- **Scenarios model users, not APIs.** Randomized think time. Varied resource
  IDs per iteration. Descriptive scenario names.
- **Measure accurately under load.** Prefer an arrival-rate executor (e.g., `constant-arrival-rate`).
  When using iteration-based executors, document the coordinated omission risk.
- **Isolate the measurement.** Setup/teardown outside the measurement window.
  Tag every request by purpose so auth overhead is filterable.
- **Keep the hot path clean.** `console.log` on every iteration distorts
  timing. Log failures only.
- **Externalize everything.** Test data in SharedArray. Credentials in CI
  variables. Target URL via `__ENV.BASE_URL`.
- **Run each test at least twice consecutively.** k6's official recommendation
  for identifying unreliable results.

## Pattern Guide

| Instead of | Prefer | Reason |
|---|---|---|
| No thresholds | p95/p99 per scenario + `http_req_failed` | Turns test into regression gate |
| Threshold on avg | Threshold on p95/p99 | Surfaces tail latency |
| Fixed `sleep(1)` | `sleep(randomIntBetween(1, 3))` | Models real users, prevents request sync |
| 1 VU "load test" | VU count matching load profile | Concurrency reveals contention |
| Auth measured in main loop | Tagged or in setup() | Focused measurement |
| Hardcoded base URL | `__ENV.BASE_URL` | Portable across environments |
| Same resource ID every iteration | Parameterized, varied IDs | Tests app, not cache |
| Duplicate threshold keys | Array of conditions on one key | JS objects silently drop duplicate keys |
| Copy-paste with one URL changed | Shared helpers, parameterized | One source of truth |

## Output Shape

When generating a k6 test stub, follow this structure:

- Filename: `<workflow_description>.js`
- `options` with thresholds and scenarios exported at top
- `setup()` for auth/seeding (outside measurement)
- Default function reads like a user story, top to bottom
- `check()` validates correctness; thresholds gate performance — keep these
  distinct
