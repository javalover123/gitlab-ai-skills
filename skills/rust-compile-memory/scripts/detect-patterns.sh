#!/usr/bin/env bash
# Pattern detection script for high-memory Rust compilation patterns
#
# Usage: bash detect-patterns.sh [path-to-rust-project]
#
# Detects:
# - Large enum types
# - Heavy generic instantiation
# - Large stack frames
# - Macro expansion issues
# - Feature combination explosions

set -Eeuo pipefail

PROJECT_DIR="${1:-.}"

echo "=== Rust Compilation Memory Pattern Detection ==="
echo "Project: $PROJECT_DIR"
echo ""

cd "$PROJECT_DIR"

# Check if this is a Rust project
if [ ! -f "Cargo.toml" ]; then
    echo "Error: Not a Rust project (no Cargo.toml found)"
    exit 1
fi

# Pattern 1: Large enum types
echo "## Pattern 1: Large Enum Types"
echo "Looking for enums with 20+ variants..."

if command -v rg &> /dev/null; then
    # Use ripgrep if available
    enum_files=$(rg -t rust "^pub enum" -l || true)

    for file in $enum_files; do
        enum_name=$(rg "^pub enum (\w+)" -or '$1' "$file" || true)
        variant_count=$(rg "^\s+\w+.*," -c "$file" || echo "0")

        if [ "$variant_count" -gt 20 ]; then
            echo "  ⚠️  $file: enum $enum_name has $variant_count variants"
            echo "      → Consider splitting into smaller enums"
        fi
    done
else
    echo "  ℹ️  Install ripgrep for better detection"
fi

echo ""

# Pattern 2: Generic function instantiations
echo "## Pattern 2: Generic Instantiation Hotspots"
echo "Analyzing LLVM IR generation..."

if command -v cargo &> /dev/null && command -v cargo-llvm-lines &> /dev/null; then
    # Run cargo-llvm-lines and show top 10
    echo "  Running cargo llvm-lines (this may take a while)..."

    cargo llvm-lines --release 2>/dev/null | head -n 15 || {
        echo "  ⚠️  cargo llvm-lines failed (project may not build)"
    }

    echo ""
    echo "  Functions with >50 copies indicate monomorphization issues"
    echo "  → Consider extracting non-generic code or using dynamic dispatch"
else
    echo "  ℹ️  Install cargo-llvm-lines: cargo install cargo-llvm-lines"
fi

echo ""

# Pattern 3: Large stack frames
echo "## Pattern 3: Large Stack Frames"
echo "Looking for large struct definitions..."

if command -v rg &> /dev/null; then
    # Find structs with many fields (proxy for large size)
    struct_files=$(rg -t rust "^pub struct" -l || true)

    for file in $struct_files; do
        field_count=$(rg "^\s+\w+:\s+" -c "$file" || echo "0")

        if [ "$field_count" -gt 20 ]; then
            struct_name=$(rg "^pub struct (\w+)" -or '$1' "$file" || true)
            echo "  ⚠️  $file: struct $struct_name has $field_count fields"
            echo "      → Consider boxing large fields"
        fi
    done

    # Look for explicit stack size warnings in build logs
    echo ""
    echo "  To check actual stack frame sizes, build and look for warnings:"
    echo "  RUSTFLAGS='-C opt-level=z' cargo build 2>&1 | grep 'stack space'"
else
    echo "  ℹ️  Install ripgrep for detection"
fi

echo ""

# Pattern 4: Macro expansion
echo "## Pattern 4: Heavy Macro Usage"
echo "Looking for recursive macros..."

if command -v rg &> /dev/null; then
    # Find macro_rules definitions that call themselves
    macro_files=$(rg -t rust "macro_rules!" -l || true)

    for file in $macro_files; do
        # Check for recursive macro patterns
        if rg -q "macro_rules! (\w+).*\1!" "$file" 2>/dev/null; then
            echo "  ⚠️  $file: contains recursive macros"
            echo "      → Consider proc macros or generic implementations"
        fi
    done

    # Count derive macros (serde is particularly heavy). `rg -c .` against a
    # directory prints one `path:count` line per file, so sum the counts.
    derive_count=$(rg -t rust "#\[derive\(" -c . 2>/dev/null | awk -F: '{sum+=$NF} END {print sum+0}')
    echo ""
    echo "  Found $derive_count derive macro usages"
    if [ "$derive_count" -gt 100 ]; then
        echo "  ⚠️  High derive usage may impact compile times"
        echo "      → Profile which derives are expensive"
    fi
else
    echo "  ℹ️  Install ripgrep for detection"
fi

echo ""

# Pattern 5: Feature combinations
echo "## Pattern 5: Feature Complexity"

if [ -f "Cargo.toml" ]; then
    feature_count=$(rg '^\[features\]' -A 100 Cargo.toml | rg '^\w+\s*=' -c || echo "0")
    echo "  Found $feature_count features in Cargo.toml"

    if [ "$feature_count" -gt 10 ]; then
        echo "  ⚠️  Many features create exponential build matrix"
        echo "      → Consider feature groups or simplification"
    fi

    # Check for feature combinations in code (sum per-file counts, as above).
    cfg_count=$(rg -t rust '#\[cfg\(.*feature.*\)\]' -c . 2>/dev/null | awk -F: '{sum+=$NF} END {print sum+0}')
    echo "  Found $cfg_count feature gates in code"

    if [ "$cfg_count" -gt 50 ]; then
        echo "  ⚠️  Heavy feature gating may create many compilation units"
    fi
fi

echo ""

# Pattern 6: Dependency analysis
echo "## Pattern 6: Dependency Complexity"

if command -v cargo &> /dev/null; then
    # Check for duplicate dependencies
    duplicates=$(cargo tree --duplicates 2>/dev/null | grep -c -v "^$" || echo "0")

    if [ "$duplicates" -gt 0 ]; then
        echo "  ⚠️  Found duplicate dependency versions:"
        cargo tree --duplicates 2>/dev/null || true
        echo "      → Unify dependency versions to reduce compilation"
    else
        echo "  ✓ No duplicate dependencies found"
    fi

    echo ""

    # Count total dependencies
    total_deps=$(cargo tree --depth 1 2>/dev/null | wc -l || echo "0")
    echo "  Total dependencies: $total_deps"

    if [ "$total_deps" -gt 100 ]; then
        echo "  ⚠️  Large dependency tree"
        echo "      → Review if all dependencies are necessary"
    fi
fi

echo ""
echo "=== Pattern Detection Complete ==="
echo ""
echo "Next Steps:"
echo "1. Review warnings above"
echo "2. Run full profiling: bash ../scripts/profile-workspace.sh"
echo "3. Apply refactoring patterns from references/refactoring-strategies.md"
echo "4. Re-profile to measure improvement"
