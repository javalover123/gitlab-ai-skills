# Performance Test Quick Reference

Expert reference for writing and reviewing k6 performance tests. Applies to
both custom k6 tests and GPT test suites (GPT uses k6 under the hood). If
you need the guided walkthrough instead, see the getting-started guide via
the main skill's routing table.

## Before Writing Any Test

Resolve these four questions - ask or infer from context:

1. **What user behavior is being tested?** Map to a scenario ("user opens MR
   with 500 comments"), not an endpoint ("GET /notes").
2. **What does "too slow" mean?** Arrive at a number: baseline measurement +
   regression budget (default 20%). Push until there's a threshold. "Fast" is
   not a threshold.
3. **What load profile?** Baseline (steady-state, regression detection - use
   this as default), stress (breaking point), spike (burst recovery), or smoke
   (single iteration).
4. **What environment constraints?** Containers, shared infra, CI runner
   limits - these determine whether stable, repeatable measurement is
   achievable. **Never staging. Never production.**

## Principles

Apply these regardless of framework:

- **Every test has thresholds.** A test with thresholds is a quality gate. A
  test without thresholds only proves the server responded. Use p95/p99
  percentiles scoped per scenario. Include an error rate threshold
  (`http_req_failed rate < 1%`). Checks alone do NOT affect k6 exit codes -
  add `'checks': ['rate>0.99']` as a threshold or they are purely
  informational.
- **Scenarios model users, not APIs.** Randomized think time. Varied resource
  IDs per iteration. Descriptive scenario names.
- **Measure accurately under load.** Prefer arrival-rate executors
  (`constant-arrival-rate` in k6). When using iteration-based executors,
  document the coordinated omission risk.
- **Isolate the measurement.** Setup/teardown outside the measurement window.
  Tag every request by purpose so auth overhead is filterable.
- **Respect the execution model.** VU isolation means only setup() return data
  survives into default() - see the k6 patterns guide via the main skill's
  routing table.
- **Keep the hot path clean.** console.log on every iteration distorts timing.
  Log failures only.
- **Externalize everything.** Test data in SharedArray. Credentials in CI
  variables. Target URL via `__ENV.BASE_URL`.
- **Run each test at least twice consecutively.** k6's official recommendation
  for identifying unreliable results. Ignore runs with anomalous variance.

## Pattern Guide

When reviewing or generating tests, guide toward the stronger pattern:

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
| `check()` without threshold on checks | Add `'checks': ['rate>0.99']` | Checks alone don't fail k6 |
| Copy-paste with one URL changed | Shared helpers, parameterized | One source of truth |

## Output Shape

- Filename: `<workflow_description>.js`
- `options` with thresholds and scenarios exported at top
- `setup()` for auth/seeding (outside measurement)
- Default function reads like a user story, top to bottom
- `check()` validates correctness; thresholds gate performance - keep these distinct

## Common Traps

| Trap | Why | Fix |
|---|---|---|
| `check()` without threshold | Checks don't affect k6 exit code | Add `'checks': ['rate>0.99']` |
| Duplicate threshold keys in `options` | JS silently drops duplicates | Use array: `['p(95)<500', 'p(99)<1000']` |
| Testing against staging/production | Can take environment offline | Dedicated perf environment only |
| `console.log` on every iteration | Serializes output, distorts timing | Log failures only |

## Deeper Reference

For k6 patterns, CI integration, or sitespeed.io guides, see the main
skill's routing table.
