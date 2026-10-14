# Test Coverage Strategies

Guide for improving test coverage systematically during iteration cycles.

## Coverage Metrics — at a glance

### Line Coverage
- **What**: Percentage of lines executed during tests
- **Target**: 80%+ for critical code, 60%+ across the codebase
- **Limitation**: High line coverage doesn't mean all logic paths tested

### Branch Coverage
- **What**: Percentage of decision branches (if/else, switch, loops) executed
- **Target**: 75%+ for critical code
- **Better than**: Line coverage (catches untested conditionals)

### Function Coverage
- **What**: Percentage of functions called during tests
- **Target**: 90%+ (almost all functions should be tested)
- **Quick check**: Identifies completely untested code

### Path Coverage
- **What**: Percentage of unique execution paths tested
- **Target**: Impractical for 100% (exponential growth)
- **Focus**: Critical paths and error paths

## Measuring Coverage

### Rust
```bash
# Install tarpaulin
cargo install cargo-tarpaulin

# Run with HTML report
cargo tarpaulin --out Html --output-dir coverage/

# Open coverage/index.html in browser
```

### Go
```bash
# Generate coverage profile
go test -coverprofile=coverage.out ./...

# View in terminal
go tool cover -func=coverage.out

# Generate HTML report
go tool cover -html=coverage.out -o coverage.html
```

### Python
```bash
# Install pytest-cov
pip install pytest-cov

# Run with HTML report
pytest --cov=mypackage --cov-report=html

# Open htmlcov/index.html in browser
```

### C
```bash
# Compile with coverage flags
gcc -fprofile-arcs -ftest-coverage -o test test.c

# Run tests
./test

# Generate report
gcov test.c
lcov --capture --directory . --output-file coverage.info
genhtml coverage.info --output-directory coverage/
```

## Prioritizing Coverage Work

### Critical Paths First
1. **User-facing operations**: Login, data submission, payment processing
2. **Data modification**: Anything that changes state
3. **Security-sensitive code**: Authentication, authorization, input validation
4. **Error handling**: How does code behave on failure?

### Don't Waste Time On
- **Generated code**: Protobuf, parser generators, etc.
- **Trivial getters/setters**: Unless they have logic
- **Main functions**: Often hard to test, minimal logic
- **Third-party code**: Not your responsibility

### Coverage Gaps to Address

**Red flags (fix immediately):**
- Untested public APIs
- Untested error handling
- Untested security checks
- Untested database operations

**Yellow flags (fix soon):**
- Untested private functions with complex logic
- Untested edge cases
- Low branch coverage on conditionals

**Green flags (low priority):**
- Trivial functions well-covered by integration tests
- Defensive checks that can't fail in practice

## Testing Strategies

### Unit Tests
**Purpose**: Test individual functions in isolation

**When to use**:
- Pure functions (no side effects)
- Business logic
- Utility functions
- Edge cases and error conditions

**Example (Rust):**
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_valid_input() {
        let result = parse_input("valid");
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), Expected);
    }

    #[test]
    fn test_parse_invalid_input() {
        let result = parse_input("invalid");
        assert!(result.is_err());
    }

    #[test]
    fn test_parse_empty_input() {
        let result = parse_input("");
        assert!(result.is_err());
    }

    #[test]
    fn test_parse_edge_case() {
        let result = parse_input("边界");
        assert!(result.is_ok());
    }
}
```

### Integration Tests
**Purpose**: Test components working together

**When to use**:
- API endpoints
- Database operations
- File I/O
- Multi-component workflows

**Example (Rust):**
```rust
// tests/integration_test.rs
use myapp::App;

