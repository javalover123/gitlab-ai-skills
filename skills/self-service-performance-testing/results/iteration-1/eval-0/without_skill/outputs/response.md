Short answer: yes, this is a good candidate for a performance test, and more importantly it's a change I'd want to look at carefully before it ships. Adding a join on a high-traffic list endpoint is one of the classic ways a subtle regression slips into production.

Here's how I'd think about it.

## Why this change is risky

A few things stack up against you here:

- **It's a list endpoint.** List/index endpoints return many rows, so any per-row cost or any join that isn't backed by a good index gets multiplied. A query that's fine for a single MR can fall over when returning a page of 20-100.
- **It's hot.** "Gets hit a lot" means even a small per-request slowdown becomes a large aggregate load increase on the database, and it's exactly where a regression is most visible to users and most expensive in DB CPU.
- **Joins can silently change row counts.** If the join isn't strictly 1:1 (e.g. an MR can have multiple approval rows), you can get row multiplication or need a `DISTINCT`/`GROUP BY` that changes the plan entirely. Worth double-checking the cardinality of the approval relationship.

## What I'd actually check, in order

1. **Look at the query plan first.** Before writing any test, run `EXPLAIN (ANALYZE, BUFFERS)` on the new query against a realistic dataset. This is the fastest way to catch the real problems:
   - Is the join using an index, or is it a seq scan / nested loop over a big table?
   - Did adding the join change the plan for the *rest* of the query (sometimes the planner flips strategies)?
   - What do the buffer numbers look like vs. the old query?
   
   If you're on GitLab, run the query through the Database Lab / `postgres.ai` bot in the MR or via ChatOps — it runs against a production-clone dataset and gives you timing + plan on realistic data volumes, which is far more trustworthy than your local dev DB. This alone will catch most regressions.

2. **Confirm the indexes exist.** The columns you're joining on (and any new filter columns) need supporting indexes. If you're adding a join to the approvals table, make sure the FK / join column is indexed. If not, that's a migration to add alongside this change.

3. **Check the N+1 angle.** Make sure you actually folded the approval data into the single query and didn't accidentally introduce a per-MR lookup in the serializer/entity layer. GitLab has request-level query counting (the `QueryRecorder` / query limit specs) that will catch this. If there's an existing spec asserting a query count for this endpoint, your join may change that count and you'll need to update it consciously (make sure the new count is *lower or equal*, not just "make the test pass").

## The actual performance test

For regression detection, you have a couple of levels:

- **Cheap and in-CI (do this):** a `QueryRecorder`-style spec that asserts the endpoint issues a bounded number of queries and doesn't scale with the number of MRs returned. This is the highest-value guard against the N+1 class of regression and it runs on every pipeline. If GitLab already has one for this endpoint, extend it; if not, adding one is low effort.

- **Load test (do this if the plan looks marginal or the endpoint is genuinely critical):** a proper load test against staging/a perf environment to measure p95/p99 latency and throughput under concurrency, comparing before vs. after your change. This is where you'd catch a regression that only shows up under real traffic and connection contention. GitLab runs the GPT (GitLab Performance Tool, k6-based) against reference environments; if this endpoint is in the covered API set, your change will get exercised there. If it's a critical endpoint not currently covered, it may be worth adding a scenario.

## My recommendation

1. Run `EXPLAIN (ANALYZE, BUFFERS)` on a production-sized dataset (Database Lab) **now** — this is non-negotiable for a join on a hot list endpoint and takes a few minutes.
2. Verify indexes back the join; add a migration if needed.
3. Add or update a query-count spec so a future N+1 can't creep back in.
4. Only reach for a full load test if the plan is borderline, the row cardinality is non-trivial, or this endpoint is critical enough to warrant it.

One important caution on load testing: **don't point ad-hoc load tests at production**, and coordinate before hitting shared staging/perf environments — a load test is a self-inflicted mini-DDoS and can disrupt other people's work. Use the designated performance environment and tooling.

If you paste the query (or the before/after `EXPLAIN` output) I can help you read the plan and tell you whether the join is safe or whether it needs an index.
