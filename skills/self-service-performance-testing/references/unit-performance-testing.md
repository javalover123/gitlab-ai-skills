# Unit-Level Performance Testing (rspec-benchmark)

**Gem:** [rspec-benchmark](https://github.com/piotrmurach/rspec-benchmark)
**Status in `gitlab-org/gitlab`:** included in the Gemfile, available in any
spec.
**Canonical reference:** [GitLab Performance Testing Tool Selection Guide — Using rspec-benchmark](https://handbook.gitlab.com/handbook/engineering/testing/performance-tools/#using-rspec-benchmark)

rspec-benchmark provides RSpec matchers that assert on performance
characteristics of individual methods or blocks — execution time,
iterations per second, allocation counts, and complexity scaling. Use it
when you want a performance regression to fail in the spec suite, scoped
to a specific unit of code.

## When to Use rspec-benchmark

Use when:

- A method or class is on a hot path and you want to lock in its current
  performance with an assertion the test suite enforces on every run.
- You've just fixed an N+1 or slow path and want a regression guard that's
  cheaper than a full k6 / CPT load test.
- You need to demonstrate that a method scales linearly (not quadratically)
  with input size.

Do **not** use when:

- The behavior you care about only manifests under concurrent load — use
  GPT or CPT instead.
- You're testing a full request/response cycle — use a request spec with
  `QueryRecorder` for query-count regressions, or k6 / CPT for latency
  regressions.
- You're trying to find out *why* something is slow — use a profiler (see
  [profiling.md](profiling.md)).

## The Four Matcher Families

### 1. `perform_under(time).ms` — execution time bound

```ruby
expect {
  UserFinder.new.find_active
}.to perform_under(50).ms
```

Asserts the block completes in under 50ms. Other units: `.sec`, `.us`, `.ns`.

### 2. `perform_allocation(count: range)` — allocation bound

```ruby
expect {
  UserFinder.new.find_active
}.to perform_allocation(count: 1..20)
```

Asserts the block allocates between 1 and 20 objects. Useful for catching
accidental object explosions (e.g., a new `.map` that builds an intermediate
array per row).

### 3. `perform_linear.in_range(min..max)` — scaling shape

```ruby
expect do |n, i|
  users = create_list(:user, n, status: :active)
  UserFinder.new.find_active
end.to perform_linear.in_range(10..100).sample(5)
```

Asserts the block's execution time scales linearly with `n` across the
input range, sampled at 5 points. Other scaling matchers:
`perform_constant`, `perform_logarithmic`, `perform_power`, `perform_exponential`.
This is the matcher that catches accidental N+1 / N² regressions even when
the absolute time is still small.

### 4. `perform_at_least(iters).ips` — throughput bound

```ruby
expect { some_fast_method }.to perform_at_least(1_000).ips
```

Asserts the block runs at least 1000 iterations per second. Less common in
GitLab's suite; usually `perform_under` is more direct.

## Complete Example (from handbook)

```ruby
require 'spec_helper'

RSpec.describe UserFinder do
  describe '#find_active' do
    it 'performs query under 50ms' do
      users = create_list(:user, 100, status: :active)

      expect {
        UserFinder.new.find_active
      }.to perform_under(50).ms
    end

    it 'allocates less than 20 objects' do
      users = create_list(:user, 100, status: :active)

      expect {
        UserFinder.new.find_active
      }.to perform_allocation(count: 1..20)
    end

    it 'scales linearly with number of users' do
      expect do |n, i|
        users = create_list(:user, n, status: :active)
        UserFinder.new.find_active
      end.to perform_linear.in_range(10..100).sample(5)
    end
  end
end
```

Source: [GitLab Performance Testing Tool Selection Guide](https://handbook.gitlab.com/handbook/engineering/testing/performance-tools/#using-rspec-benchmark)

## Caveats and Pitfalls

- **Time-based matchers are inherently noisy on CI runners.** Use them
  sparingly and set generous thresholds (50ms, not 5ms). Repeated flakes
  erode trust in the suite. If a time matcher is flaky, prefer
  `perform_allocation` or `perform_linear` instead — both are deterministic.
- **`perform_linear` runs the block multiple times** with different input
  sizes. Make sure the setup (factories, fixtures) is included inside the
  block argument or the assertion is meaningless.
- **Warm up if needed.** rspec-benchmark handles repetition internally for
  ips/scaling matchers, but a fresh class-loaded codepath may have one-time
  init cost. For a single-shot `perform_under`, call the method once before
  the `expect` block to discard cold-start cost.
- **These specs run in normal RSpec runs.** Don't put expensive perf specs
  in the hot path of `bundle exec rspec` for everyday developers — tag them
  (`:performance`) and run them in a dedicated CI job if they take more
  than a few seconds.

## When to Reach For Something Bigger

- Symptom is "the request is slow" not "this method is slow" → use
  QueryRecorder for query-count regressions, or k6 / CPT for end-to-end
  latency. See [getting-started.md](getting-started.md).
- Need to compare *before and after* a code change with statistical
  confidence → use [benchmark-ips](profiling.md#benchmark-ips) directly in
  a script, or `derailed_benchmarks` for full-app boot/memory comparison.
- Symptom is intermittent / load-dependent → unit specs won't reproduce it.
  Use GPT or CPT.
