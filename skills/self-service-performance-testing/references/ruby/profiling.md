# Profiling Ruby Code in GitLab

When a test, request, or worker is slow and you need to find **where** the
time is going, you need a profiler — not a load test. This reference covers
the profilers shipped in the `gitlab-org/gitlab` Gemfile, when to reach for
each, and how to invoke them.

**Canonical sources** (rules and snippets below are taken from these):

- [GitLab Performance Testing Tool Selection Guide — Profiling Tools](https://handbook.gitlab.com/handbook/engineering/testing/performance-tools/#profiling-tools) — the handbook's inventory of the profilers GitLab uses
- [GitLab Performance Guidelines](https://docs.gitlab.com/development/performance/) — the docs page that contains the verbatim quotes, env var defaults, the memory budget, the rbtrace and benchmark-ips guidance, and the "Importance of Changes" section
- [GitLab Profiling docs](https://docs.gitlab.com/development/profiling/) — the Speedscope flamegraph workflow

The handbook lists the profilers; the operational detail (quotes, env
vars, code samples) lives in the `development/performance/` docs page.
`rbtrace` below is not in the handbook list but is documented in the
performance docs as `#rbtrace`; it's included here because it's the
go-to tool for live heap inspection.

## Decision Table: Which Profiler For Which Symptom?

| Symptom | Tool | What it shows |
|---|---|---|
| "This endpoint / spec is slow" — CPU-bound suspected | **Stackprof** | Sampled call stacks; which methods dominate CPU time |
| "Memory keeps growing" / "objects piling up" | **memory_profiler** | Retained vs allocated memory and objects, grouped by gem / file / location / class |
| "App boot is slow" or "Memory at boot is high" | **derailed_benchmarks** | Boot-time memory, per-dependency memory cost, full app perf under Rack |
| "Need to compare two versions of one method" | **benchmark-ips** | Iterations per second of each variant |
| "Ruby heap looks fragmented" / hunting memory leaks | **rbtrace** + heap viz | Live heap dump from a running process |
| "Want to profile a live production process" | **Stackprof in production** (SIGUSR2) or **rbspy** | Sampling profiler attached to a running PID |
| "Which spec files are slowest in the suite" | **rspec_profiling** | CSV of timing/query count/request count per spec |

For the four matcher-style **assertions** (`perform_under`, `perform_allocation`,
`perform_linear`, `perform_at_least`), use **rspec-benchmark** — see
[unit-performance-testing.md](unit-performance-testing.md). That's a perf
*test* gem; this page covers *investigation* tools.

## Profiling Bedrock Principle

> *"Profiling an application alters its performance. Different profiling
> strategies have different overheads. Stackprof is a sampling profiler.
> It samples stack traces from running threads at a configurable frequency
> (for example, 100 hz, that is 100 stacks per second). This type of
> profiling has quite a low (albeit non-zero) overhead and is generally
> considered to be safe for production."*
>
> *"A profiler can be a very useful tool during development, even if it
> does run in an unrepresentative environment. In particular, a method
> is not necessarily troublesome just because it's executed many times,
> or takes a long time to execute. Profiles are tools you can use to
> better understand what is happening in an application — using that
> information wisely is up to you!"*

— [Performance Guidelines, Profiling with Stackprof](https://docs.gitlab.com/development/performance/#profiling-with-stackprof)

---

## 1. Stackprof (CPU profiler)

**Repo:** https://github.com/tmm1/stackprof — included in the `gitlab-org/gitlab` Gemfile.
**Type:** Sampling call-stack profiler.
**When:** Something is CPU-bound or you want to see "where is time going" in a request, spec, or worker.

### Profile a code block

```ruby
StackProf.run(mode: :wall, out: 'tmp/stackprof-profiling.dump') do
  # code under investigation
end
```

This produces a `.dump` file. Read it with the `stackprof` CLI.

### Profile a spec

```shell
bin/rspec-stackprof --limit=10 spec/policies/project_policy_spec.rb
```

Sample output (excerpt from official docs):

```
==================================
 Mode: wall(1000)
 Samples: 17033 (5.59% miss rate)
 GC: 1901 (11.16%)
==================================
    TOTAL    (pct)     SAMPLES    (pct)     FRAME
     6000  (35.2%)        2566  (15.1%)     Sprockets::Cache::FileStore#get
     2018  (11.8%)         888   (5.2%)     ActiveRecord::ConnectionAdapters::PostgreSQLAdapter#exec_no_cache
     ...
```

`SAMPLES` = times this frame was on top of the stack (self time).
`TOTAL` = times this frame appeared anywhere in the stack (self + callees).

Pass any RSpec args to limit the run: `bin/rspec-stackprof --limit=10 spec/path:42`.

### Reading a Stackprof profile

Generate a graphviz call graph:

```shell
stackprof tmp/project_policy_spec.rb.dump --graphviz > project_policy_spec.dot
dot -Tsvg project_policy_spec.dot > project_policy_spec.svg
```

Generate a flame graph (requires `--raw=true` when dumping):

```shell
stackprof --flamegraph tmp/group_member_policy_spec.rb.dump > group_member_policy_spec.flame
stackprof --flamegraph-viewer=group_member_policy_spec.flame
```

Inspect a specific method:

```shell
stackprof tmp/project_policy_spec.rb.dump --method access_allowed_to
```

### Stackprof in production

GitLab supports Stackprof-on-SIGUSR2 in production. Set:

| Env var | Default | What it does |
|---|---|---|
| `STACKPROF_ENABLED` | `false` | Master switch — installs SIGUSR2 handler |
| `STACKPROF_MODE` | `cpu` | `cpu`, `wall`, or `object` (see [sampling modes](https://github.com/tmm1/stackprof#sampling)) |
| `STACKPROF_INTERVAL` | `10100` μs for cpu mode (≈99 Hz) | Sampling interval |
| `STACKPROF_FILE_PREFIX` | `$TMPDIR` | Output directory |
| `STACKPROF_TIMEOUT_S` | `30` | Auto-stop after this many seconds |
| `STACKPROF_RAW` | `true` | Collect raw samples (needed for flame graphs) |

Trigger with `kill -SIGUSR2 <pid>`. Profile is written to
`$STACKPROF_FILE_PREFIX/stackprof.$PID.$RAND.profile`. Supported targets:
**Puma workers** and **Sidekiq**. The Puma master treats SIGUSR2 as
restart — use `pkill -USR2 puma:` (note the colon) to target only workers.

---

## 2. memory_profiler (memory + allocation profiler)

**Repo:** https://github.com/SamSaffron/memory_profiler — in the `gitlab-org/gitlab` Gemfile.
**When:** Memory growing unexpectedly, want to see retained vs allocated bytes/objects.
**Also available:** via the [Performance Bar](https://docs.gitlab.com/administration/monitoring/performance/performance_bar/) for the current URL.

```ruby
require 'memory_profiler'

report = MemoryProfiler.report do
  # Code you want to profile
end

output = File.open('/tmp/profile.txt', 'w')
report.pretty_print(output)
```

The report groups retained and allocated memory by **gem**, **file**,
**location**, and **class**, and performs string analysis showing how often
each string is allocated and retained.

### Retained vs Allocated — the key distinction

> *"Retained memory: long-lived memory use and object count retained due to
> the execution of the code block. This has a direct impact on memory and
> the garbage collector.*
>
> *Allocated memory: all object allocation and memory allocation during the
> code block. This might have minimal impact on memory, but substantial
> impact on performance. The more objects you allocate, the more work is
> being done and the slower the application is."*
>
> *"As a general rule, retained is always smaller than or equal to allocated."*

— [Performance Guidelines, Retained versus allocated](https://docs.gitlab.com/development/performance/#retained-versus-allocated)

Use **retained** to find memory leaks and per-request memory growth.
Use **allocated** to find code that's just making the GC work hard.

### Memory allocation budget for web requests

> *"It is advised that web server requests do not allocate more than
> 100k mem_objects and 100M mem_bytes."*

— [Performance Guidelines, Memory allocations](https://docs.gitlab.com/development/performance/#memory-allocations)

You can measure these counters in your own code with
`Gitlab::Memory::Instrumentation.with_memory_allocations { ... }`, which
returns `{ mem_objects:, mem_mallocs:, mem_bytes:, mem_total_bytes: }`.
See [`lib/gitlab/memory/instrumentation.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/memory/instrumentation.rb)
for the implementation.

---

## 3. derailed_benchmarks (boot/memory benchmark for Rails apps)

**Repo:** https://github.com/zombocom/derailed_benchmarks — in the `gitlab-org/gitlab` Gemfile.
**When:** App boot is slow or memory at boot is concerning; you want to
attribute memory use to specific gems; or you want full-app benchmarks
under Rack.

Runs in CI as a job called **`memory-on-boot`** in every pipeline that has
a `test` stage. Results surface:

- On the MR **Overview** tab in the **Metrics Reports** dropdown
- In the `memory-on-boot` job artifacts (full report + dependency breakdown)

To run locally:

```shell
bundle exec derailed exec perf:mem
```

Other modes (each boots the app in `production` env and benchmarks under
Rack) are documented in the [gem README](https://github.com/zombocom/derailed_benchmarks#running-derailed-exec).
In GDK, follow the gem's "Running in production locally" instructions and
GDK has `production` sections configured out of the box.

---

## 4. benchmark-ips (block iterations/sec benchmark)

**Repo:** https://github.com/evanphx/benchmark-ips — in the Gemfile.
**When:** You want to compare two implementations of the same logic.

> *"When writing benchmarks you should almost always use benchmark-ips.
> Ruby's Benchmark module that comes with the standard library is rarely
> useful as it runs either a single iteration (when using Benchmark.bm)
> or two iterations (when using Benchmark.bmbm). Running this few
> iterations means external factors, such as a video streaming in the
> background, can very easily skew the benchmark statistics."*
>
> *"The benchmark-ips gem takes care of all this and much more. You
> should therefore use it instead of the Benchmark module."*

— [Performance Guidelines, Benchmarks](https://docs.gitlab.com/development/performance/#benchmarks)

The official guidance is unusually blunt about how to interpret results:

> *"Don't trust benchmarks you find on the internet."*
> *"Never make claims based on just benchmarks, always measure in production
> to confirm your findings."*
> *"X being N times faster than Y is meaningless if you don't know what
> impact it has on your production environment."*

Companion gem **`benchmark-memory`** ([repo](https://github.com/michaelherold/benchmark-memory))
is also in the Gemfile — same API as `benchmark-ips` but reports memory
size, objects, and strings allocated/retained instead of iterations/sec.

---

## 5. rbtrace (live process inspection + heap dump)

**Repo:** https://github.com/tmm1/rbtrace — in the `gitlab-org/gitlab` Gemfile.
**When:** Process is running and you can't restart it — need to inspect its
state. Most commonly used to dump the live Ruby heap for fragmentation
analysis.

Enable by setting `ENABLE_RBTRACE=1` when starting the web server or Sidekiq.
Then from another shell:

```shell
bundle exec rbtrace -p <PID> -e 'File.open("heap.json", "wb") { |t| ObjectSpace.dump_all(output: t) }'
```

Render a heap visualization with [Aaron Patterson's heapviz script](https://gist.github.com/tenderlove/f28373d56fdd03d8b514af7191611b88):

```shell
ruby heapviz.rb heap.json
```

See [Performance Guidelines — Rbtrace](https://docs.gitlab.com/development/performance/#rbtrace)
for the full procedure and an example fragmented heap image.

---

## 6. rbspy (sampling profiler for live Ruby processes)

**Site:** https://rbspy.github.io
**When:** You need to profile a Ruby process running in production or
locally without modifying its code. Unlike Stackprof, rbspy runs as an
external command.

GitLab's [Sidekiq troubleshooting documentation](https://docs.gitlab.com/administration/sidekiq/sidekiq_troubleshooting/#ruby-profiling-with-rbspy)
covers the production usage pattern for profiling Sidekiq workers.

---

## 7. ruby-prof (deterministic profiler)

**Repo:** https://github.com/ruby-prof/ruby-prof — listed in the
[handbook profiling tools](https://handbook.gitlab.com/handbook/engineering/testing/performance-tools/#profiling-tools).
**When:** You want exact call counts (not samples) for every method. Higher
overhead than Stackprof — usually you should reach for Stackprof first.

---

## 8. rspec_profiling (which specs are slow)

**Repo:** https://github.com/foraker/rspec_profiling — in the Gemfile.
**When:** The test suite itself is slow, or you want to see how an
individual spec's performance has changed over time.

Activate locally:

```shell
export RSPEC_PROFILING=yes
```

This creates timestamped CSVs in `rspec/profiling/` recording per-spec
timing, query count, query time, request count, request time, and feature
category. Set `RSPEC_PROFILING_FOLDER_PATH` to change the directory.

All test execution metrics are also exported to a ClickHouse instance and
visualized in the [Test Runtime Overview dashboard](https://dashboards.gitlab.net/d/dx-test-file-runtime-overview/dx3a-test-file-runtime-overview)
(GitLab team members only) which shows the slowest spec files and runtime
trends.

---

## Profiling From the Performance Bar

If you have GDK or admin access to a target instance, the
[Performance Bar](https://docs.gitlab.com/administration/monitoring/performance/performance_bar/)
is the fastest way to start. It can:

- Profile any request with **Stackprof** and output a
  [Speedscope flame graph](https://docs.gitlab.com/development/profiling/#speedscope-flamegraphs)
- Run **memory_profiler** for the current URL

No code changes needed — just enable the bar and request the URL you want
to profile.

---

## When To Stop Profiling

The [Performance Guidelines](https://docs.gitlab.com/development/performance/#importance-of-changes)
include a section called *"Importance of Changes"* worth quoting:

> *"When working on performance improvements, it's important to always ask
> yourself the question 'How important is it to improve the performance of
> this piece of code?'. Not every piece of code is equally important and
> it would be a waste to spend a week trying to improve something that
> only impacts a tiny fraction of our users."*

Examples the guidelines call out as **not worth the effort**:

- Replacing double quotes with single quotes
- Replacing `Array` with `Set` when the list is very small
- Replacing library A with library B when both take up 0.1% of total time
- Calling `.freeze` on every string

After profiling, ask: does the hottest frame in the profile account for
enough of total time to be worth optimizing? If it's at 1%, look elsewhere.