#[tokio::test]
async fn test_user_registration_flow() {
    let app = App::new_test_instance().await;

    // Create user
    let response = app.post("/api/register")
        .json(&json!({"email": "test@example.com"}))
        .await;
    assert_eq!(response.status(), 201);

    // Verify user exists
    let user = app.db.get_user("test@example.com").await.unwrap();
    assert_eq!(user.email, "test@example.com");
}
```

### Property-Based Tests
**Purpose**: Test properties that should hold for many inputs

**When to use**:
- Parsers (parse then serialize = identity)
- Encoders/decoders
- Compression
- Cryptographic primitives

**Example (Rust with proptest):**
```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_roundtrip(s in "\\PC*") {
        let encoded = encode(&s);
        let decoded = decode(&encoded).unwrap();
        assert_eq!(s, decoded);
    }
}
```

### Fuzz Tests
**Purpose**: Find crashes and edge cases with random input

**When to use**:
- Parsers (high attack surface)
- File format handlers
- Network protocol implementations

**Example (Rust with cargo-fuzz):**
```rust
#![no_main]
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let _ = myparser::parse(data);
    // Should not panic
});
```

### Snapshot Tests
**Purpose**: Verify output hasn't changed unexpectedly

**When to use**:
- Rendering (HTML, images)
- Code generation
- Pretty-printing
- Complex data structures

**Example (Rust with insta):**
```rust
#[test]
fn test_render_user_profile() {
    let user = User::new("alice");
    let html = render_profile(&user);
    insta::assert_snapshot!(html);
}
```

## Filling Coverage Gaps

### Pattern: Test-Driven Gap Closure

1. **Generate coverage report**
2. **Identify untested function**
3. **Write test that calls it**
4. **Re-run coverage**
5. **Verify improvement**

### Pattern: Branch Coverage Improvement

When branch coverage is low:

1. **Find conditional with missing branch**:
   ```rust
   if condition {
       // Tested
   } else {
       // NOT tested ← gap
   }
   ```

2. **Write test exercising missing branch**:
   ```rust
   #[test]
   fn test_else_branch() {
       let result = function_with_conditional(trigger_else);
       // Assert expected behavior
   }
   ```

### Pattern: Error Path Testing

Many gaps are in error handling:

```rust
// Typical untested error paths
fn process(data: &str) -> Result<Output, Error> {
    let parsed = parse(data)?;  // What if parse fails? ← test this
    let validated = validate(parsed)?;  // What if validate fails? ← test this
    Ok(transform(validated))
}

// Tests to add:
#[test]
fn test_process_parse_error() {
    let result = process("invalid");
    assert!(matches!(result, Err(Error::ParseError(_))));
}

#[test]
fn test_process_validation_error() {
    let result = process("parseable but invalid");
    assert!(matches!(result, Err(Error::ValidationError(_))));
}
```

### Pattern: Edge Case Enumeration

For each input:

- **Empty**: "", [], None
- **Minimal**: Single element, zero, smallest valid value
- **Maximal**: Large string, max int, capacity limit
- **Boundary**: Off-by-one values (len-1, len, len+1)
- **Invalid**: Wrong type, null, negative where positive expected
- **Special**: Unicode, whitespace, special characters

**Example:**
```rust
#[test]
fn test_split_lines_empty() {
    assert_eq!(split_lines(""), vec![]);
}

#[test]
fn test_split_lines_single() {
    assert_eq!(split_lines("one"), vec!["one"]);
}

#[test]
fn test_split_lines_multiple() {
    assert_eq!(split_lines("one\ntwo"), vec!["one", "two"]);
}

#[test]
fn test_split_lines_trailing_newline() {
    assert_eq!(split_lines("one\n"), vec!["one"]);
}

#[test]
fn test_split_lines_windows_newlines() {
    assert_eq!(split_lines("one\r\ntwo"), vec!["one", "two"]);
}

#[test]
fn test_split_lines_unicode() {
    assert_eq!(split_lines("日本語\n中文"), vec!["日本語", "中文"]);
}
```

## Mocking and Test Doubles

### When to Mock

**Do mock**:
- External APIs (HTTP requests)
- Databases (unless using test DB)
- File system (slow, side effects)
- Time (for deterministic tests)
- Random number generators (for deterministic tests)

**Don't mock**:
- Your own code (test it for real)
- Trivial dependencies
- Data structures

### Rust Mocking Example

```rust
use mockall::automock;

