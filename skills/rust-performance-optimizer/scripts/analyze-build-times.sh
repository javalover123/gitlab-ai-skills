#!/usr/bin/env bash
# Runs cargo build --timings and reports the slowest crates.
# Also runs cargo llvm-lines if available, for monomorphization analysis.

set -euo pipefail

echo "=== Build Timing Analysis ==="
echo ""
echo "Running cargo build --timings (generates HTML report)..."
cargo build --timings 2>&1 | grep -E "^(Compiling|Finished|error)" | tail -5 || true
echo ""
echo "Report written to: target/cargo-timings/cargo-timing.html"
echo "Open it in a browser for an interactive Gantt chart showing:"
echo "  - Which crates are on the critical path"
echo "  - How much parallelism is happening"
echo "  - Which crates take the longest"
echo ""

# Run cargo llvm-lines if available
if cargo llvm-lines --version &>/dev/null 2>&1; then
    echo "=== Top Monomorphization Sources (cargo llvm-lines) ==="
    echo "(High 'Copies' count = excessive generic instantiation)"
    echo ""
    cargo llvm-lines 2>/dev/null | head -25
    echo ""
    echo "Fix high-copy functions with: dyn Trait, #[inline(never)],"
    echo "or extracting non-generic inner functions."
else
    echo "=== Monomorphization Analysis ==="
    echo "Install cargo-llvm-lines to see monomorphization hotspots:"
    echo "  cargo install cargo-llvm-lines"
    echo "Then run: cargo llvm-lines | head -20"
fi
