# Refactoring Strategies for Reducing Compilation Memory

This reference provides detailed guidance on identifying and refactoring Rust code patterns that cause high compilation memory usage.

## Strategy 1: Reduce Monomorphization Overhead

### Detection

From `cargo llvm-lines` output, look for functions appearing 50+ times:

```
  Lines        Copies    Function name
  -----        ------    -------------
  95123 (100%)  1203 (100%) (TOTAL)
   2134 (2.2%)   145 (12%) core::fmt::Display::fmt
   1876 (2.0%)    89 (7%)  serde::ser::Serialize::serialize
```

High copy counts indicate monomorphization explosion.

### Refactoring: Extract Non-Generic Code

**Problem:** Generic function with complex logic duplicated per type.

```rust
// Before: 1000+ lines of LLVM IR per instantiation
pub fn process_data<T: Serialize + Clone>(items: Vec<T>) -> Result<String> {
    let mut results = Vec::new();

    for item in &items {
        // Complex validation (duplicated per T)
        if !validate_item(item) {
            return Err("Invalid item");
        }

        // Complex transformation (duplicated per T)
        let transformed = transform(item.clone())?;

        // Serialization (needs to be generic)
        let json = serde_json::to_string(&transformed)?;
        results.push(json);
    }

    Ok(results.join("\n"))
}
```

**After:** Non-generic code extracted, only serialization generic.

```rust
// Generic wrapper - thin, minimal IR
pub fn process_data<T: Serialize + Clone>(items: Vec<T>) -> Result<String> {
    items.iter()
        .map(|item| serialize_item(item))
        .collect::<Result<Vec<_>>>()?
        .join("\n")
        .into()
}

// Non-generic validation (shared across all types)
fn validate_json(json: &str) -> bool {
    // Complex validation, compiled once
    !json.is_empty() && json.len() < 1_000_000
}

// Only this part is duplicated per type
fn serialize_item<T: Serialize + Clone>(item: &T) -> Result<String> {
    let json = serde_json::to_string(&item.clone())?;
    if !validate_json(&json) {
        return Err("Validation failed");
    }
    Ok(json)
}
```

**Memory reduction:** ~40% fewer LLVM IR lines per instantiation.

### Refactoring: Use Trait Objects

**Problem:** Many concrete types implementing the same trait.

```rust
// Before: Each handler type creates new instantiation
pub fn dispatch<H: Handler>(handler: H, events: Vec<Event>) {
    for event in events {
        handler.handle(event);
    }
}

// Usage creates many instantiations
dispatch(FileHandler::new(), events1);
dispatch(NetworkHandler::new(), events2);
dispatch(DatabaseHandler::new(), events3);
// ... 20+ handler types
```

**After:** Dynamic dispatch with trait objects.

```rust
// After: Single compiled version
pub fn dispatch(handler: &dyn Handler, events: Vec<Event>) {
    for event in events {
        handler.handle(event);
    }
}

// Usage: single compiled function
dispatch(&FileHandler::new(), events1);
dispatch(&NetworkHandler::new(), events2);
dispatch(&DatabaseHandler::new(), events3);
```

**Tradeoff:** Small runtime cost (virtual dispatch) for large compile-time savings.

**When to use:**
- 10+ concrete types implementing a trait
- Handler/strategy patterns
- Functions not in hot path

**When to avoid:**
- Hot inner loops
- Functions requiring const generics
- Zero-cost abstractions needed

## Strategy 2: Reduce Large Type Impact

### Detection

From heap profile or compiler error messages about large stack frames:

```
warning: function uses more than 4096 bytes of stack space
  --> src/config.rs:42:1
```

Or from `heaptrack` showing large allocations in type checking.

### Refactoring: Box Large Fields

**Problem:** Large inline fields increase stack usage and type-checking memory.

```rust
// Before: 8KB struct on stack
pub struct ApplicationConfig {
    database: DatabaseConfig,      // 2KB
    network: NetworkConfig,         // 1KB
    cache: CacheConfig,             // 3KB
    logging: LoggingConfig,         // 2KB
}

impl ApplicationConfig {
    pub fn load() -> Self {
        // Stack allocation = 8KB
        Self {
            database: DatabaseConfig::default(),
            network: NetworkConfig::default(),
            cache: CacheConfig::default(),
            logging: LoggingConfig::default(),
        }
    }
}
```

**After:** Box large fields to keep stack small.

```rust
// After: ~32 bytes on stack (4 pointers)
pub struct ApplicationConfig {
    database: Box<DatabaseConfig>,
    network: Box<NetworkConfig>,
    cache: Box<CacheConfig>,
    logging: Box<LoggingConfig>,
}

impl ApplicationConfig {
    pub fn load() -> Self {
        Self {
            database: Box::new(DatabaseConfig::default()),
            network: Box::new(NetworkConfig::default()),
            cache: Box::new(CacheConfig::default()),
            logging: Box::new(LoggingConfig::default()),
        }
    }
}
```

**Memory reduction:** Reduces type-checking memory and stack frame size.