#[automock]
trait Repository {
    fn get_user(&self, id: u64) -> Result<User, Error>;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_service_with_mock_repo() {
        let mut mock_repo = MockRepository::new();
        mock_repo
            .expect_get_user()
            .with(eq(42))
            .returning(|_| Ok(User { id: 42, name: "Alice".into() }));

        let service = Service::new(mock_repo);
        let user = service.process(42).unwrap();
        assert_eq!(user.name, "Alice");
    }
}
```

### Test Database Pattern (Go)

```go
func setupTestDB(t *testing.T) *sql.DB {
    db, err := sql.Open("sqlite3", ":memory:")
    require.NoError(t, err)

    // Run migrations
    _, err = db.Exec(schema)
    require.NoError(t, err)

    t.Cleanup(func() { db.Close() })
    return db
}

func TestUserRepository(t *testing.T) {
    db := setupTestDB(t)
    repo := NewRepository(db)

    user := User{Name: "Alice"}
    err := repo.Create(&user)
    require.NoError(t, err)
    assert.Greater(t, user.ID, 0)
}
```

## Coverage Anti-Patterns

### Anti-Pattern: Chasing 100%

**Problem**: Diminishing returns, testing trivial code

**Solution**: Set realistic targets (80-90%), exclude generated code

### Anti-Pattern: Tests Without Assertions

**Problem**: High coverage, low quality (tests don't verify behavior)

```rust
// BAD: Runs code but doesn't test anything
#[test]
fn test_process() {
    let _ = process("input");
}

// GOOD: Verifies behavior
#[test]
fn test_process() {
    let result = process("input");
    assert_eq!(result, expected_output);
}
```

### Anti-Pattern: Testing Implementation

**Problem**: Tests break on refactoring, even when behavior unchanged

```rust
// BAD: Depends on implementation details
#[test]
fn test_internal_cache_updated() {
    let service = Service::new();
    service.fetch_data();
    assert!(service.cache.contains_key("data"));
}

// GOOD: Tests observable behavior
#[test]
fn test_data_fetched_correctly() {
    let service = Service::new();
    let data = service.fetch_data();
    assert_eq!(data.value, expected);
}
```

### Anti-Pattern: Flaky Tests

**Problem**: Tests sometimes pass, sometimes fail (race conditions, timing)

**Solution**: Make tests deterministic
- Mock time instead of using real time
- Avoid sleeps (use explicit synchronization)
- Seed random number generators
- Use in-memory databases (not shared disk)

## Coverage Improvement Checklist

Per iteration:

- [ ] Generate coverage report
- [ ] Identify functions/branches with 0% coverage
- [ ] Prioritize critical paths
- [ ] Write tests for untested code
- [ ] Re-run coverage
- [ ] Verify coverage improved (X% → Y%)
- [ ] Ensure new tests have assertions
- [ ] Check tests are deterministic (run multiple times)
- [ ] Update coverage metrics in iteration log

## Tools by Language

### Rust
- `cargo-tarpaulin` — Coverage for cargo projects
- `cargo-llvm-cov` — LLVM-based coverage (more accurate)
- `grcov` — Alternative coverage tool

### Go
- `go test -cover` — Built-in coverage
- `gocov` — Better reporting
- `go-junit-report` — JUnit XML for CI

### Python
- `pytest-cov` — pytest integration for coverage.py
- `coverage.py` — Standard coverage tool
- `diff-cover` — Coverage of changed lines only

### C/C++
- `gcov` — GCC coverage
- `lcov` — gcov frontend
- `llvm-cov` — LLVM coverage

### JavaScript/TypeScript
- `istanbul` / `nyc` — Coverage for Node.js
- `jest --coverage` — Built-in for Jest

## Resources

- **Rust testing**: https://doc.rust-lang.org/book/ch11-00-testing.html
- **Go testing**: https://go.dev/doc/tutorial/add-a-test
- **pytest**: https://docs.pytest.org/
- **Property testing**: https://hypothesis.readthedocs.io/ (Python), proptest (Rust)
- **Fuzzing**: cargo-fuzz (Rust), go-fuzz (Go), AFL
