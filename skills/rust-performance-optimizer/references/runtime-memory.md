# Runtime Memory Reference

Covers smart pointer overhead, enum layout, Cow and zero-copy patterns, arena allocators, custom global allocators, and Vec/String patterns.

---

## Smart Pointer Overhead

On 64-bit systems (stack size of the pointer itself):
- `Box<T>`: 8 bytes (one pointer)
- `Rc<T>` and `Arc<T>`: also 8 bytes on the stack (a single thin pointer). They add 16 bytes of *heap* overhead — the strong and weak reference counts stored alongside the value.
- `Option<Box<T>>`: still just 8 bytes — niche optimization makes `None` the null pointer

The niche optimization also applies to `Option<&T>`, `Option<NonZeroU64>`, and similar. Use these freely — they're zero-overhead.

## Small Collection Crates

Avoid heap allocation for collections that are usually small:

| Crate | Behavior | Best for |
|-------|----------|----------|
| `SmallVec<[T; N]>` | Inline up to N, spills to heap | Collections usually small, sometimes large |
| `ArrayVec<T, N>` | Fixed capacity N, never heaps | Known maximum size |
| `TinyVec<[T; N]>` | Like SmallVec, 100% safe code | Safety-critical code |
| `compact_str` | Strings ≤24 bytes stored inline | Parsing, many short strings |
| `smol_str` | Strings ≤23 bytes inline, O(1) clone | Tokens, identifiers |

`SmallVec` is used heavily in rustc and Servo. **Caveat**: For standalone use, `Vec::with_capacity(N)` often beats `SmallVec` due to branch-checking overhead. Always benchmark before adopting.

---

## Enum Layout

Rust's default repr reorders struct fields to minimize padding. A struct `{u8, u32, u16}` is 8 bytes (reordered to `u32, u16, u8, padding`) vs 12 bytes with `#[repr(C)]`.

**Boxing large enum variants** is critical. An enum with a 1024-byte variant forces every instance to be 1032+ bytes. Box the variant:

```rust
// Before: every MyEnum is 1032+ bytes
enum MyEnum {
    Small(u8),
    Large([u8; 1024]),
}

// After: every MyEnum is 16 bytes
enum MyEnum {
    Small(u8),
    Large(Box<[u8; 1024]>),
}
```

**`#[repr(u8)]` or `#[repr(C)]` disables niche optimization.** Only use these when FFI compatibility is required.

Use `-Zprint-type-sizes` (nightly) to audit type layouts.

---

## Cow and Zero-Copy

`Cow<'_, str>` avoids allocation when data passes through unmodified:

```rust
fn process(input: &str) -> Cow<'_, str> {
    if input.contains("bad") {
        Cow::Owned(input.replace("bad", "good"))  // allocates only when needed
    } else {
        Cow::Borrowed(input)  // zero allocation
    }
}
```

**Zero-copy deserialization** with serde's `#[serde(borrow)]` borrows `&str` directly from the input buffer. JSON supports this only for strings without escape sequences. Binary formats (bincode, postcard) support full zero-copy.

For true zero-copy access, **rkyv** provides O(1) deserialization regardless of data size. Apache Iggy benchmarks showed 2× read throughput and 2× better p99 latency after switching.

---

## Arena Allocators

**Bumpalo** performs bump allocation in ~11 instructions on the fast path — 2–10× faster than the global allocator for many small, short-lived allocations:

```rust
use bumpalo::Bump;

let bump = Bump::new();
let node = bump.alloc(AstNode { .. });  // fast path
// All memory freed when bump is dropped
```

Ideal for: compiler passes, per-request web server processing, graph structures where everything is freed together.

---

## Custom Global Allocators

For multi-threaded server workloads, switching the global allocator can meaningfully improve throughput:

| Allocator | Best for | Typical improvement |
|-----------|----------|-------------------|
| `tikv-jemallocator` | Long-running servers, fragmentation resistance | 10–20% for multi-threaded |
| `mimalloc` | General throughput, musl targets | 7.6% (glibc), 92% (musl) |
| System | Simple programs, no C compiler needed | Baseline |

**Setup:**
```toml
# Cargo.toml
[target.'cfg(not(target_env = "msvc"))'.dependencies]
tikv-jemallocator = "0.6"
```

```rust
#[cfg(not(target_env = "msvc"))]
#[global_allocator]
static GLOBAL: tikv_jemallocator::Jemalloc = tikv_jemallocator::Jemalloc;
```

---

## Vec and String Patterns

`Vec` doubles capacity on growth, potentially wasting up to 50% of allocated memory. Key patterns:

- `Vec::with_capacity(n)` — eliminates ~14 reallocations for 10K elements when size is known
- `shrink_to_fit()` — reclaims unused capacity after population
- `into_boxed_slice()` — drops the capacity field (saves 8 bytes per collection; significant for `Vec<Vec<T>>`)

**`LazyLock`** (stable since Rust 1.80) replaces `lazy_static!` for deferred global initialization:

```rust
use std::sync::LazyLock;

static CONFIG: LazyLock<HashMap<&str, &str>> = LazyLock::new(|| {
    let mut m = HashMap::new();
    m.insert("log_level", "info");
    m
});
```

---

## Profiling Tools for Runtime Memory

- **DHAT** (`dhat` crate): Rust-native heap profiler. Add `dhat = "0.3"` as dev-dep, use `#[global_allocator]`. Output viewed at nnethercote.github.io/dh_view. Supports heap assertions in tests: `dhat::assert!(stats.max_bytes <= 10_000_000)`.
- **heaptrack**: Linux GUI profiler tracking all allocations over time. High overhead — may OOM on memory-intensive workloads.
- **Bytehound**: LD_PRELOAD-based with web UI at localhost:8080. Tracks allocations, deallocations, mmap calls.
- **`memory-stats` crate**: Lightweight RSS monitoring via `memory_stats().physical_mem`.

See [profiling-tools.md](profiling-tools.md) for full usage details.

---

## Resources

- [Rust Performance Book — Memory](https://nnethercote.github.io/perf-book/heap-allocations.html)
- [DHAT: a Dynamic Heap Analysis Tool](https://valgrind.org/docs/manual/dh-manual.html)
- [rkyv zero-copy deserialization](https://rkyv.org/)
