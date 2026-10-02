# Build Speed Optimization Reference

Covers linker selection, Cargo profiles, incremental compilation, the Cranelift backend, sccache, PGO, and proc-macro costs.

---

## Linker Selection (Biggest Single Win)

The linker is often the bottleneck. Switching from GNU `ld` to a modern parallel linker can cut link times by 10–20×.

| Linker | Relative speed | Platform | Notes |
|--------|---------------|----------|-------|
| GNU `ld` (BFD) | 1× (baseline) | Linux | Single-threaded, slowest |
| `gold` | ~2–3× | Linux | Google's parallel linker |
| `lld` (LLVM) | ~10× | Linux/Win/macOS | Being rolled out as default on x86_64-linux |
| `mold` | ~15–20× on Linux, smaller on macOS | Linux/macOS | Fastest on Linux; works on macOS via Homebrew but the system linker is already fast there |

**Config in `.cargo/config.toml`:**
```toml
[target.'cfg(target_os = "linux")']
rustflags = ["-C", "link-arg=-fuse-ld=mold"]
```

**Tradeoffs**: `mold` doesn't support LTO. For release builds needing LTO, use `lld`. On macOS, `mold` does work (install via Homebrew) but the system linker is already fast, so the win is smaller than on Linux; `sold` (the macOS port) or the default linker is usually fine.

---

## Cargo Profile Configuration

### Development profiles (faster iteration)

```toml
[profile.dev]
debug = "line-tables-only"         # Up to 70% faster incremental on macOS
split-debuginfo = "unpacked"

[profile.dev.package."*"]
debug = false                       # No debug info for dependencies
opt-level = 2                       # 5–10× faster runtime for dep code

[profile.dev.build-override]
opt-level = 1                       # Faster proc-macro execution
```

**Caveat on `opt-level = 2` for deps**: at level 2+, rustc stops sharing monomorphized generics between crates, potentially increasing binary size. Try `opt-level = 1` as a middle ground.

### Mirror `package."*"` overrides across every profile you use

Cargo scopes `package."*"` overrides to the profile that declares them. They do **not** inherit even when the base profile does. So a repo with only `[profile.dev.package."*"]` declared will compile deps under one set of flags for `cargo build`, and under the inherited-default flags for `cargo test`, `cargo bench`, and any custom profile that inherits from `dev` / `test`. Each distinct flag set gets its own fingerprint, so `target/debug/.fingerprint/` ends up with two (or more) copies of every dep — `gtk4-145e8b...` and `gtk4-97c194...` side by side — and dep rebuilds fire any time you switch between modes.

**Fix:** declare the dep override explicitly for every profile you actually exercise, with identical settings. Workspace crates still honor their per-profile base settings, so dev-vs-release distinctions are preserved.

```toml
[profile.dev.package."*"]
opt-level = 1
debug = false

[profile.test.package."*"]
opt-level = 1
debug = false

[profile.bench.package."*"]
opt-level = 1
debug = false

# Custom profiles need their own explicit override too
[profile.fast-test.package."*"]
opt-level = 1
debug = false
```

**Check whether this is worth doing on any given repo:** `ls target/debug/.fingerprint/ | sort | uniq -c -w 40` — two rows with the same prefix hash but different suffixes means dep duplication is happening.

**Doesn't fix:** `cargo check` vs `cargo build` — those produce different artifact kinds (`.rmeta` vs `.rmeta` + `.rlib`) and keep separate lineages regardless of profile alignment. For editor-integrated check loops (rust-analyzer), give the editor its own target dir instead. See [environment-config.md](environment-config.md#rust-analyzer-target-dir).

### Release profiles (max runtime performance)

```toml
[profile.release]
lto = "fat"
codegen-units = 1
panic = "abort"
strip = "symbols"
```

### LTO tradeoffs

| Setting | Build time impact | Runtime perf | Binary size |
|---------|------------------|-------------|-------------|
| `lto = false` (default) | Baseline | Baseline | Baseline |
| `lto = "thin"` | +30–50% | +5–15% | −5–15% |
| `lto = "fat"` | +100–300% | +10–20% | −10–20% |
| `lto = "off"` | −10–20% | −5–10% | +5–10% |

### codegen-units

Default is 256 with incremental (dev), 16 without (release). Setting `codegen-units = 1` in release enables maximum LLVM optimization at the cost of ~10–15% longer compile times.

---

## Incremental Compilation

- **Enabled by default** for dev builds — good for local iteration
- **Disable in CI** with `CARGO_INCREMENTAL=0`: incremental adds overhead to clean builds and inflates cache sizes
- Defaults to 256 codegen-units, trading runtime quality for faster recompilation

---

## Cranelift Backend (Nightly Only)

Cranelift replaces LLVM's codegen with a faster alternative: ~20% faster clean builds, ~40% fewer CPU-seconds.

```toml
# .cargo/config.toml (requires nightly)
[unstable]
codegen-backend = true

[profile.dev]
codegen-backend = "cranelift"
```

**Tradeoffs**: nightly only, produces slower runtime code, lacks SIMD and unwinding support, no debug info.

---

## sccache (Shared Compilation Cache)

```toml
# .cargo/config.toml
[build]
rustc-wrapper = "sccache"
```

With an S3 backend, real-world reports show ~50% build time reduction. Key limitation: can't cache crates that invoke the linker (binary crates, proc-macro crates). Split binary crates into a thin `main.rs` + library crate to maximize cache hits.

---

## Profile-Guided Optimization (PGO)

PGO delivers 10–20% runtime improvement via a two-phase build:

```bash
# Phase 1: instrument
RUSTFLAGS="-Cprofile-generate=/tmp/pgo-data" cargo build --release

# Run representative workloads
./target/release/myapp workload1 workload2

# Phase 2: merge and rebuild
llvm-profdata merge -o /tmp/pgo-data/merged.profdata /tmp/pgo-data
RUSTFLAGS="-Cprofile-use=/tmp/pgo-data/merged.profdata" cargo build --release
```

The `cargo-pgo` crate simplifies this to three commands: `cargo pgo build`, `cargo pgo run`, `cargo pgo optimize`.

---

## Proc-Macro Compile Times

Proc macros serialize the build graph — dependent crates wait for them. Techniques:

- Use `[profile.dev.build-override] opt-level = 1` for faster macro compilation
- Replace heavy macros with lighter alternatives: `miniserde` for `serde`, `lexopt` for `clap`
- Use `#[cfg_attr(feature = "serde", derive(Serialize))]` for conditional derives
- Audit expansion volume: `cargo expand --lib | wc -l`
- Quantify per-macro cost with nightly `-Zmacro-stats`

---

## Key Resources

- [Cargo Build Performance Guide](https://doc.rust-lang.org/stable/cargo/guide/build-performance.html)
- [Tips for Faster Rust Compile Times](https://corrode.dev/blog/tips-for-faster-rust-compile-times/)
- [cargo build --timings](https://doc.rust-lang.org/cargo/reference/timings.html) — interactive HTML Gantt chart
