# Finding where the time and memory go in `GET /api/v4/projects/:id/issues`

You want *profiling*, not load testing. The goal is to attribute the latency and the memory growth to specific code paths without piling extra traffic onto the endpoint. Here's how I'd approach it, from cheapest/fastest to deepest.

## 1. Start with the request-level breakdown you already have for free

GitLab emits structured logs and per-request instrumentation, so before reaching for a profiler, look at what's already recorded.

- **`api_json.log`** (in `log/api_json.log` locally, or Kibana in staging/prod): every API request logs `duration_s`, `db_duration_s`, `gitaly_duration_s`, `redis_duration_s`, `cpu_s`, plus SQL and Gitaly call *counts*. This alone usually tells you whether the regression is DB-bound, Gitaly-bound, or CPU/Ruby-bound. If `db_duration_s` and the query count jumped, you likely have an N+1 or a missing index. If `duration_s` climbed but the sub-durations didn't, the time is in Ruby (serialization, object allocation, etc.).
- **Correlation ID**: grab the `correlation_id` from a slow response header (`X-Request-Id` / `x-gitlab-meta`) and trace it across all the logs (`api_json`, `production_json`, Sidekiq if anything is enqueued).

This is the "where do I even look" step. Do it first — it scopes everything below.

## 2. Confirm/kill the N+1 and query-count hypothesis

Given the symptoms (slower *and* climbing memory as the request runs), an N+1 or an unbounded association load is the most common culprit for an issues-list endpoint.

- **Bullet gem** is enabled in GitLab's development environment — it flags N+1s and unused eager loads directly in the logs/UI. Hit the endpoint locally with a project that has a realistic number of issues.
- **`ActiveRecord` query log / `db_query_count`**: watch the query count as you vary the page size. If queries scale with the number of issues (or labels, assignees, milestones, notes) instead of being constant, that's your N+1. The fix is usually a `preload`/`includes` in the finder or a `Preloader`, or a change in the Grape entity that's lazily triggering per-record queries during serialization.
- Check the Grape **entity/serializer** (`Entities::Issue` and friends) — serialization is a frequent spot where a per-issue association is touched, generating one query per row and allocating a lot of intermediate objects.

## 3. Profile the Ruby side: CPU time and allocations

If the logs point at Ruby time or memory (not DB/Gitaly), profile the actual code.

- **`rack-mini-profiler`** is wired into GitLab's dev environment. Append `?pp=flamegraph` to the request for a flamegraph of where wall-clock time goes, or `?pp=help` for the other modes (`?pp=profile-memory`, SQL breakdown, etc.). This is the fastest way to see the hot call stack for a single request without adding load — it profiles the one request you make.
- **`stackprof`** for a sampling CPU profile of a single request or a benchmark harness — good for confirming the hot path that mini-profiler surfaces, and it produces a flamegraph you can attach to an issue/MR.
- **`memory_profiler`** (or `?pp=profile-memory` via mini-profiler) for the memory question specifically: it reports allocated vs. retained objects/bytes grouped by gem, file, and line. "Memory climbing during the request" almost always means large **allocations** — building a big array of AR objects, materializing all rows before paginating, or a serializer that dups strings per record. `memory_profiler` will name the exact line and class doing the allocating.
- **`derailed_benchmarks`** if you want a repeatable memory-over-time picture of the endpoint (`bundle exec derailed exec perf:mem_over_time` / `perf:objects`), driven by a single scripted request rather than real load.

## 4. Reproduce in isolation

To profile cleanly and iterate on a fix, drive the endpoint from a small harness instead of the running app:

- A Rails **runner/console** snippet that calls the finder (`IssuesFinder`) and renders the entity directly, wrapped in `Benchmark` + `stackprof`/`memory_profiler`. This removes middleware noise and lets you bisect: is the cost in the finder query, the preloading, or the serialization?
- Seed a project with a representative volume of issues (and labels/assignees/notes, since those drive association loading) so the profile reflects the slow case, not an empty DB.

## 5. If you need the production/staging picture

If it only reproduces at scale on staging/prod:

- **Kibana** for the aggregated `api_json` metrics (p95/p99 `duration_s`, `db_duration_s`, query counts) over time — this both confirms the regression window and lets you correlate it with a deploy/MR.
- GitLab runs a **continuous profiler**; if you have access, pull a CPU/heap profile for the endpoint from real traffic — that's the zero-added-load option.
- **Grafana/Prometheus** for the memory trend on the Puma workers serving `/api`, to distinguish per-request transient allocation from an actual leak (retained memory that doesn't come back after the request).

## Recommended order

1. Read `api_json.log` (or Kibana) for one slow request via its correlation ID -> decide DB vs Gitaly vs Ruby.
2. If DB: Bullet + query counts -> find the N+1, fix with preloading in the finder/entity.
3. If Ruby time: `rack-mini-profiler` flamegraph (`?pp=flamegraph`) -> find the hot stack.
4. If memory: `memory_profiler` / `?pp=profile-memory` -> find the allocating line, usually a materialized collection or the serializer.
5. Reproduce and iterate against a seeded project in a `stackprof`/`memory_profiler` harness.

All of the above profile a *single* request (or a scripted one), so you're not adding load to shared infrastructure. Keep any real load testing out of this investigation until you've got a candidate fix and want to confirm it holds under concurrency.

One thing to watch: "slower *and* memory climbing" together on a list endpoint is the classic signature of the collection being fully materialized before pagination/serialization, or an N+1 that both issues extra queries and allocates the extra objects. I'd bet on the finder or the Grape entity — that's where I'd point the profiler first.
