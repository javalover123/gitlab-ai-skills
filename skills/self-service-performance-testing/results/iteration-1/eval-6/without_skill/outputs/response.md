Short version: you don't want a load test for this — you want an **in-suite RSpec regression guard** that measures the cost of one method and fails when it grows past a fixed budget. gitlab-org/gitlab already has the tooling for exactly this. There are two flavors depending on what "bloat" means to you:

- **Query count / N+1** → `exceed_query_limit` (or `exceed_all_query_limit`), backed by `ActiveRecord::QueryRecorder`.
- **Object allocations** → a `GC.stat(:total_allocated_objects)` delta bounded by a hard ceiling.

Pick based on what your refactor actually reduced. If you were cutting allocations specifically, do the allocation guard; if the win was fewer/cheaper SQL calls, the query-count guard is the more stable and idiomatic choice. Doing both is fine and common.

Your spec already exists: `spec/finders/merge_requests_finder_spec.rb` (`RSpec.describe MergeRequestsFinder, feature_category: :code_review_workflow`). Add the guard there.

## Option A — allocation guard (matches "reduce allocations")

```ruby
describe '#execute performance', :aggregate_failures do
  let_it_be(:user) { create(:user) }
  let_it_be(:project) { create(:project, :repository) }
  let_it_be(:merge_requests) { create_list(:merge_request, 5, source_project: project) }

  let(:params) { { project_id: project.id } }

  # Regression guard for the #execute allocation refactor.
  # Bump ONLY with a comment justifying the increase.
  ALLOCATION_LIMIT = 20_000

  it 'does not exceed the allocation budget' do
    finder = described_class.new(user, params)

    # Warm up caches/memoization so we measure steady-state, not first-call setup.
    finder.execute.to_a

    before = GC.stat(:total_allocated_objects)
    described_class.new(user, params).execute.to_a
    allocated = GC.stat(:total_allocated_objects) - before

    expect(allocated).to be <= ALLOCATION_LIMIT
  end
end
```

Key points:
- **Force execution.** Finders return an `ActiveRecord::Relation`, which is lazy — nothing runs until you enumerate it. Call `.to_a` (or `.load`) inside the measured block, otherwise you're measuring almost nothing.
- **Warm up first.** The first call allocates for query plan caching, connection setup, autoloading, etc. Measure a second call so the number reflects the method, not one-time setup.
- **Set the limit from a real measurement.** Run the method locally on your post-refactor code, note the steady-state number, and set the ceiling a bit above it (headroom for legitimate churn — roughly 10-15%, not 2x, or the guard never fires). A tight-but-not-brittle ceiling is what makes this catch reintroduced bloat.
- Disable GC around the block (`GC.disable`/`GC.enable`) only if you find the number is noisy; usually `total_allocated_objects` is a stable counter and you don't need to.

## Option B — query-count guard (idiomatic in gitlab-org/gitlab)

If the bloat you removed was in the SQL, this is the more robust guard — query counts are deterministic where raw allocation counts can drift with unrelated changes. This is the standard N+1/query-budget pattern used all over the finder specs (`spec/finders/members_finder_spec.rb`, `deployments_finder_spec.rb`, etc.):

```ruby
it 'does not regress the query count' do
  control = ActiveRecord::QueryRecorder.new do
    described_class.new(user, params).execute.to_a
  end

  # Post-refactor steady-state count + small margin.
  expect(control.count).to be <= 8
end
```

For the classic "count doesn't grow as the dataset grows" N+1 shape:

```ruby
it 'avoids N+1 queries' do
  control = ActiveRecord::QueryRecorder.new { described_class.new(user, params).execute.to_a }

  create_list(:merge_request, 3, source_project: create(:project, :repository))

  expect { described_class.new(user, params).execute.to_a }
    .not_to exceed_query_limit(control)
end
```

`exceed_query_limit` accepts either an integer budget or a `QueryRecorder` control, and there's an `exceed_all_query_limit` variant that includes cached queries. Both live in `spec/support/matchers/exceed_query_limit.rb`.

## Why this over a load test

A k6/GPT load test spins up an environment and hammers an HTTP endpoint — the right tool for user-journey throughput and p95/p99 latency, but wrong here. It's slow, needs a dedicated performance environment (never staging/production), and can't isolate one Ruby method. Your guard runs in the normal rspec suite on every MR, fails fast and cheap, and points straight at `#execute`. Keep it method-scoped exactly as you intended.

## Making it durable

- Put a comment on the limit constant saying it's a deliberate regression budget and that raising it needs justification — otherwise the next person just bumps the number when it fails, which defeats the guard.
- Keep the setup dataset small and fixed (`let_it_be`) so the number is reproducible and the test stays fast.
- If you're unsure whether the allocation count will be stable enough across Ruby/CI environments, prefer the query-count guard — it's the more portable of the two.

If later you do want end-to-end latency coverage for the merge-requests list (a different question from this method-level guard), that's when GPT or the Performance Testing Kit comes in — but for "fail the spec suite if the bloat comes back," the guard above is all you need.