### Refactoring: Split Large Enums

**Problem:** Enum with many large variants causes high memory usage during exhaustiveness checking.

```rust
// Before: 50 variants, some very large
pub enum Message {
    RequestConfig(ConfigRequest),           // 100 bytes
    ResponseConfig(ConfigResponse),         // 500 bytes
    RequestData(DataRequest),               // 200 bytes
    ResponseData(DataResponse),             // 1KB
    // ... 46 more variants
}

// Compiler must allocate space for largest variant (1KB)
// Times number of instances in flight
```

**After:** Group related variants, use nested enums.

```rust
// After: Split by message type
pub enum ConfigMessage {
    Request(ConfigRequest),
    Response(ConfigResponse),
}

pub enum DataMessage {
    Request(DataRequest),
    Response(DataResponse),
}

pub enum Message {
    Config(ConfigMessage),          // 500 bytes max
    Data(DataMessage),              // 1KB max
    // Other groups...
}
```

**Memory reduction:** Smaller enum sizes, better cache locality.

## Strategy 3: Reduce Feature Combinations

### Detection

From build logs showing many feature combinations being compiled:

```bash
cargo build --all-features
# Compiling mylib v0.1.0 (32 feature combinations)
```

From `cargo tree`:
```bash
cargo tree -e features | grep -c "feature"
```

### Refactoring: Consolidate Features

**Problem:** Exponential feature combinations.

```rust
// Before: 2^4 = 16 combinations
#[cfg(feature = "feature-a")]
mod impl_a;

#[cfg(feature = "feature-b")]
mod impl_b;

#[cfg(all(feature = "feature-a", feature = "feature-c"))]
mod impl_ac;

#[cfg(all(feature = "feature-b", feature = "feature-d"))]
mod impl_bd;

// Each combination compiles separately
```

**After:** Reduce to groups of features.

```rust
// After: Group related features
#[cfg(any(feature = "group-1"))]
mod group1 {
    // Combine feature-a and feature-c
}

#[cfg(any(feature = "group-2"))]
mod group2 {
    // Combine feature-b and feature-d
}
```

In `Cargo.toml`:

```toml
[features]
default = []
group-1 = ["feature-a", "feature-c"]
group-2 = ["feature-b", "feature-d"]
```

**Memory reduction:** Fewer compilation units, reduced feature matrix.

## Strategy 4: Reduce Macro Expansion Size

### Detection

From `-Z macro-backtrace` or large files in `target/` directory after macro expansion.

### Refactoring: Limit Macro Recursion

**Problem:** Recursive macros generating huge token trees.

```rust
// Before: Recursive macro creating large expansion
macro_rules! generate_impls {
    ($($t:ty),*) => {
        $(
            impl MyTrait for $t {
                // Complex implementation (duplicated per type)
                fn method1(&self) { /* 50 lines */ }
                fn method2(&self) { /* 50 lines */ }
                fn method3(&self) { /* 50 lines */ }
            }
        )*
    }
}

// Generates 1000+ lines
generate_impls!(u8, u16, u32, u64, i8, i16, i32, i64, f32, f64);
```

**After:** Use generic implementation or proc macro.

```rust
// After: Generic implementation
impl<T: Numeric> MyTrait for T {
    fn method1(&self) { /* single implementation */ }
    fn method2(&self) { /* single implementation */ }
    fn method3(&self) { /* single implementation */ }
}

// Or use proc macro for unavoidable cases
#[derive(MyTrait)]
struct MyType;
```

**Memory reduction:** Smaller token trees during macro expansion.

## Strategy 5: Split Large Modules

### Detection

From compilation logs showing single files taking minutes to compile:

```bash
cargo build -v 2>&1 | grep "Compiling" | sort -k 3 -n
```

Or using `cargo-modules`:
```bash
cargo modules generate tree --lib | grep -E '\[.*MB\]'
```

### Refactoring: Extract Submodules

**Problem:** Single 5000-line file causes high memory usage during parsing and type-checking.

```rust
// Before: src/handlers.rs (5000 lines)
mod handlers {
    pub struct HandlerA { /* ... */ }
    impl HandlerA { /* 500 lines */ }

    pub struct HandlerB { /* ... */ }
    impl HandlerB { /* 500 lines */ }

    // ... 8 more handlers
}
```

**After:** Split into separate files.

```
src/
  handlers/
    mod.rs
    handler_a.rs
    handler_b.rs
    ...
```

```rust
// src/handlers/mod.rs
mod handler_a;
mod handler_b;

pub use handler_a::HandlerA;
pub use handler_b::HandlerB;
```

**Memory reduction:** Parallel compilation, smaller parsing units.

## Strategy 6: Optimize Dependency Tree

### Detection

```bash
cargo tree --duplicates
cargo bloat --release --crates
```

Look for:
- Multiple versions of same crate
- Unused dependencies
- Heavy dependencies for light features

### Refactoring: Prune Dependencies

**Problem:** Pulling in large dependency trees.

