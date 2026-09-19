---
name: rust-unsafe-ffi-review
description: "Reviews Rust unsafe code and FFI bindings for memory safety and soundness issues. Use when auditing unsafe blocks, FFI interfaces, or preparing Rust code for security-critical use."
version: 1.0.0
license: MIT
category: Testing
compatibility: opencode
metadata:
  audience: developers
  workflow: rust
---

# Rust Unsafe and FFI Review

Audit Rust code that uses `unsafe` or interfaces with C/C++. Soundness bugs here
become security issues, so nothing merges until it's proven sound — ideally
under Miri.

## When to use

- New `unsafe` blocks or FFI bindings that need soundness verification.
- Reviewing a PR that adds unsafe Rust or C interop.
- Auditing a crate before depending on it in a security-sensitive context.
- A fuzzer or sanitizer flagged a possible memory-safety issue.
- Wrapping a C library and verifying the safe API layer is actually sound.

## Dependency baseline (do this first)

Outdated deps are worse in unsafe/FFI contexts — sys crates (openssl-sys,
libsqlite3-sys) may carry known exploits, and unsafe code often depends on exact
library behaviour. Before reviewing the unsafe code, get the tree clean:

```bash
cargo install cargo-edit cargo-audit
cargo outdated          # should report all up to date
cargo upgrade && cargo update
cargo audit             # zero vulnerabilities
cargo test              # still green
```

## Critical patterns to check

The bad/good examples and per-rule checklists live in
[references/patterns.md](references/patterns.md). In summary:

- **ANSSI rules** — document every `unsafe` with a `// SAFETY:` comment;
  minimize `unsafe` scope; never `mem::uninitialized`/`zeroed` for non-ZST (use
  `MaybeUninit`); correct bounds on manual `Send`/`Sync`.
- **FFI patterns** — `#[repr(C)]` on all boundary types; null-check before
  deref; `catch_unwind` at every `extern "C"` boundary; ownership transfer via
  `Box::into_raw`/`from_raw`; C strings via `CString`.
- **Common bugs** — mutable aliasing (two `*mut` to the same memory), lifetime
  extension (casting away a lifetime), unaligned access after byte-buffer casts.

## Validation tools

- **Miri** — the arbiter. `rustup +nightly component add miri && cargo +nightly
  miri test`. Catches use-after-free, OOB, uninitialized reads, invalid pointer
  arithmetic, data races. **If Miri errors, the code isn't sound.**
- **Clippy restriction lints** — `cargo clippy -- -D
  clippy::undocumented_unsafe_blocks -D clippy::missing_safety_doc -D
  clippy::mem_forget -W clippy::cast_ptr_alignment -W
  clippy::multiple_unsafe_ops_per_block`.
- **cargo-geiger** — measures the unsafe surface across dependencies; minimize
  it.
- **cargo-audit / cargo-deny** — RustSec advisories and license/ban policy.
- **Test effectiveness (mandatory for unsafe)** — passing tests with weak
  assertions are the worst case here. Run `cargo mutants --in-diff <(git diff
  origin/main)` (any surviving mutant on an unsafe block means the `// SAFETY:`
  claim isn't tested) and a CRAP score via `cargo crap --lcov lcov.info`
  (threshold 30; an unsafe-containing function above it is a P0 finding). Full
  runbook: [references/test-effectiveness.md](references/test-effectiveness.md).
  Static-analysis tool setup: [references/static-analysis-tools.md](references/static-analysis-tools.md).

## Merge checklist

Don't merge unsafe code until all hold:

- **Docs:** `// SAFETY:` on every block explaining why it's sound; `# Safety`
  section on public unsafe fns; invariants documented.
- **Soundness:** Miri clean; no mutable aliasing; no lifetime extension; no
  uninitialized memory (`MaybeUninit`).
- **FFI:** `#[repr(C)]` on boundary types; null checks; panics caught at the
  boundary; paired create/destroy documented.
- **Testing:** unit tests on unsafe paths; Miri in CI; ASan/MSan clean where
  applicable; zero surviving mutants on changed unsafe/FFI lines; no
  unsafe-containing function scoring CRAP > 30.
- **Linting:** clippy restriction lints pass; cargo-geiger surface minimal;
  cargo-audit clean.

## Reporting

Be direct and specific — state what you found and where (file:line), not vague
summaries. Don't call an issue "fixed" until you've verified it (re-run Miri /
the mutant that was surviving).

## References

- [references/patterns.md](references/patterns.md) — ANSSI rules, FFI patterns, common bugs (bad/good examples)
- [references/static-analysis-tools.md](references/static-analysis-tools.md) — tool setup and configuration
- [references/test-effectiveness.md](references/test-effectiveness.md) — cargo-mutants + cargo-crap runbook for unsafe/FFI
- External: [Rust Nomicon](https://doc.rust-lang.org/nomicon/), [Miri](https://github.com/rust-lang/miri)
