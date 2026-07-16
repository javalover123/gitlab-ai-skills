# Rust Static Analysis Tools

Curated from 33 open-source Rust analysis tools. Focused on unsafe code, FFI boundaries, and security auditing.

## Primary tools — run these on every review

### clippy (with restriction lints)

The standard Rust linter. For unsafe/FFI review, enable the restriction lint group alongside pedantic.

```bash
# Standard pedantic pass
cargo clippy -- -W clippy::pedantic

# Unsafe-focused lints
cargo clippy -- \
  -W clippy::undocumented_unsafe_blocks \
  -W clippy::multiple_unsafe_ops_per_block \
  -W clippy::unnecessary_safety_comment \
  -W clippy::unnecessary_safety_doc \
  -D clippy::transmute_ptr_to_ref \
  -D clippy::cast_ptr_alignment

# Restriction lints for security-critical code
cargo clippy -- \
  -W clippy::as_conversions \
  -W clippy::arithmetic_side_effects \
  -W clippy::indexing_slicing \
  -W clippy::panic \
  -W clippy::unwrap_used \
  -W clippy::expect_used
```

**What to look for:** `undocumented_unsafe_blocks` (every unsafe block needs a `// SAFETY:` comment), `transmute_ptr_to_ref` (almost always UB), `cast_ptr_alignment` (misaligned pointers cause UB on most architectures).

### cargo-audit

Checks Cargo.lock against the RustSec Advisory Database for known vulnerabilities.

```bash
# Install
cargo install cargo-audit

# Basic audit
cargo audit

# JSON output for CI
cargo audit --json

# Fix yanked/vulnerable deps automatically
cargo audit fix
```

**What to look for:** any advisory with RUSTSEC ID. Prioritize by CVSS score. `cargo audit fix` handles most cases, but review the version bumps for breaking changes.

### cargo-deny

Policy enforcement for dependencies. Checks licenses, bans specific crates, detects duplicates, and flags advisories.

```bash
# Install
cargo install cargo-deny

# Initialize config
cargo deny init

# Run all checks
cargo deny check

# Check specific category
cargo deny check advisories
cargo deny check licenses
cargo deny check bans
cargo deny check sources
```

**What to look for:** unlicensed dependencies, copyleft contamination in permissive-licensed projects, duplicate crate versions (often indicates diamond dependency issues), advisory findings.

### cargo-geiger

Counts and reports unsafe code usage across your dependency tree. Essential for understanding your unsafe surface area.

```bash
# Install
cargo install cargo-geiger

# Report unsafe usage
cargo geiger

# Include build dependencies
cargo geiger --all-features --all-targets

# Machine-readable output
cargo geiger --output-format json
```

**What to look for:** dependencies with high unsafe ratios that you wouldn't expect to need unsafe code. A crypto library using unsafe is expected; a string formatting library shouldn't need it.

## Unsafe-specific analysis

### Miri

An interpreter for Rust's MIR (Mid-level Intermediate Representation) that detects undefined behavior in unsafe code.

```bash
# Install (requires nightly)
rustup +nightly component add miri

# Run tests under Miri
cargo +nightly miri test

# Run a specific binary
cargo +nightly miri run

# With Stacked Borrows validation (default, stricter)
MIRIFLAGS="-Zmiri-tag-gc=1" cargo +nightly miri test

# With Tree Borrows (experimental, less strict)
MIRIFLAGS="-Zmiri-tree-borrows" cargo +nightly miri test
```

**What to look for:** stacked borrows violations (aliasing issues), use of uninitialized memory, out-of-bounds access, use-after-free, data races, invalid enum discriminants. Miri is sound for the checks it performs — if Miri reports UB, it's real.

**Limitations:** can't test FFI calls into C code, no I/O, no inline assembly. Testing coverage depends on which code paths your tests exercise.

### Rudra

Memory safety and undefined behavior detection for Rust. Developed at Georgia Tech's SSLab. Finds bugs that clippy misses.

```bash
# Install (requires specific nightly)
# Check https://github.com/sslab-gatech/Rudra for current nightly version
rustup install nightly-2021-10-21
cargo +nightly-2021-10-21 install rudra

# Analyze current crate
cargo rudra
```

**What to look for:** `SendSyncVariance` (incorrect Send/Sync implementations), `UnsafeDestructor` (panic safety in Drop impls), `UnsafeDataflow` (unsafe value flow from untrusted sources).

### kani (Rust Model Checker)

Bit-precise model checker from AWS. Proves properties about unsafe code or finds counterexamples. Particularly strong for verifying memory safety and absence of panics.

```bash
# Install
cargo install --locked kani-verifier
cargo kani setup

# Verify all proof harnesses
cargo kani

# Verify specific harness
cargo kani --harness my_proof_harness

# With concrete playback (generates failing test cases)
cargo kani --concrete-playback=inplace
```

**When to use:** writing proof harnesses for critical unsafe code. kani can prove that a function never panics, never accesses out-of-bounds memory, and never triggers UB — for all possible inputs up to a given bound.

### Prusti

Formal verification for Rust. Based on the Viper verification infrastructure. Proves absence of panics and verifies user-specified contracts.

```bash
# Install via VS Code extension or
# Docker: docker pull viperproject/prusti
docker run -v $(pwd):/work viperproject/prusti cargo prusti
```

**When to use:** high-assurance code where you need mathematical proof of correctness. Requires adding precondition/postcondition annotations.

## Dependency and supply chain analysis

### cargo-udeps

Finds unused dependencies in Cargo.toml. Unused deps increase attack surface for no benefit.

```bash
# Install
cargo install cargo-udeps --locked

# Check for unused deps (requires nightly)
cargo +nightly udeps
```

### cargo-bloat

Identifies what's taking space in your binary. Useful for detecting unexpectedly large dependencies.

```bash
# Install
cargo install cargo-bloat

# Show largest functions
cargo bloat --release -n 20

# Show largest crates
cargo bloat --release --crates
```

## Testing tools for unsafe code

### cargo-fuzz

Coverage-guided fuzzing using libFuzzer. Essential for testing parsers and code handling untrusted input.

```bash
# Install
cargo install cargo-fuzz

# Initialize fuzz targets
cargo fuzz init

# Run a fuzz target
cargo fuzz run my_target

# Run with AddressSanitizer (default) + time limit
cargo fuzz run my_target -- -max_total_time=300
```

### proptest

Property-based testing. Generates random inputs and checks invariants. Good complement to Miri.

```toml
# Cargo.toml
[dev-dependencies]
proptest = "1.4"
```

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn my_function_never_panics(input in any::<Vec<u8>>()) {
        // If this panics, proptest will shrink the input
        // to a minimal failing case
        let _ = my_function(&input);
    }
}
```

## Tool selection by review scenario

| Scenario | Run these |
|----------|-----------|
| Unsafe code audit | clippy (restriction lints) + Miri + cargo-geiger |
| FFI boundary review | Miri + kani proof harnesses + cargo-fuzz |
| Dependency security | cargo-audit + cargo-deny + cargo-geiger |
| Supply chain audit | cargo-deny (sources check) + cargo-geiger + cargo-udeps |
| Pre-commit / CI gating | clippy (pedantic) + cargo-audit + cargo-deny |
| Formal verification | kani or Prusti (for critical paths) |

## ANSSI Rust security guidelines

The French National Cybersecurity Agency (ANSSI) publishes Rust security guidelines covering safe coding practices, unsafe usage, FFI patterns, and memory management. Available at: https://anssi-fr.github.io/rust-guide/
