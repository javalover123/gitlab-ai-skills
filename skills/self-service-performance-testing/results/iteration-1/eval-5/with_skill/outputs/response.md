No, you don't need to run any performance tests before merging this.

Both of your changes are documentation-only:

- **CHANGELOG.md** is pure documentation and never affects runtime behavior.
- **Inline comments in config/database.yml** are comments only. As long as you literally added comments and didn't change any actual values (pool size, timeouts, host, adapter, etc.), YAML comments are ignored at parse time and have zero runtime effect.

Since nothing in the application code changed and no configuration values were altered, there's no code path, query, or load characteristic that could regress. A performance test wouldn't measure anything different from the current baseline.

One thing worth a quick double-check before you merge: confirm you only *documented* the connection pool settings and didn't also *change* any of them. If a comment nudged you to also tweak the actual `pool:` value, that's a different story:

- The connection pool size directly affects how many concurrent DB connections each process can hold. Raising or lowering it can shift database load and change behavior under concurrency, which is exactly the kind of thing a load test would want to catch.
- In that case, the right tool would be GPT (the GitLab Performance Tool) for backend/DB load against a **dedicated performance environment** — never staging or production, since a pool misconfiguration under load is a good way to take an environment offline and block everyone's pipelines.

But assuming this really is just a CHANGELOG entry plus explanatory comments, you're clear to merge with no performance testing. If you do end up adjusting the pool value and want a hand sizing a test, ping #g_performance_enablement on Slack.
