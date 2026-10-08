# Rust Code Quality Rules

## Error Handling

Rust's type system gives you the tools to make errors explicit and recoverable. Don't throw that away with `.unwrap()`.

- Never use `.unwrap()` or `.expect()` in library/production code
  ```rust
  // BAD: let v = map.get("key").unwrap();
  // GOOD: let v = map.get("key").ok_or_else(|| Error::NotFound)?;
  ```
- Use `match` for contextual branching, `?` for linear propagation
- Implement `std::error::Error` for custom errors with `source()` chaining
- Layer errors by abstraction level: Storage -> Service -> API
- Use `thiserror` for library errors, `anyhow` only in binaries
- Include enough context to diagnose: "failed to read config" beats "I/O error"

## Async (Tokio)

Blocking the executor is the async equivalent of holding up the checkout line while you run back for milk.

- Never block the executor:
  ```rust
  // BAD: std::thread::sleep(), std::fs::read()
  // GOOD: tokio::time::sleep(), tokio::fs::read()
  ```
- Use `spawn_blocking` for unavoidable blocking ops (like CPU-heavy computation)
- Provide `CancellationToken` for spawned tasks -- they need a way to shut down gracefully
- Use `tokio::sync` primitives, not `std::sync` across `.await` points (a `std::Mutex` held across an await will deadlock)

## Ownership

The borrow checker isn't your enemy. If you're fighting it, that's usually a design signal worth listening to.

- Accept `&str` not `&String`, `&[T]` not `&Vec<T>` -- let callers pass what they have
  ```rust
  // BAD: fn process(data: &Vec<String>) -> ...
  // GOOD: fn process(data: &[impl AsRef<str>]) -> ...
  ```
- Avoid `.clone()` to satisfy the borrow checker (usually a design issue worth rethinking)
- Use `Cow<'_, T>` for conditional allocation -- borrowed when you can, owned when you must
- Pre-allocate collections when size is known: `Vec::with_capacity(n)`

## Modern Rust (2021/2024)

- `LazyLock`/`OnceLock` instead of `lazy_static!` -- they're in std now
- `let-else` for early returns: `let Some(x) = val else { return Err(...); };`
- Native async closures (2024 edition)
- `let` chains in `if`/`while` (2024 edition)
- Edition 2024 resolver is the default -- no more `resolver = "2"` in workspace manifests

## Detection Commands

```bash
# unwrap/expect abuse (excluding test code)
rg '\.unwrap\(\)|\.expect\(' --type rust -g '!tests/'

# Blocking calls in async code
rg 'std::thread::sleep|std::fs::' --type rust

# Overly specific parameter types
rg 'fn.*&String|fn.*&Vec<' --type rust

# Unsafe blocks (audit each one)
rg 'unsafe\s*\{' --type rust

# Full lint
cargo clippy --workspace --all-targets -- -D warnings

# Security audit
cargo audit && cargo deny check
```

## Crate Organization

When your project grows past a single crate, here's a structure that keeps things maintainable.

- `shared-types`: Traits, error types, common structs
- `shared-db`: Database operations ONLY -- no business logic
- `helper-normalization`: Data transformation and cleaning
- `helper-versioning`: Version handling and comparison
- `helper-ecosystem`: Ecosystem-specific logic
- `-sys` crates: Raw FFI bindings, paired with safe wrapper crates
