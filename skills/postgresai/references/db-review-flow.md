# Before requesting a database review

Maps to GitLab's [database review guidelines](https://docs.gitlab.com/development/database_review/).

1. **List the queries** the change adds or modifies. In GDK, enable SQL logging while
   running the feature or its specs and collect the distinct statements (watch for N+1).
2. **Plan each one** on the clone: `joe plan`, then `joe explain` with realistic
   parameters (large project or namespace, not an empty one).
3. **Fix what's slow**: apply the loop in [plan-analysis.md](plan-analysis.md).
4. **Migrations**: test new indexes or columns with `joe exec`, then `joe reset`.
5. **Write up in the MR**: for each query, the SQL, a plan link or sanitized plan text, and
   timing/buffers. Replace real values with placeholders; no production data.
6. Request the review with that evidence attached.
