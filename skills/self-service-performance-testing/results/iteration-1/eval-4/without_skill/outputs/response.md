Short answer: **No, don't write a new test.** A CPT test already exists for exactly this endpoint. Run the existing one and compare against its baseline. Only touch the file if the existing test is genuinely missing coverage for what your change affects.

Here's the reasoning and what to do.

## What your CI config actually is

That `tests:performance` job isn't a generic k6 runner. It's a trigger for **CPT (Component Performance Testing)** — one of GitLab's Performance Testing Kit tools. The `trigger.project: gitlab-org/quality/component-performance-testing` with `strategy: depend` fires a multi-project pipeline: CPT provisions GCP VMs, deploys your component, runs the k6 files it finds under `TEST_FILE_LOCATION` (`qa/performance_test/k6_test`), and posts a results table as a comment on your MR. `COMPONENT_SERVICE_NAME: "gitlab"` tells it which service to stand up.

Because CPT runs in your MR pipeline against a provisioned, isolated environment, you get MR-level regression detection without touching staging or production — which is the rule (never run perf tests against shared staging/production; they can take the environment offline and block every team's deploys).

## The endpoint you named is already covered

`qa/performance_test/k6_test/group_merge_requests.js` is a CPT test for `GET /api/v4/groups/:id/merge_requests` — the exact endpoint you want to test. I read it. It already:

- Resolves the group dynamically in `setup()` (searches for "Test Seed Group" by name, falls back to group ID 1) rather than hardcoding an ID — good practice, survives environment reseeding.
- Uses the CPT conventions correctly: exports `TEST_NAME`, `TTFB_THRESHOLD` (25ms p90), `RPS_THRESHOLD` (2), plus warmup + `load_test` scenarios on `constant-vus`, with thresholds scoped to `{scenario:load_test}` and `abortOnFail: false` (CPT owns pass/fail).
- Runs a `GET` and `check()`s status 200 / array response / non-empty.

So the correct move for adding "performance coverage" to this endpoint is: **run the pipeline, let CPT execute this test, and compare the TTFB/RPS numbers against the stored baseline** (CPT compares against historical data in the GitLab Package Registry with statistical significance if a baseline exists). If there's no baseline yet, run it at least twice to establish one — single perf runs are noisy and not trustworthy.

## When you *should* edit the existing file (not create a new one)

Modify `group_merge_requests.js` — don't add a parallel file — if your change means the current test no longer exercises the risky path. Common reasons:

- **You added a query parameter or filter** (e.g. `state`, `scope`, `labels`, `author_id`, `milestone`) that changes the query plan or introduces N+1 risk. The current test hits the bare endpoint with no filters, so it won't catch a regression in a filtered path. Add a request (or parameterize) to cover the filter combination your change touches.
- **The threshold is now wrong.** `TTFB_THRESHOLD = 25` (ms, p90) is quite tight and is only meaningful relative to a baseline on CPT's environment. If your change legitimately shifts the baseline, update the constant — but base it on measured numbers + a regression budget (default ~20%), not a guess. "Fast" is not a threshold; a number is.
- **The test data doesn't represent your scenario.** It resolves one seed group. If your change matters at scale (a group with thousands of MRs, deep subgroup hierarchies), the seed data needs to reflect that or the test proves nothing. For realistic volume, that's a data-seeding concern — CPT supports a CNG instance with `DATA_SEEDER_FILE_NAME` (`ee/db/seeds/data_seeder/`).

If none of those apply — your change is on a path the existing test already drives — then no code change at all. Just run it and read the MR comment.

## Two small quality notes if you do edit it

- `console.log` runs on **every iteration** here. In CPT that's tolerated (it's used for CPT's own reporting), but be aware per-iteration logging distorts timing under load; keep it to failures if you extend the hot path.
- Keep `check()` (correctness) and thresholds (the performance gate) distinct — the file already does this correctly.

## Bottom line

1. Don't write a new test — CPT already has one for this endpoint.
2. Run the pipeline; let CPT run `group_merge_requests.js` and post its comparison.
3. Only edit the existing file if your change introduces a path/filter/data-shape the current test doesn't exercise — and set any new threshold from measured numbers, not intuition.
4. CPT is **alpha** — if you hit setup issues, baseline questions, or want help sizing the load, ask in **#g_performance_enablement** on Slack.
