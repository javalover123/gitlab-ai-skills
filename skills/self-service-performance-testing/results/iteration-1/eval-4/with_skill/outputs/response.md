Short answer: probably not a new test. You've already found the two things that matter, and they point to a test that most likely already covers your endpoint. Confirm it, then either add a case or just make sure it runs.

## What you've actually found

That `.gitlab-ci.yml` block isn't a generic performance job — it's a **CPT (Component Performance Testing)** trigger. CPT is GitLab's Performance Enablement tool that runs load tests *inside your MR pipeline* via a multi-project pipeline against the `gitlab-org/quality/component-performance-testing` project. It's the only toolkit tool that runs in your repo's CI rather than an external system. (Heads up: CPT is currently **alpha** — worth a note to `#g_performance_enablement` on Slack before leaning on it heavily, but it's the right fit here.)

The `TEST_FILE_LOCATION: "qa/performance_test/k6_test"` variable tells CPT where to find its k6 test files. And you've spotted `qa/performance_test/k6_test/group_merge_requests.js` sitting right there — which, by name, is almost certainly a test for exactly the endpoint you want to cover: `GET /api/v4/groups/:id/merge_requests`.

## So: don't write a new one yet

Before writing anything, the right move is to open `group_merge_requests.js` and confirm what it hits. Specifically check:

- **What request(s) it makes** in the `default` function — is it calling `GET /api/v4/groups/:id/merge_requests`? If yes, your endpoint is already under test.
- **The exported constants** — CPT tests must export `TEST_NAME`, `TTFB_THRESHOLD` (p90 TTFB in ms), and `RPS_THRESHOLD` (min requests/sec). It also reads optional `LOAD_TEST_VUS` / `LOAD_TEST_DURATION` and a warmup scenario. If those are present, it's a valid CPT test and is wired into the pipeline you found.

If the file already exercises the endpoint, you're done — the coverage exists and runs on your MR. Writing a second test file for the same endpoint just duplicates it and muddies the MR report.

## When you *would* touch it

There are a couple of cases where the existing file isn't enough, but even then you're **editing**, not creating new:

- **You're changing the endpoint's behavior** (new filter param, a JOIN, a `per_page` bump, an added query). Then extend `group_merge_requests.js` to exercise the new path — e.g. add a request variant hitting the new parameter — so the report reflects your change. Note that CPT does a code-path analysis and will tell you whether your MR's changed code actually intersects the tested endpoint, which helps confirm the test is meaningful for your diff.
- **The file tests something adjacent but not your specific query shape.** Add a case there rather than a new file.

One thing you don't need to sweat: CPT runs `k6 run --no-thresholds` and reports **variance**, not pass/fail. The `TTFB_THRESHOLD` / `RPS_THRESHOLD` constants are reference values, not gates. So you do *not* need to go measure a baseline and set a 20% regression budget the way you would for a standalone GPT/k6 test — CPT's automated analysis frames whether the variance on your MR is significant and posts it as an MR comment.

## Concrete next steps

1. Read `qa/performance_test/k6_test/group_merge_requests.js` and confirm it calls `GET /api/v4/groups/:id/merge_requests`.
2. If it does and your change doesn't alter the query shape: no new test — just make sure the `tests:performance` job runs on your MR and review its comment.
3. If your change adds a param/query path: add a request variant to the existing file (keep the exported constants and warmup/load scenario structure intact).
4. If anything about the CPT setup is unclear or it's misbehaving (it's alpha), ask in **#g_performance_enablement** on Slack.

For reference on CPT conventions and the test file structure: https://gitlab.com/gitlab-org/quality/component-performance-testing and the live examples at https://gitlab.com/gitlab-org/gitlab/-/tree/master/qa/performance_test/k6_test.

One safety note since it always applies: don't point any k6 run at staging or production — CPT sidesteps this by provisioning its own isolated instance, which is exactly why you want to run through it rather than hand-rolling a test against a shared environment.
