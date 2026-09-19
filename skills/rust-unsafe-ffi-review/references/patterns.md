# Unsafe & FFI patterns and bugs

Reference detail for the `rust-unsafe-ffi-review` skill: the ANSSI rules, the
FFI safety patterns, and the common unsafe bugs, each with a bad/good example
and a check list.

## ANSSI secure-Rust rules

### Rule 1 — Document every `unsafe` block

Every `unsafe` block needs a `// SAFETY:` comment explaining *why* the operation
is sound and which invariants hold (validity, alignment, initialization, no
aliasing).

```rust
unsafe {
    // SAFETY: ptr is valid, aligned, points to an initialized T, and is not
    // mutably aliased anywhere else.
    *ptr = value;
}
```

### Rule 2 — Minimize `unsafe` scope

Keep only the operation that actually needs `unsafe` inside the block; move safe
calls out. Don't wrap safe code in `unsafe`.

### Rule 3 — No `mem::uninitialized` / `mem::zeroed` for non-ZST

Use `MaybeUninit<T>`; only call `assume_init()` after fully initializing.

```rust
let mut x = MaybeUninit::<T>::uninit();
// initialize x ...
let x = unsafe { /* SAFETY: fully initialized above */ x.assume_init() };
```

### Rule 4 — Verify `Send`/`Sync`

Manual `unsafe impl Send/Sync` must carry the correct bounds
(`unsafe impl<T: Send> Send for MyType<T> {}`), or use `PhantomData<T>` to
inherit auto-trait behaviour from owned data behind raw pointers.

## FFI safety patterns

### `#[repr(C)]` for FFI types

All structs crossing an `extern "C"` boundary need `#[repr(C)]` (Rust's default
layout is unspecified). Null-check every pointer before dereferencing; keep
Rust-specific types out of `extern "C"` signatures.

### Catch panics at the boundary

Wrap FFI function bodies in `std::panic::catch_unwind` and return an error code —
a panic unwinding into C is undefined behaviour.

### Ownership transfer via `Box`

Return heap objects with `Box::into_raw`, and free them with `Box::from_raw` in a
paired `destroy_*` function. Never return a pointer to a stack local.

### C strings via `CString`

Return C strings with `CString::new(...).into_raw()` and free with
`CString::from_raw` — guarantees the null terminator and correct deallocation.

## Common unsafe bugs

- **Mutable aliasing** — two `&mut`/`*mut` to the same memory live at once (e.g.
  two `as_mut_ptr()` writes). Undefined behaviour; use a single mutable path or
  `split_at_mut`.
- **Lifetime extension** — transmuting or casting away a lifetime so a reference
  outlives its owner. Tie returned references to the owner's lifetime.
- **Unaligned access** — dereferencing a pointer that doesn't meet `T`'s
  alignment (common after byte-buffer casts); use `read_unaligned`/
  `write_unaligned` or ensure alignment.

Each has the same remedy shape: narrow the `unsafe`, document the invariant, and
prove it holds under Miri.
