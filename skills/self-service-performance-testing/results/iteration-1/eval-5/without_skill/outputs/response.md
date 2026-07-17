No, you don't need to run performance tests for this change.

Here's the reasoning:

- **CHANGELOG.md** is pure documentation. It's not loaded, parsed, or executed by the application at runtime, so it has zero impact on performance.
- **Inline comments in `config/database.yml`** are also inert. YAML comments (`# ...`) are stripped during parsing and never affect the resolved configuration. As long as you only added comments and did not change any actual values (pool size, timeout, host, adapter, etc.), the runtime behavior is byte-for-byte identical to before.

Performance testing is meant to catch regressions in things that actually execute or change how the system behaves under load — new/changed code paths, altered DB queries, modified connection pool *values*, changed indexes, new endpoints, etc. None of that applies to a docs + comments change.

A couple of things worth double-checking before you merge, just to be safe:

1. **Confirm it's truly comments-only.** Run a diff to make sure no config values sneaked in:
   ```
   git diff config/database.yml
   ```
   Verify every non-blank change starts with `#`. If you accidentally touched `pool:`, `timeout:`, `checkout_timeout:`, `reaping_frequency:`, or similar, then that *would* warrant a look at performance/connection behavior.

2. **YAML syntax is still valid.** Comments are hard to break, but a stray `#` inside a quoted string or an accidental edit to indentation can subtly change parsing. A quick sanity check:
   ```
   ruby -ryaml -e "YAML.load_file('config/database.yml')"
   ```
   or, if your app uses ERB in that file, boot the app / run its config-load step in a dev environment.

If both of those check out, this is a safe, no-perf-impact change. Standard code review is all it needs — no load test, no benchmark, no staging performance run required.

One nice side benefit: documenting your connection pool settings inline is genuinely useful, since pool sizing is a common source of confusion and production incidents. If you want, this could be a good moment to note *why* the current pool values were chosen (e.g. matching them to your web/worker thread count), so the next person doesn't have to reverse-engineer it — but that's a documentation improvement, not a testing requirement.
