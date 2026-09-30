# Reading and iterating on plans

Run `joe explain` (ANALYZE, BUFFERS) for the real picture; `joe plan` only gives estimates.

## What to look at

- **Buffers** (`shared hit` / `read`): the most stable metric. Timing on a clone varies
  with cache state; buffer counts don't. Aim for few buffers, mostly hits.
- **Timing**: compare the first and second run; a big gap means a cold cache.
- **Estimates vs actual rows**: a large mismatch points to stale statistics or
  correlated columns.
- **Seq Scan on large tables**, or `Rows Removed by Filter` much larger than rows
  returned: a missing or unsuitable index.
- **Sort / hash spilling to disk** (`Disk:`), and nested loops with many loops over
  big inner sets.
- **Index Scan vs Index Only Scan** and `Heap Fetches`.

## Iterating

1. `joe hypo "create index on t (cols)"` to test whether the planner would use an index.
2. If promising, `joe exec "CREATE INDEX ..."` and re-run `joe explain`. Plan shape
   alone is not proof; confirm buffers drop.
3. Try a couple of column orders, partial indexes (`WHERE`), or query rewrites.
4. `joe reset` between unrelated experiments so earlier indexes don't distort results.

Hypothetical (`hypo`) results are estimates; confirm real indexes with `exec` + `explain`.
Check each candidate index against GitLab's migration guidelines (concurrent creation,
naming, necessity) before turning it into a migration.
