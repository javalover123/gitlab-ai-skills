Short answer: yes, this is exactly the kind of change that warrants a perf test. A new JOIN on the MR list endpoint is a classic regression vector — an approvals join can turn into N+1 queries or a full scan if the join columns aren't indexed, and because it's a high-traffic list endpoint, any per-row cost gets multiplied under load. A changed SQL query on a hot path is a clear "yes" in our decision framework, so I wouldn't skip it here.

That said, a couple of things could lower the urgency, and you know your context better than I do:

- If it's behind a feature flag, that doesn't remove the need for a baseline (the flag will roll out eventually), but it does buy you time.
- If you've already confirmed the join is on indexed columns and eyeballed the query plan (EXPLAIN ANALYZE) with no N+1, that's most of the risk retired. A quick check there is worth doing regardless.

A couple of quick sanity checks before writing anything new:

1. Confirm this isn't already covered. There are existing CPT k6 tests for MR endpoints in `gitlab-org/gitlab` at `qa/performance_test/k6_test/` (e.g. `group_merge_requests.js`, `project_merge_requests.js`). If the MR list endpoint you touched is already in there, you may just need to make sure that test runs on your MR rather than authoring a new one. Worth grepping `.gitlab/ci/**` for existing performance/CPT/k6 wiring too.
2. Verify the query plan locally as noted above — cheap and often decisive.

On tooling — since you want feedback on a specific MR touching a GitLab API, CPT (Component Performance Testing) is the tightest loop. It runs in your MR pipeline via a multi-project trigger and posts a comment showing TTFB/RPS variance for the endpoint, plus a code-path analysis that flags whether your changed code actually intersects the endpoint under test (so you don't get false alarms). For MR-list you'd use its CNG instance option (`RUN_ON_CNG=true`) since it needs a real GitLab instance with seeded data. Note CPT is currently in alpha, so ping #g_performance_enablement before adopting it — they'll help you get set up.

If you'd rather have a broader, scheduled load test against a reference architecture instead of per-MR feedback, GPT (the GitLab Performance Tool) is the other option, and MR-list endpoints are likely already in its suite.

Important guardrail either way: do not run these against staging or production. A load test can take an environment down, and staging going down blocks every team's merges. Use CPT's isolated/CNG setup or a dedicated perf environment — nothing shared.

On thresholds: the MR list is a standard (arguably critical, given the traffic) API endpoint, so measure the current p95 as your baseline and budget ~20% regression on p95 (tighten to 10% if you consider it truly critical-path). With CPT specifically you don't wire up pass/fail thresholds the same way — it reports variance and does the significance analysis for you, so you mainly care that the test exercises the endpoint with representative data.

Want me to sketch a CPT k6 test stub for the MR list endpoint, or help you check whether the existing MR-endpoint tests already cover your change? Happy to do either. And #g_performance_enablement on Slack is the place for anything beyond this.
