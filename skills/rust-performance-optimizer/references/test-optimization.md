# Test Suite Optimization Reference

Covers cargo-nextest, integration test structure, and rstest parameterization.

---

## cargo-nextest

`nextest` runs each test in a **separate process**, enabling better parallelism, isolation, and memory control. Typically ~40% faster than `cargo test` with zero configuration.

Install: `cargo install cargo-nextest`

```bash
cargo nextest run          # replaces: cargo test
cargo nextest run --locked # for CI
```

### Configuration (`.config/nextest.toml`)

```toml
[profile.default]
test-threads = "num-cpus"
fail-fast = true
slow-timeout = { period = "60s", terminate-after = 2 }

[profile.ci]
fail-fast = false
retries = 2
failure-output = "immediate-final"

# Serialize tests that share a resource (e.g., a database)
[test-groups]
serial-db = { max-threads = 1 }

[[profile.default.overrides]]
filter = 'test(db_)'
test-group = 'serial-db'
```

### `--jobs` vs `--test-threads`

This distinction trips people up:
- `--jobs` — controls **compilation** parallelism (number of rustc processes)
- `--test-threads` — controls **test execution** parallelism

For memory-constrained CI, combine both:
```bash
cargo nextest run --jobs 2 --test-threads 4
```

---

## Integration Test Structure

Every file in `tests/` becomes a **separate binary**, each linking independently. If you have 20 integration test files, you're linking 20 separate executables — the compile time adds up fast.

### The fix: single entry point

Instead of:
```
tests/
  auth.rs        # separate binary
  payments.rs    # separate binary
  users.rs       # separate binary
```

Do this:
```
tests/
  integration.rs  # single binary
  common/
    mod.rs        # shared helpers — NOT compiled as a test binary
```

`integration.rs`:
```rust
mod common;
mod auth;
mod payments;
mod users;
```

**Key rule**: `tests/common/mod.rs` is NOT compiled as a test binary. But `tests/common.rs` WOULD be — it's a file at the top level of `tests/`. Always use the `mod.rs` pattern for shared helpers.

---

## rstest — Parameterized Tests

`rstest` removes test function duplication with parameterized cases and fixtures.

```toml
[dev-dependencies]
rstest = "0.23"
```

### Parameterized cases

```rust
use rstest::rstest;

#[rstest]
#[case(0, 0)]
#[case(1, 1)]
#[case(4, 3)]
#[case(13, 7)]
fn fibonacci_test(#[case] input: u32, #[case] expected: u32) {
    assert_eq!(expected, fibonacci(input));
}
```

### Test matrices

`#[values(...)]` generates cartesian products automatically:

```rust
#[rstest]
fn test_combinations(
    #[values("alice", "bob")] name: &str,
    #[values(18, 21, 25)] age: u32,
) {
    // Runs 6 tests (2 names × 3 ages)
    assert!(is_valid_user(name, age));
}
```

### Shared fixtures with `#[once]`

```rust
#[fixture]
#[once]
fn database() -> TestDatabase {
    TestDatabase::new()  // called once, shared across all tests using this fixture
}

#[rstest]
fn test_with_db(database: &TestDatabase) {
    // ...
}
```

---

## Quick Wins Summary

For most projects, these two changes pay off immediately:

1. Switch from `cargo test` to `cargo nextest run` — zero code changes, ~40% speed gain
2. Consolidate `tests/*.rs` into a single `tests/integration.rs` — reduces linker invocations

If you're writing many similar test cases by hand, `rstest` eliminates the duplication.

---

## Resources

- [cargo-nextest](https://nexte.st/)
- [nextest configuration reference](https://nexte.st/docs/configuration/)
- [rstest](https://github.com/la10736/rstest)
- [Rust book — integration tests](https://doc.rust-lang.org/book/ch11-03-test-organization.html)
