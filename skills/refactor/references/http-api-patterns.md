# HTTP/API Patterns

Refactoring HTTP code means consolidating scattered logic, improving error handling, and making sure your API works reliably under load. This reference covers the patterns that actually matter.

## Client Code

When you're calling out to other services, a lot goes wrong if you're not careful.

**Consolidate HTTP helpers.** If you've got retry logic in one place, auth setup in another, and timeout handling scattered across files, you've got a problem. Create a shared HTTP client package that wraps the standard library (or whatever framework you're using). Put retry, timeout, authentication, and header setup in one place. Now you can fix bugs everywhere at once instead of six different locations.

**Use context/cancellation everywhere.** Pass context through your entire call chain. This way, if a request gets cancelled (user closed the browser, request timed out at the gateway), every downstream operation respects that cancellation. You're not starting work that'll just get thrown away.

```go
// Good: context flows through
resp, err := client.Do(ctx, req)
if err := ctx.Err(); err != nil {
    return err // cancelled or timed out
}
```

**Close response bodies.** This is the killer for resource leaks. You read the body, you close it. Even if the read fails, close it. Even if you didn't read it, close it. Most languages will tell you the body wasn't read, so you can't skip this step.

**Handle rate limiting.** If the API you're calling returns 429, you need to back off. Read the `Retry-After` header if it exists. Implement exponential backoff for your retries, with jitter so you're not thundering herd with every other client.

## Server Code

Building reliable API servers means being ruthless about boundaries.

**Extract middleware.** Logging, authentication, error handling, request tracing — these all belong in middleware, not in every handler. You write it once, it applies everywhere.

**Consistent error responses.** Every endpoint should return errors in the same format. Your clients depend on it. That means:
- Same HTTP status codes for the same errors
- Same JSON/XML structure for error details
- Consistent message fields

If you've got one endpoint returning `{"error": "msg"}` and another returning `{"message": "msg"}`, you've got a problem. Pick one format and use it.

**Validate at boundaries.** All input validation happens when the request comes in, not buried in business logic. That way you can be confident that everything past the handler is valid. It also makes error messages better — users see validation errors immediately, not buried in a 500 error.

**Use request IDs.** Generate a unique ID for every incoming request. Pass it through:
- All log statements
- All outgoing HTTP calls (add a header)
- All database queries (as a query parameter or context value)
- Error responses to clients

When something goes wrong at 2 AM, that request ID is the thread that unravels the whole failure.

### Detecting API Issues

```bash
# HTTP calls without context (Go)
rg 'http\.(Get|Post|Head|Do)\(' --type go -A2 | grep -v 'ctx\|context'

# Unclosed response bodies (Go/Rust/Python)
rg 'http\.(Get|Post|Do)' -A10 --type go | grep -v 'Close\|defer'
rg 'response\.text\(\)|response\.json\(' -B2 --type py | grep -v 'with\|finally'

# Middleware missing (check handlers for logging)
rg 'func.*Handler|def.*handler' --type go --type py | wc -l
# Compare to middleware count
```

If you find HTTP calls without context or response bodies without explicit closing, that's your refactor target.
