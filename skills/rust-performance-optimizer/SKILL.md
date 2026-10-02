---
name: rust-performance-optimizer
description: >-
  Analyzes and tunes Rust project performance across build speed, runtime
  memory, binary size, and test throughput. Applies Cargo profile tuning,
  linker selection, dependency auditing, profiling, and workspace restructuring
  to fix bottlenecks. Use when Rust builds are slow, binaries are too large,
  memory is high at runtime, or CI times are painful. Triggers: "slow rust
  build", "binary size", "reduce memory", "rust profiling", "cargo timing",
  "cargo flamegraph", "nextest", "dependency audit".
version: 1.0.1
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: rust
---

# Rust Performance Tuning

It's a full-stack guide: build times, binary size, runtime memory, test speed, and dependency hygiene.

## Quick Start

Got a performance problem? Here's the fastest path forward:

1. **Build too slow?** — Switch the linker to `mold` or `lld` first. Biggest win with zero code changes. See [build-optimization.md](references/build-optimization.md).
2. **Memory too high at runtime?** — Profile with DHAT or heaptrack to find actual hotspots before changing anything. See [runtime-memory.md](references/runtime-memory.md).
3. **Binary too large?** — Run `cargo bloat --release --crates` to see what's actually large. See [profiling-tools.md](references/profiling-tools.md).
4. **Tests slow?** — Switch to `cargo nextest` (usually ~40% faster with zero config changes). See [test-optimization.md](references/test-optimization.md).

## When to Use This Skill

- Build times exceed 60 seconds for incremental builds or 10 minutes for clean
- Binary size is larger than expected (> 10 MB for a CLI, > 50 MB for a server)
- Runtime memory is higher than expected or OOM is happening in production
- `cargo test` feels slow and you want better parallelism or test isolation
- CI pipeline is slow or failing due to out-of-memory errors
- Someone mentions `cargo flamegraph`, `cargo bloat`, `cargo nextest`, `heaptrack`, `cargo-deny`, or PGO

## Workflow

Copy this checklist when you're starting a performance investigation:

```
Progress:
- [ ] Phase 1: Diagnose — which dimension(s) have problems?
- [ ] Phase 2: Baseline — collect before-metrics
- [ ] Phase 3: Fix — apply changes from the relevant reference
- [ ] Phase 4: Verify — compare after-metrics to baseline
```

### Phase 1: Diagnose

Identify which problem you're actually solving. Don't mix categories — a linker change helps build speed, not runtime memory.

**Build speed** — Is wall-clock time for `cargo build` too high? For clean builds or incremental?

**Runtime memory** — Is RSS too high while the binary runs? Are there hot allocation paths?

**Binary size** — Is the output executable or `.so` bigger than expected? Separate from runtime memory.

**Test performance** — Are tests slow to compile, slow to run, or both?

**Dependency hygiene** — Is the tree large, with unused crates, duplicated versions, or known advisories?

### Phase 2: Baseline

Collect concrete numbers before changing anything. Without a baseline, you won't know whether your changes helped.

**Build times:**
```bash
# Generates target/cargo-timings/cargo-timing.html (interactive Gantt chart)
cargo build --timings
```

Or run the bundled script: [`scripts/analyze-build-times.sh`](scripts/analyze-build-times.sh).

**Binary size:**
```bash
cargo bloat --release --crates   # install: cargo install cargo-bloat
ls -lh target/release/yourbinary
```

**Runtime memory:** DHAT (add `dhat = "0.3"` as a dev-dependency, instrument
with `#[global_allocator]`) or `heaptrack ./target/release/app [args]` (Linux).

**Test speed:** `time cargo test` vs `time cargo nextest run`
(`cargo install cargo-nextest`).

### Phase 3: Fix

Route to the relevant reference based on your diagnosis:

| Problem | Reference | Key technique |
|---------|-----------|---------------|
| Slow build | [build-optimization.md](references/build-optimization.md) | Linker + profiles |
| High runtime memory | [runtime-memory.md](references/runtime-memory.md) | Allocator + Cow + arenas |
| Binary size | [build-optimization.md](references/build-optimization.md) for LTO, [profiling-tools.md](references/profiling-tools.md) for strip + cargo-bloat | LTO + strip + cargo-bloat |
| Slow tests | [test-optimization.md](references/test-optimization.md) | nextest + structure |
| Too many deps | [dependency-optimization.md](references/dependency-optimization.md) | Feature flags + machete |
| Slow CI | [environment-config.md](references/environment-config.md) | Cache + nextest + no incremental |

### Phase 4: Verify

Re-run the same measurements from Phase 2 and document what changed.

```markdown
## Performance Results

**Build time**: X → Y seconds (Z% change)
**Binary size**: A → B MB
**Peak RSS**: C → D MB
**Test time**: E → F seconds

### Changes applied
- [what changed and why]

### What's still outstanding
- [remaining issues, if any]
```

Don't skip this. Stating that performance improved without measuring it isn't honest.

## Static Analysis

Run dependency auditing before reporting on dep health:

```bash
# Run the bundled audit script: scripts/audit-dependencies.sh
# Or individually:
cargo tree -d            # duplicate versions
cargo machete            # unused deps (stable)
cargo audit              # security advisories
cargo deny check         # licenses + duplicates (CI gate)
```

See [dependency-optimization.md](references/dependency-optimization.md) for the full toolchain.

Report actual measured numbers — don't say "this will be faster", say "build
time dropped from 45s to 28s after switching to mold". List what you changed,
what you verified, and what's still outstanding, and cite the source for
quantitative claims (tool output, benchmarks, or the Rust Performance Book).

## References

- [build-optimization.md](references/build-optimization.md) — Linker config, LTO, codegen-units, Cranelift, sccache, PGO, proc macros
- [runtime-memory.md](references/runtime-memory.md) — Smart pointers, enums, Cow, arenas, custom allocators
- [profiling-tools.md](references/profiling-tools.md) — cargo-bloat, DHAT, heaptrack, flamegraph, Criterion, Divan
- [test-optimization.md](references/test-optimization.md) — nextest, integration test structure, rstest
- [dependency-optimization.md](references/dependency-optimization.md) — Feature flags, alternatives, auditing tools
- [environment-config.md](references/environment-config.md) — Linux tuning, CI/CD, Docker (cargo-chef), Nix (crane)
- [Rust Performance Book](https://nnethercote.github.io/perf-book/)
- [Cargo Build Performance](https://doc.rust-lang.org/stable/cargo/guide/build-performance.html)
