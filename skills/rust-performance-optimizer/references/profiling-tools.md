# Profiling Tools Reference

Covers binary size analysis, heap profiling, CPU profiling, and benchmarking tools for Rust projects.

---

## Binary Size Analysis

### cargo-bloat

Shows per-crate `.text` section contribution. Install: `cargo install cargo-bloat`.

```bash
# Per-crate breakdown
cargo bloat --release --crates

# Per-function (find largest individual functions)
cargo bloat --release -n 20
```

### cargo-llvm-lines

Counts LLVM IR lines per function, revealing monomorphization bloat. High "Copies" values mean too many generic instantiations.

```bash
cargo install cargo-llvm-lines
cargo llvm-lines | head -20
```

Fix high-copy functions with `dyn Trait`, `#[inline(never)]`, or extracting non-generic inner functions from generic wrappers.

### Binary stripping

In `Cargo.toml`:
```toml
[profile.release]
strip = "symbols"    # Removes debug symbols; significant size reduction
```

Or post-build: `strip target/release/mybinary`

---

## CPU Profiling

### cargo flamegraph

Wraps `perf` for one-command CPU profiling. Install: `cargo install flamegraph`.

```bash
# Generate flamegraph.svg in the current directory
RUSTFLAGS="-C force-frame-pointers=yes" cargo flamegraph --bin app
```

Open `flamegraph.svg` in a browser. Wide boxes = hot code paths.

**Platform notes**: Requires `perf` on Linux (available in most distros as `linux-tools-generic`). On macOS, uses `dtrace` instead.

### cargo build --timings

Shows per-crate compilation time and parallelism in an interactive HTML Gantt chart.

```bash
cargo build --timings
# Opens target/cargo-timings/cargo-timing.html
```

Look for crates on the critical path (no parallel work happening above them) — those are where build time wins are.

---

## Heap Profiling

### DHAT (Rust-native)

Add to `Cargo.toml`:
```toml
[dev-dependencies]
dhat = "0.3"
```

```rust
#[cfg(test)]
#[global_allocator]
static ALLOC: dhat::Alloc = dhat::Alloc;

#[test]
fn test_memory_usage() {
    let _profiler = dhat::Profiler::new_heap();
    // ... run code ...
    let stats = dhat::HeapStats::get();
    dhat::assert!(stats.max_bytes <= 10_000_000);
}
```

Output is JSON — view at nnethercote.github.io/dh_view.

### heaptrack (Linux)

Tracks all allocations over time with a GUI. Install via package manager (`heaptrack`).

```bash
heaptrack ./target/release/app [args]
heaptrack_gui heaptrack.app.*.zst  # GUI analysis
# Or text report:
heaptrack_print heaptrack.app.*.zst > report.txt
```

High overhead — may OOM on memory-intensive workloads. Use on a representative but not maximum-load run.

### Bytehound (Linux)

LD_PRELOAD-based profiler with a web UI.

```bash
LD_PRELOAD=/path/to/libbytehound.so ./target/release/app [args]
# View at http://localhost:8080
```

Tracks allocations, deallocations, and mmap calls.

### memory-stats crate

For lightweight runtime RSS monitoring without instrumentation overhead:

```toml
[dependencies]
memory-stats = "1.0"
```

```rust
use memory_stats::memory_stats;
if let Some(usage) = memory_stats() {
    println!("Physical: {} MB", usage.physical_mem / 1_048_576);
}
```

---

## Benchmarking

### Criterion (full-featured)

Statistical analysis, change detection, HTML reports. Industry standard for Rust micro-benchmarks.

```toml
[dev-dependencies]
criterion = "0.5"

[[bench]]
name = "my_bench"
harness = false
```

```rust
use criterion::{criterion_group, criterion_main, Criterion};

fn bench_something(c: &mut Criterion) {
    c.bench_function("my_function", |b| b.iter(|| my_function()));
}

criterion_group!(benches, bench_something);
criterion_main!(benches);
```

Run with `cargo bench`.

### Divan (simpler, stable since 1.80)

Attribute-based benchmarking with built-in `AllocProfiler` for counting allocations.

```toml
[dev-dependencies]
divan = "0.1"
```

```rust
#[divan::bench]
fn my_bench() {
    // ... code to benchmark ...
}

fn main() {
    divan::main();
}
```

Divan's `AllocProfiler` counts allocations per benchmark run, useful for tracking allocation regressions alongside latency.

---

## Quick Selection Guide

| Goal | Tool |
|------|------|
| Which crate is making my binary large? | `cargo bloat --crates` |
| Which generic is exploding with copies? | `cargo llvm-lines` |
| Which function is slowest at runtime? | `cargo flamegraph` |
| Which crate takes the longest to compile? | `cargo build --timings` |
| Where are my heap allocations? | DHAT (any platform) or heaptrack (Linux) |
| How fast is this function? | Criterion (full stats) or Divan (quick) |

---

## Resources

- [Rust Performance Book — Profiling](https://nnethercote.github.io/perf-book/profiling.html)
- [cargo-bloat](https://github.com/RazrFalcon/cargo-bloat)
- [cargo flamegraph](https://github.com/flamegraph-rs/flamegraph)
- [Criterion.rs](https://bheisler.github.io/criterion.rs/book/)
- [Divan](https://github.com/nvzqz/divan)
