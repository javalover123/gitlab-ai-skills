You want **rspec-benchmark** — it's already in the `gitlab-org/gitlab` Gemfile, so nothing new to install. It gives you RSpec matchers that assert on a single method's performance and fail in the normal spec run. That's exactly the right tool here: you want a regression guard scoped to one method, cheap, in the suite you already run — no k6/CPT/GPT load test needed.

## The matcher you want: `perform_allocation`

Since you refactored specifically to reduce *allocations*, assert on the allocation count directly. This is deterministic (unlike wall-clock time), so it won't flake on CI:

```ruby
# spec/finders/merge_requests_finder_spec.rb (add to the existing describe block)

it 'does not regress on object allocations', :aggregate_failures do
  # Build a realistic dataset so the count reflects real usage, not an empty scan.
  project = create(:project)
  create_list(:merge_request, 20, source_project: project)  # adjust factory/traits to match your setup

  finder = described_class.new(user, project_id: project.id)

  # Warm up: discard one-time class-load / memoization cost before measuring.
  finder.execute.to_a

  expect do
    described_class.new(user, project_id: project.id).execute.to_a
  end.to perform_allocation(count: 1..N)
end
```

Two things to fill in:

- **`.execute.to_a`** — `MergeRequestsFinder#execute` returns a lazy `ActiveRecord::Relation`, so the allocations you care about don't happen until it's enumerated. Force it (`.to_a`, or `.to_a.size`) inside the block, or you'll be measuring the cost of building a relation object, not running your refactored code path.
- **`N`** — set the ceiling from your *current* (post-refactor) measurement plus a little headroom. Run the method through `memory_profiler` or just iterate on the matcher locally to find the real number, then pad it ~10-20% so normal churn doesn't trip it. A range like `count: 1..1500` is a budget, not an exact assertion — the point is to fail loudly if someone reintroduces the bloat, not to pin the exact count.

## A couple of practical notes

- **Prefer allocation over time here.** You *could* add `perform_under(50).ms`, but time-based matchers are noisy on shared CI runners and are a common source of flakes. Since your refactor was about allocations, `perform_allocation` measures the thing you actually changed and stays deterministic. Skip the time matcher unless you specifically want a latency guard too (and if so, keep the threshold generous — 50ms, not 5ms).
- **Consider `perform_linear` if the bloat was N-per-row.** If the allocations you removed scaled with the number of MRs (e.g. an intermediate array or object built per row), a scaling assertion catches a reintroduced regression even when the absolute count looks fine:

  ```ruby
  expect do |n, i|
    project = create(:project)
    create_list(:merge_request, n, source_project: project)
    described_class.new(user, project_id: project.id).execute.to_a
  end.to perform_linear.in_range(10..100).sample(5)
  ```

  Note the factory setup lives *inside* the block — `perform_linear` re-runs it at each input size, so if setup is outside the block the assertion is meaningless.
- **Tag it if it's slow.** These run in the normal `bundle exec rspec`. If your setup (factories, DB writes) makes the spec take more than a couple seconds, tag it `:performance` so it can be scoped to a dedicated job rather than slowing everyone's local runs.

## Nudge on scope

`MergeRequestsFinder#execute` is a hot, high-traffic path, and allocation churn there is real. But note: rspec-benchmark guards *this method's* allocations in isolation. If the regression you're really worried about is query count on the MR list (N+1s creeping back in via the relation), pair this with a `QueryRecorder` expectation in the corresponding request/finder spec — that's the deterministic guard for query bloat, and the two complement each other.

## References

- rspec-benchmark matchers and caveats: [handbook — Using rspec-benchmark](https://handbook.gitlab.com/handbook/engineering/testing/performance-tools/#using-rspec-benchmark)
- Gem README (all matcher families): [github.com/piotrmurach/rspec-benchmark](https://github.com/piotrmurach/rspec-benchmark)
- To find the actual allocation number to set your ceiling from, `memory_profiler` (also in the Gemfile) will give you a per-line breakdown.

If you want a hand picking the right ceiling or deciding whether to add the `QueryRecorder` guard too, #g_performance_enablement on Slack can help.
