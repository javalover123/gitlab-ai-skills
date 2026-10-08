# Database Code Patterns

When refactoring database code, you're usually working toward cleaner separation of concerns and safer query execution. This file covers the patterns that matter most.

## Code Organization

The golden rule: SQL belongs in one place, not scattered through your application.

**ALL SQL queries** go in a dedicated db package/module/crate. This is non-negotiable. Why? Because it's the only way to audit for injection vulnerabilities, tune queries without hunting through files, and test your data layer independently.

**NO SQL strings** should live in:
- Service or business logic files
- API handlers
- Provider code
- Configuration files

Use parameterized queries **EXCLUSIVELY**. Never build SQL with string concatenation, interpolation, or formatting functions. That's how vulnerabilities slip in.

### Detecting Organization Problems

```bash
# Find SQL outside db packages (Go/Rust/Python)
rg '(SELECT|INSERT|UPDATE|DELETE)' --type go --type rust --type py | grep -v 'db\|database\|repo'

# Catch SQL injection risks
rg 'format!.*SELECT|fmt\.Sprintf.*SELECT|f".*SELECT' --type go --type rust
```

If you see SQL queries anywhere but your data layer, move them. Don't negotiate.

## Transaction Patterns

Transactions are tricky because they're easy to get half-right.

**Defer rollback early.** In most languages (Go, Rust), you'll defer a rollback that's a no-op after commit. That simplicity is worth it. Here's why: you can't forget to rollback on error paths.

```go
// Good pattern
tx, err := db.Begin()
if err != nil {
    return err
}
defer tx.Rollback() // no-op after commit

// do work

if err := tx.Commit(); err != nil {
    return err
}
```

**Explicit commit required.** If rollback is deferred, commit must be explicit. You're not relying on implicit behavior.

**Handle transaction-scoped errors.** Some operations (like constraint violations) only show up during commit. Your error handling needs to know about them.

**Don't hold transactions across async/await boundaries.** If you're using async code, keep the transaction synchronous and tight. Holding locks while waiting for I/O is a deadlock waiting to happen.

## Connection Pools

Connection pools look simple but misconfiguration causes production pain.

**Pool size:** Start with `(CPU cores × 2) + disk spindles`. Adjust down if you're hitting open file limits. Adjust up only if you're seeing queueing in metrics.

**Connection timeouts:** Set both acquisition timeout (how long to wait for an idle connection) and statement timeout (how long before a single query fails).

**Max lifetime:** Connections age out. Set a max lifetime to prevent stale connections that've been sitting in the pool for hours. Five minutes is reasonable. Your database might have its own timeout that's shorter.

**Test before use:** Some drivers support connection testing. Enable it. Better to discover a bad connection during acquisition than mid-transaction.

### Verifying Pool Configuration

Check your logs and metrics:
- Are connections being dropped unexpectedly?
- Is the pool exhausted during normal load?
- Are queries timing out while connections sit idle?

If you see any of those, pool config needs adjustment.
