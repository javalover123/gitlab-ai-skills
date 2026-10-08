# Dependency Optimization Reference

Covers feature flag minimization, lightweight alternatives, the auditing toolchain, and workspace dependency deduplication.

---

## Feature Flag Minimization

Features are additive and unioned across the dependency graph — if any crate enables a feature, all get it. Using `default-features = false` with selective features can cut compile times 20–50% for heavy crates:

```toml
[dependencies]
tokio = { version = "1", default-features = false, features = ["rt", "macros", "net"] }
serde = { version = "1", default-features = false, features = ["derive"] }
reqwest = { version = "0.12", default-features = false, features = ["json", "rustls-tls"] }
```

**How to find which features you actually need**: Start with `default-features = false` and compile. Add back feature flags until it builds. The compile errors will tell you exactly which features are missing.

---

## Lightweight Dependency Alternatives

For crates that are pulling in hundreds of transitive dependencies:

| Heavy crate | Light alternative | Impact |
|-------------|------------------|--------|
| `reqwest` (~200 deps) | `ureq` (~20 deps) | Massive binary and compile reduction |
| `serde` with derive macros | `nanoserde` or `miniserde` | Much faster compilation |
| `serde_json` | `simd-json` | 1.5–2.7× faster parsing |
| `clap` with derive | `lexopt` | No proc macros |
| `log` + `env_logger` | `tracing` with minimal features | Structured logging, similar cost |

Before switching: check API compatibility, maintenance status, and whether the lighter alternative covers your actual usage.

---

## Auditing Toolchain

Run these to find problems in your dependency tree:

### cargo tree -d (built-in)

Finds duplicate dependency versions. Each duplicate version compiles separately.

```bash
cargo tree -d         # show all duplicates
cargo tree -p tokio   # show dependency chain for a specific crate
```

### cargo-machete (fast, stable)

Regex-based detection of unused dependencies. Works on stable Rust.

```bash
cargo install cargo-machete
cargo machete
```

### cargo-shear (more accurate)

Uses rust-analyzer's parser for better accuracy than cargo-machete. Has `--fix` for auto-removal.

```bash
cargo install cargo-shear
cargo shear
cargo shear --fix    # auto-remove unused deps
```

### cargo-audit (security)

Checks for known CVEs in your dependency tree.

```bash
cargo install cargo-audit
cargo audit
```

### cargo-deny (CI gate)

Enforces policies on licenses, duplicate versions, security advisories, and banned crates. Runs as a CI check.

```toml
# deny.toml
[advisories]
ignore = []

[licenses]
allow = ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"]

[bans]
multiple-versions = "deny"
```

```bash
cargo install cargo-deny
cargo deny check
```

### cargo-geiger (unsafe audit)

Shows unsafe code usage across the dependency tree with per-crate ratios.

```bash
cargo install cargo-geiger
cargo geiger
```

---

## Workspace Dependency Deduplication

In a Cargo workspace, declare shared dependencies once and have members inherit them:

```toml
# Cargo.toml (workspace root)
[workspace.dependencies]
tokio = { version = "1.0", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
thiserror = "2.0"
```

In each member crate:
```toml
# crates/my-crate/Cargo.toml
[dependencies]
tokio.workspace = true
serde.workspace = true
```

This ensures all workspace members use the same version, preventing duplicate compilation. Use `cargo-autoinherit` to migrate an existing project automatically:

```bash
cargo install cargo-autoinherit
cargo autoinherit
```

---

## Workspace Structure for Build Parallelism

Cargo builds independent crates in parallel. A workspace sharing a single `target/` directory compiles shared dependencies once — benchmarks show 40–60% build time reduction for medium projects.

Structure along domain boundaries with parallel-friendly topology:

```toml
[workspace]
resolver = "2"
members = ["core", "api-types", "db", "server", "cli"]
```

Rather than a linear chain (`cli → server → db → core`), a diamond shape (multiple crates depending on `core` and `api-types` independently) lets Cargo parallelize more work.

---

## Resources

- [cargo-deny](https://embarkstudios.github.io/cargo-deny/)
- [cargo-nextest](https://nexte.st/)
- [cargo-machete](https://github.com/bnjbvr/cargo-machete)
- [cargo-geiger](https://github.com/rust-secure-code/cargo-geiger)
