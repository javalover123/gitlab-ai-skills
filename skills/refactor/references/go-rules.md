# Go Code Quality Rules

## Error Handling

Every error deserves attention. If you're discarding one, you'd better have a good reason -- and that reason should be in a comment.

- Never discard errors with `_`: every error must be handled or documented why it's safe to ignore
  ```go
  // BAD: result, _ := SomeFunction()
  // GOOD: result, err := SomeFunction()
  // if err != nil {
  //     return fmt.Errorf("context: %w", err)
  // }
  ```
- Always wrap errors with context: `fmt.Errorf("fetching user %d: %w", id, err)`
- Use `errors.Is()` and `errors.As()` for comparison, never `==`
- Never return bare `err` without wrapping -- the caller needs to know *where* things broke

## Nil Safety

Go's zero values can bite you in surprising ways. Be deliberate about "not set" vs "empty."

- Use Option types for optional values (never pointer types or empty strings as "not set")
  ```go
  // BAD: if name != "" { ... }
  // GOOD: if name.IsSome() { ... }
  ```
- Check errors before deferring cleanup -- if opening a resource failed, there's nothing to close
- Initialize maps before use (`var m map[K]V` then writing = panic)
- Don't rely on nil slices being "empty" when nil has semantic meaning

## Concurrency

Goroutines are cheap to start and easy to leak. Every goroutine you spawn needs a way to stop.

- Always provide goroutine exit mechanisms (check `ctx.Done()` or close channels)
- Close channels to signal completion -- don't leave readers hanging
- Use context for cancellation propagation (pass as first parameter)
- Defer `cancel()` for derived contexts immediately after creation
- Use `errgroup` for coordinated goroutine lifecycle
- Never share memory without synchronization -- even "read-only" data can surprise you

## Modern Go (1.21+)

Take advantage of newer language features. They're cleaner and the compiler can reason about them better.

- Use `min()`/`max()` builtins instead of hand-rolled comparisons
- Use `for i := range n` for counting loops
- Use `slices` and `maps` packages instead of hand-written loops
- Use `slog` for structured logging -- it's in the standard library now
- Use generics for type-safe containers and utility functions

## Detection Commands

```bash
# Ignored errors
rg '_ = |, *_ *:*=' --type go

# Bare error returns (missing context wrapping)
rg 'return err' --type go

# Empty string checks (consider Option types)
rg '!= ""|== ""' --type go

# Cyclomatic complexity hotspots
gocyclo -over 15 ./...
gocognit -over 15 ./...

# Code duplication
dupl -t 100 ./...

# Full lint suite
golangci-lint run ./...
```

## Helper Package Structure

Keep packages focused. A package that does "a little of everything" helps nobody.

- `pkg/common`: General utilities, type conversion, string manipulation
- `pkg/util`: I/O operations, HTTP helpers, file handling
- `pkg/version`: Version parsing, comparison, ranges
- `pkg/ecosystem`: Ecosystem detection, normalization
- `pkg/db`: Database operations ONLY -- no business logic here
- `internal/`: Project-specific code that shouldn't be imported by others
