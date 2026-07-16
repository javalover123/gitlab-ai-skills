# Rust Compilation Memory — command sequences

The full profiling commands for each phase. See `SKILL.md` for when to run them.

## Baseline profiling

Determine scope:

```bash
cargo metadata --format-version 1 | jq '.workspace_members | length'
# <= 3 crates: profile the whole workspace
# >  3 crates: profile per-crate (loop below)
```

Whole-workspace:

```bash
cargo clean

CARGO_PROFILE_RELEASE_DEBUG=true cargo rustc --release -- \
  -Z self-profile=rustc-profile \
  -Z self-profile-events=default,args

heaptrack cargo build --release           # Linux only

cargo llvm-lines --release > llvm-lines-baseline.txt
```

Per-crate (workspaces > 3 crates):

```bash
for crate in $(cargo metadata --format-version 1 | jq -r '.workspace_members[] | split(" ")[0]'); do
  echo "Profiling $crate..."
  cargo clean -p "$crate"

  CARGO_PROFILE_RELEASE_DEBUG=true cargo rustc -p "$crate" --release -- \
    -Z self-profile="profile-$crate" \
    -Z self-profile-events=default,args

  if command -v heaptrack >/dev/null 2>&1; then
    heaptrack -o "heaptrack-$crate" cargo build -p "$crate" --release
  fi

  cargo llvm-lines -p "$crate" --release > "llvm-lines-$crate.txt"
done
```

## Analysis / visualization

```bash
crox rustc-profile.mm_profdata > trace.json                                    # Chrome tracing
inferno-collapse-cargo rustc-profile.mm_profdata | inferno-flamegraph > flamegraph.svg
heaptrack_print heaptrack.cargo.*.zst > heaptrack-report.txt                   # or heaptrack_gui
```

Read from the outputs:

- **heaptrack** — peak RSS, allocation hotspots, temporary-allocation churn.
- **llvm-lines** — top IR generators; a function appearing 50+ times is a
  monomorphization explosion.
- **trace.json** (Chrome DevTools Performance tab) — LLVM passes, type checking
  of large types, codegen bottlenecks.

## Validation (re-profile after refactoring)

```bash
cargo clean

CARGO_PROFILE_RELEASE_DEBUG=true cargo rustc --release -- \
  -Z self-profile=rustc-profile-after \
  -Z self-profile-events=default,args

heaptrack -o heaptrack-after cargo build --release
heaptrack_print heaptrack-after.*.zst > heaptrack-report-after.txt
cargo llvm-lines --release > llvm-lines-after.txt

echo "Before: $(grep 'peak heap memory' heaptrack-report.txt)"
echo "After:  $(grep 'peak heap memory' heaptrack-report-after.txt)"
echo "Before: $(head -1 llvm-lines-baseline.txt)"
echo "After:  $(head -1 llvm-lines-after.txt)"
```

Disable incremental compilation while profiling: `export CARGO_INCREMENTAL=0`.
