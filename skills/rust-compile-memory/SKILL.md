---
name: rust-compile-memory
description: "Profiles Rust compilation memory usage with rustc nightly and measureme tools, identifies high-memory patterns (monomorphization, large types, LLVM bottlenecks), and refactors code to reduce compilation RSS. Use when Rust builds trigger the OOM killer or consume excessive memory. Triggers: compilation memory, rustc OOM, reduce compile memory, profile compilation."
version: 1.0.1
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: rust
---

# Rust Compilation Memory Profiling and Optimization

When rustc starts eating gigabytes of RAM and the OOM killer shows up, profile
what's consuming memory during compilation and refactor the code to bring it
down.

**Requirements:** Rust nightly (for `-Z self-profile`); `heaptrack` is
Linux-only (on macOS use Instruments or valgrind); Nix recommended but not
required. Tool setup — including a ready-to-use `flake.nix` and the rustup
fallback — is in [references/tool-installation.md](references/tool-installation.md).

## When to use

- The OOM killer terminates rustc during builds, or RSS exceeds ~8 GB.
- Incremental or CI builds crash under memory pressure.
- Multi-crate workspaces where some crates consume excessive memory.
- Generic-heavy code causing a monomorphization explosion.

## Workflow

### Phase 1 — Environment

Switch to nightly (via the Nix flake or `rustup toolchain install nightly`) and
install `heaptrack`, `cargo-llvm-lines`, and `inferno`. See
[references/tool-installation.md](references/tool-installation.md).

### Phase 2 — Baseline profiling

**Pre-flight — rule out non-code causes that dominate the numbers:**

- **Disk free** (`df -h .`) — a `target/` partition past ~95% fails with "No
  space left" that reads like OOM downstream.
- **Unpinned toolchain** — without a `rust-toolchain.toml`, `rustup update`
  silently invalidates every fingerprint; pin `channel = "nightly-YYYY-MM-DD"`.
- **Profile-hash duplication** — a dep built under multiple profile lineages
  (`build` + `test` + `check`) doubles peak RSS; see the
  `[profile.test.package."*"]` mirror fix in
  [references/refactoring-strategies.md](references/refactoring-strategies.md#unify-per-package-overrides-across-profiles).

Scope by workspace size (`cargo metadata --format-version 1 | jq
'.workspace_members | length'`): ≤3 crates profile the whole workspace, >3
profile per-crate. Collect three baselines on a clean build — self-profile
(`cargo rustc --release -- -Z self-profile=… -Z self-profile-events=default,args`),
heaptrack (Linux), and `cargo llvm-lines`. Exact commands (incl. the per-crate
loop): [references/commands.md](references/commands.md).

### Phase 3 — Analysis

Turn the data into views: `crox …mm_profdata > trace.json` (Chrome DevTools),
`inferno-*` for a flamegraph, `heaptrack_print`/`heaptrack_gui` for allocations.
Look for peak RSS and allocation hotspots (heaptrack), monomorphization
explosion — a generic function instantiated 50+ times (`llvm-lines`), and LLVM
pass / type-checking / codegen bottlenecks (trace). Categorize findings by crate
and root cause (monomorphization / large types / LLVM backend).

### Phase 4 — Refactoring

Apply the pattern that matches each hotspot. Full before/after examples:
[references/refactoring-strategies.md](references/refactoring-strategies.md).

| Symptom | Pattern |
|---|---|
| Large enum slows type-checking | Split into grouped sub-enums |
| Large struct fields | `Box` the large fields |
| Same generic instantiated many times | Extract the non-generic body into a plain fn |
| Many trait impls monomorphized | Use `&dyn Trait` dynamic dispatch |
| Combinatorial feature gates | Consolidate the feature matrix |
| `lazy_static!` heavy init | Replace with `OnceCell::get_or_init` |

For each hotspot: read the source, pick the pattern (monomorphization → dynamic
dispatch / extract non-generic; large types → split / box), apply it, then
`cargo test` and re-profile to confirm the reduction.

`scripts/detect-patterns.sh` scans a crate for these patterns to prioritize.

### Phase 5 — Validation

Re-profile on a clean build with the same Phase 2 commands, then compare peak
RSS and top `llvm-lines` before/after. Report **actual measured numbers**, not
estimates — don't claim an improvement until the post-refactoring profile shows
lower peak RSS than the baseline. Note which hotspots remain.

**Done when:** nightly active; tools installed; baseline collected; hotspots
categorized; patterns applied to the top offenders; `cargo test` passes;
post-refactoring profile shows a measured reduction; before/after numbers
documented.

## Notes

- Disable incremental compilation while profiling (`CARGO_INCREMENTAL=0`).
- Profile **release** builds (where memory matters most) with
  `CARGO_PROFILE_RELEASE_DEBUG=true` for symbols without full debug overhead.

## References

- [references/tool-installation.md](references/tool-installation.md) — toolchain + profiler setup, flake.nix
- [references/commands.md](references/commands.md) — full profiling command sequences
- [references/refactoring-strategies.md](references/refactoring-strategies.md) — detailed refactoring techniques
- [scripts/detect-patterns.sh](scripts/detect-patterns.sh) — pattern-detection scan
- External: [rustc profiling guide](https://rustc-dev-guide.rust-lang.org/profiling.html), [measureme](https://github.com/rust-lang/measureme), [heaptrack](https://github.com/KDE/heaptrack), [cargo-llvm-lines](https://github.com/dtolnay/cargo-llvm-lines)
