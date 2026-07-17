You want a **profiler**, not a load test. Load tests (GPT, k6, CPT) tell you *whether* an endpoint is slow under traffic; they add load, which is exactly what you're trying to avoid, and they won't point at the line of Ruby that's eating your time or allocating your memory. Profilers answer the "where" question by measuring a single request/code path. Since `gitlab-org/gitlab` ships these gems in the Gemfile already, you don't need to install anything.

You have two distinct symptoms, so use two tools.

## Fastest start if you have GDK / admin access: the Performance Bar

Before wiring up any code, try the Performance Bar against the URL. It can profile any request with **Stackprof** (CPU, rendered as a Speedscope flame graph) *and* run **memory_profiler** for the current URL, with no code changes. For `GET /api/v4/projects/:id/issues`, hit the endpoint with the bar enabled and read both reports. This is usually enough to localize the problem in minutes.

## For the "getting slower" symptom (CPU time) → Stackprof

Stackprof is a sampling call-stack profiler with low overhead. It shows which methods dominate.

- Profile a representative spec that exercises the endpoint:
  ```shell
  bin/rspec-stackprof --limit=10 spec/requests/api/issues_spec.rb
  ```
- Or wrap the code path directly:
  ```ruby
  StackProf.run(mode: :wall, out: 'tmp/issues.dump') do
    # the finder / serializer call the endpoint runs
  end
  ```
  Then read it with the `stackprof` CLI (`--flamegraph`, `--method`, or `--graphviz`).

Reading it: `SAMPLES` = self time (frame on top of the stack), `TOTAL` = self + everything it called. For a list endpoint like this, watch specifically for a query or serialization step that scales with the number of issues returned — the classic N+1 (a query per row) or a serializer that balloons with `per_page`.

## For the "memory climbing" symptom → memory_profiler

```ruby
require 'memory_profiler'
report = MemoryProfiler.report do
  # the endpoint's code path
end
report.pretty_print(File.open('/tmp/issues-mem.txt', 'w'))
```

It groups memory by gem / file / location / class. The key distinction:

- **Retained** = long-lived memory still held after the block. Use this to hunt the actual growth/leak you're seeing.
- **Allocated** = everything allocated during the block, even if freed. High allocated with low retained means you're making the GC work hard (a performance cost, not a leak).

For a request that's "climbing," look at **retained** first. GitLab's guideline: a web request should not allocate more than **100k objects or 100M bytes**. You can measure your own path against that budget with:
```ruby
Gitlab::Memory::Instrumentation.with_memory_allocations { ... }
# => { mem_objects:, mem_mallocs:, mem_bytes:, mem_total_bytes: }
```

## Suggested order

1. Run the Performance Bar on the URL (or Stackprof + memory_profiler around the code path) to localize.
2. If the heavy frame is a query loop, you've likely found an N+1 — confirm and fix, then re-profile.
3. Re-run after your fix and check the hottest frame actually shrank. If the top frame is only ~1% of total time, it's not worth optimizing — look elsewhere.

## Two notes

- Don't reach for GPT/k6/CPT here. Those are for detecting regressions under load, and per our shared-infra rules you'd never point them at staging or production anyway. Your task is investigation, which is local/dev profiling.
- If you later want a *guard* so this doesn't regress again after you fix it, `rspec-benchmark` (`perform_allocation`, `perform_under`, `perform_linear`) can assert allocations/time in the spec suite — but that's a follow-up, not part of finding the current problem.

Full profiler reference (Stackprof production mode via SIGUSR2, rbtrace for live heap dumps, derailed_benchmarks for boot memory, etc.) lives in the GitLab Performance Guidelines: https://docs.gitlab.com/development/performance/. If you get stuck or the profile points somewhere unexpected, **#g_performance_enablement** on Slack can help.
