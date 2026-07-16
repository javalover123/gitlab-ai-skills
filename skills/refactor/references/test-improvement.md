# Test Improvement Patterns

## Before Refactoring

Get the lay of the land before you touch anything. You need to know what's tested,
what isn't, and what's flaky.

```
Pre-Refactoring Test Audit:
- [ ] Run ALL tests — record the exact pass/fail state
- [ ] Measure coverage with your language's tool
- [ ] Identify untested public functions and methods
- [ ] Note any flaky or slow tests (they'll bite you later)
- [ ] Document expected behavior for code you're about to change
```

If tests are failing *before* you start, fix them first or document them as known
failures. You can't use "all tests pass" as a verification criterion if some were
already broken.

## During Refactoring

The rule is simple: write tests BEFORE changing code. Every time.

```
Test-First Cycle:
- [ ] Write tests that lock current behavior
- [ ] Verify tests pass on the EXISTING code
- [ ] Make your refactoring change
- [ ] Run tests immediately — they must still pass
- [ ] Add edge case tests for the refactored code
- [ ] Run the full suite after each logical change
```

If you can't write a test for what you're refactoring, that's a signal. Either the code
is too tightly coupled (which is itself a refactoring target), or you don't understand
the behavior well enough yet. Step back and read more code before proceeding.

## Test Patterns by Type

### Unit Tests

- **Fast**: Each test should run in under 100ms. If it's slower, you probably need a mock.
- **Isolated**: No shared state between tests. Each test sets up its own world.
- **Focused**: One behavior per test. "TestProcessOrder" that checks validation, calculation, AND persistence is doing too much.
- **Table-driven**: When testing the same logic with multiple inputs, use table-driven tests (Go), parameterized tests (Python/pytest), or test macros (Rust).
- **Mocked at boundaries**: Mock I/O, network, and database calls. Don't mock internal functions — that couples your tests to implementation details.

**Go table-driven example:**
```go
tests := []struct {
    name     string
    input    string
    expected string
    wantErr  bool
}{
    {"valid version", "1.2.3", "1.2.3", false},
    {"strips v prefix", "v1.2.3", "1.2.3", false},
    {"empty string", "", "", true},
    {"garbage", "not-a-version", "", true},
}
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        got, err := NormalizeVersion(tt.input)
        if tt.wantErr {
            require.Error(t, err)
            return
        }
        require.NoError(t, err)
        assert.Equal(t, tt.expected, got)
    })
}
```

### Integration Tests

- Separate from unit tests (different file, tag, or directory)
- Test real interactions between components
- Acceptable to be slower — but still keep them as fast as possible
- Clean up resources after each test (databases, temp files, network connections)
- Use testcontainers or similar for database/service dependencies

### Test Organization

- Tests live close to the code they test (same directory, `_test.go`/`_test.rs`/`test_*.py`)
- Shared test utilities go in a dedicated test helper package
- Fixtures and test data in a `testdata/` or `fixtures/` directory
- Don't put test helpers in production code packages

## Coverage Goals

Coverage isn't a vanity metric — it's a safety net indicator.

**Per session:** Coverage should increase or stay flat with each refactoring pass. It
should *never* decrease. If it does, either you deleted tested code without replacing
the tests, or you added untested code.

**Prioritize coverage for:**
- Complex logic with many branches
- Error handling paths (these are the ones that matter in production)
- Security-sensitive code (auth, crypto, input validation)
- Code that's been buggy recently (historical hotspots)

**Target:** 80%+ line coverage is a good goal. But 100% error handling coverage matters more
than 100% line coverage. A codebase with 70% line coverage but 100% error path
coverage is healthier than one with 95% lines covered but untested error handling.

## Test Quality Metrics

High coverage with bad tests is worse than moderate coverage with good tests. Watch for
these quality signals:

- **Clear names**: `TestNormalizeVersion_StripsVPrefix` beats `TestNormalize2`
- **No flaky tests**: If a test fails intermittently, fix it or delete it. Flaky tests erode trust in the entire suite.
- **No order dependence**: Tests must pass when run in any order. If test B fails without test A running first, you've got shared state.
- **No external state dependence**: Tests shouldn't fail because a service is down or a file is missing from your machine
- **No arbitrary sleeps**: `time.Sleep(2 * time.Second)` in a test means you're waiting for something you should be polling or signaling for
- **Deterministic**: Same input, same output, every time. No randomness unless you're testing randomness itself (and even then, seed it).
