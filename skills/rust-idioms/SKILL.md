---
name: rust-idioms
description: "Write, review, and refactor Rust so it survives review: Result instead of panics on caller misuse, reuse of existing helpers, no dead API, typed values over strings and magic numbers, and iterator and allocation choices. Use when adding or changing .rs files, implementing a Rust feature or fix, or reviewing a Rust change. Not for repo-wide quality or tech-debt passes (refactor), unsafe/FFI (rust-unsafe-ffi-review), build speed or runtime perf (rust-performance-optimizer), compile memory (rust-compile-memory), Cargo/CI config, or non-Rust code."
version: 1.0.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: rust
---

# Rust idioms

Use when writing or reviewing Rust in any crate. Project rules (AGENTS.md,
lint config) win. This covers what the compiler and `clippy::all` mostly miss.

## Before you write

1. **Reuse first.** Before adding a helper, type, or constant, look for the
   concept in the crate (code index or LSP for definitions and callers, `rg`
   for literal text). Extend or call what exists. A second copy of a check
   is a smell; a third is a bug.
2. **No dead API.** Every new `pub` or `pub(crate)` item needs a caller in
   the same change (a test or doc example counts), or it does not ship. No
   "for later" methods, builders, or getters. Start private; widen only when
   something outside needs it.
3. **Parse, don't re-check.** Validate at the boundary and hand inner code a
   typed value (see [types](references/types.md)). Inner code never
   re-validates and never silently repairs bad input.
4. **Failures are values.** If a caller can reach it, return `Result` or
   `Option`; don't panic. `assert!`, `expect`, `unwrap`, and slice
   indexing on caller-controlled input are bugs, including "use after
   shutdown/close", "empty input", and "index out of range". Panic only when
   your own invariant is broken and a message states it.
5. **Check the shape of the data.** Pick collections for the access pattern
   ([iterators](references/iterators.md)).

## Typed values (details: [types](references/types.md))

- Closed set of strings or integers: `enum` with `FromStr`/`TryFrom`,
  `match` without a `_ =>` arm so new variants break the build.
- Same-primitive values that must not be mixed (ids, units): a newtype.
  Repeated literal: a named `const`, defined once.
- Mode-selecting booleans: an enum. "May be absent": `Option<T>`, not a
  sentinel (`""`, `-1`).
- Return owned types only when the callee creates the data; else borrow.

## Allocation and iterators (details: [iterators](references/iterators.md))

- Return `impl Iterator` (or take `impl IntoIterator`) instead of building a
  `Vec` that the caller immediately loops over or filters.
- One pass: chain adapters, `collect` once, at the end.
- Reserve capacity or use `collect` when the size is known; no
  `Vec::contains` in a loop (quadratic), use a set or map.
- `clone()` to satisfy the borrow checker is a design signal: restructure,
  borrow, or move first; clone where ownership is genuinely needed.
  `mem::take`/`Option::take` move a field out.

## Errors in short

- Library code: a small `enum` error implementing `Display` and `Error`
  with `source()`; a manual `From` impl (or `thiserror`'s `#[from]`) plus
  `?` to convert. Binary glue may use a boxed or context-carrying error.
- Never swallow: `.ok()`, `unwrap_or_default()`, `let _ =` on a `Result`
  hide failures. Propagate, log and continue deliberately, or document why
  ignoring is correct (`#[expect(..., reason = "...")]`).
- Keep the source error when mapping; do not replace it with a string.
- Channel disconnect and closed handles are normal states of a public API:
  model them in the return type.
- Lock poisoning means another thread already panicked. Propagate the
  panic (`expect` with a message), recover with `into_inner` when the data
  stays valid, or return an error only when callers can act on it.

## Lints that are not in `clippy::all`

`clippy::unwrap_used`, `expect_used`, `indexing_slicing`, `panic`,
`let_underscore_must_use`, `unreachable`. Avoid them in non-test code even if
the project does not enable them. Mark an infallible invariant with
`#[expect(clippy::expect_used, reason = "...")]`.

## When done

Re-read the diff as a reviewer: duplicate helper? Unused item? String where
an enum fits? Eager `collect`? Panic reachable from a public function? Fix,
then run the project's lint and tests.

## Further reading

[Rust API Guidelines](https://rust-lang.github.io/api-guidelines/), [*The Rust
Programming Language*](https://doc.rust-lang.org/book/) ch. 6, 9, 13, [Rust
design patterns](https://rust-unofficial.github.io/patterns/). Attribution:
[NOTICE](references/NOTICE.md).

## Contributing Improvements

This skill is maintained in [`gitlab-org/ai/skills`](https://gitlab.com/gitlab-org/ai/skills).
If any guidance here is **inaccurate or outdated** (e.g. a renamed lint), confirm
with the user and open an MR against that repository with the fix. Keep changes
focused — one fix per MR.