```toml
# Before
[dependencies]
tokio = { version = "1.0", features = ["full"] }  # Brings 50+ deps
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
reqwest = "0.12"  # Brings tokio anyway
```

**After:** Minimal features, deduplicated versions.

```toml
# After
[dependencies]
tokio = { version = "1.0", features = ["rt", "net"] }  # Only what you need
serde = { version = "1.0", default-features = false, features = ["derive"] }
serde_json = { version = "1.0", default-features = false }
reqwest = { version = "0.12", default-features = false, features = ["json"] }
```

**Memory reduction:** Fewer crates compiled, smaller dependency graph.

## Pattern Detection Automation

See [scripts/detect-patterns.sh](../scripts/detect-patterns.sh) for automated detection of these patterns.

## Measurement After Refactoring

After applying each strategy, measure impact:

```bash
# Before
cargo clean
heaptrack cargo build --release
# Note peak RSS

# After refactoring
cargo clean
heaptrack cargo build --release
# Compare peak RSS

# Calculate reduction percentage
```

Document each change with before/after measurements to track cumulative improvement.

---

## Strategy 6: Build-Cache Hygiene (Non-Code)

Not every "rebuilds everything, uses tons of RAM" problem is a code problem. A meaningful share of apparent compile-memory issues are really cache-invalidation issues: the same deps get compiled two, three, sometimes four times into the same `target/` because different tooling modes keep separate fingerprints. Cut this first — it's mechanical and the gain is immediate.

### Detection

```bash
# How many distinct builds of each dep are in the cache?
ls target/debug/.fingerprint/ \
  | grep -oE '^[a-z0-9_-]+-[a-f0-9]{16}$' \
  | sed 's/-[a-f0-9]*$//' \
  | sort | uniq -c | sort -rn | head
```

Any row with count > 1 is a duplicated dep lineage. Also informative:

```bash
df -h .                                  # target dir at >95%? that's the acute issue
ls rust-toolchain.toml 2>/dev/null       # unpinned = rustup update invalidates everything
du -sh target/debug/incremental          # regeneratable cache, often 50+ GB
```

### Unify per-package overrides across profiles

Cargo scopes `[profile.<p>.package."*"]` to the profile that declares it. Overrides do **not** inherit even when the base profile does. So:

```toml
# This ONLY applies when cargo build / cargo run is active.
# cargo test deps get dev defaults, not these flags.
[profile.dev.package."*"]
opt-level = 1
debug = false
```

`cargo test` then rebuilds every dep with different flags → different fingerprint → second copy of everything in `target/`. Peak RSS is unchanged per build but doubled across the suite, and wall-clock time is wasted.

**Fix:** declare identical overrides for every profile the repo uses:

```toml
[profile.test.package."*"]
opt-level = 1
debug = false

[profile.bench.package."*"]
opt-level = 1
debug = false

# And any custom profiles
[profile.fast-test.package."*"]
opt-level = 1
debug = false
```

Workspace crates still honor their own per-profile base settings — dev vs release distinctions are intentional and should stay different. It's only the `package."*"` dep override that benefits from being uniform.

### Pin the toolchain

Every fingerprint includes `rustc`'s own hash. `rustup update` — manual or auto — advances `nightly` by one day and invalidates every artifact in `target/`. For reproducible profiling and stable local caches, pin:

```toml
# rust-toolchain.toml (project root)
[toolchain]
channel = "nightly-2026-01-19"
components = ["rust-src", "rustfmt", "clippy"]
profile = "minimal"
```

For Nix users, also pin inside the flake so dev-shell and rustup agree:

```nix
rustToolchain = pkgs.rust-bin.nightly."2026-01-19".default.override {
  extensions = [ "rust-src" "rust-analyzer" "clippy" "rustfmt" ];
};
```

`pkgs.rust-bin.nightly.latest` drifts with the `nixpkgs` input; the dated form is immutable.

### Give editor-side cargo check its own target dir

Editor-integrated `cargo check` (rust-analyzer) emits `.rmeta` files. CLI `cargo build` emits `.rlib`. They coexist in the same target but track as different unit kinds — so switching from editor to terminal or back keeps triggering rebuilds. Split them:

```elisp
;; .dir-locals.el — Emacs + eglot
((nil . ((eglot-workspace-configuration
          . (:rust-analyzer (:cargo (:targetDir t)))))))
```

```json
// .vscode/settings.json
{"rust-analyzer.cargo.targetDir": true}
```

Both forms resolve to `target/rust-analyzer/`. `.gitignore` rule for `target/` covers it automatically.

### When to apply before profiling

Run through this strategy *before* establishing a baseline. Otherwise the baseline captures the cache-invalidation thrash instead of the compile memory you're trying to measure, and the after-refactor numbers tell you nothing.

## References

- [Rust Performance Book - Compile Times](https://nnethercote.github.io/perf-book/compile-times.html)
- [Minimizing Rust Binary Size](https://github.com/johnthagen/min-sized-rust)
- [cargo-llvm-lines documentation](https://github.com/dtolnay/cargo-llvm-lines)
