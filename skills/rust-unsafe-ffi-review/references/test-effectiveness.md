# Test effectiveness for unsafe and FFI code

Unsafe Rust with passing tests but weak assertions is the worst of both worlds — the type system isn't protecting you, and neither is the suite. Two mechanical checks close that gap. Both are mandatory before any unsafe code merges.

## cargo-mutants — does any test actually catch the bug?

Mutation testing inserts small wrong changes (`==` → `!=`, `Ok(x)` → `Err(...)`, delete a negation, drop a side effect) and reports any mutant that didn't cause a test to fail. A surviving mutant on an unsafe line means your test suite can't tell whether the `// SAFETY:` claim is actually upheld.

**Install:**

```bash
cargo install --locked cargo-mutants
```

**Per-PR invocation (recommended — only mutates changed lines):**

```bash
cargo mutants --in-diff <(git diff origin/main) --timeout-multiplier 2.0
```

**Target a specific unsafe-heavy file:**

```bash
cargo mutants --file crates/foo-sys/src/ffi.rs
```

**Reading the output:**

| Outcome | Meaning |
|---------|---------|
| `CAUGHT` | A test failed for the mutant — good |
| `PASS` (or `MISSED`) | Mutant survived — test gap on that line |
| `TIMEOUT` | Raise `--timeout-multiplier`; if it persists, the test's too slow at this layer |
| `UNVIABLE` | Mutant produced uncompilable code — ignore |

When you run cargo-mutants, read the surviving mutants rather than just the
count: a survivor is a line the suite can't constrain. For unsafe code, a
survivor on an `unsafe` block means the `// SAFETY:` claim isn't backed by a
test — write the test that would fail if the invariant were violated, then
re-run.

**What to check for unsafe code specifically:**

- Zero surviving mutants on unsafe blocks themselves
- Zero surviving mutants on FFI null-check branches (`if ptr.is_null() { return ...; }`)
- Zero surviving mutants on length-check branches (`if len > MAX { return Err(...); }`)
- Zero surviving mutants on alignment / repr conversion lines

If a mutant survives on an unsafe boundary, your fix is to **add an assertion that kills it** — not to add more unsafe blocks. The kill assertion is the contract test for the unsafe invariant.

## cargo-crap — where's the dangerous undertested complexity?

CRAP (Change Risk Anti-Patterns, Savoia & Evans 2007) flags code that's both complex *and* undertested. For unsafe Rust that's a five-alarm signal — high-cyclomatic unsafe with low coverage is exactly where soundness bugs hide.

The formula:

```
CRAP(m) = comp(m)² × (1 − cov(m)/100)³ + comp(m)
```

The squared complexity and cubed coverage-deficit make the score explode for the worst offenders. Conventional threshold: **30**. Anything above is a refactor candidate that needs tests before changes.

**Install:**

```bash
cargo install cargo-llvm-cov cargo-crap
```

**Generate the report:**

```bash
cargo llvm-cov --lcov --output-path lcov.info
cargo crap --lcov lcov.info             # default threshold 30
```

**SARIF for CI dashboards:**

```bash
cargo crap --lcov lcov.info --format sarif > crap.sarif
```

**What to check:**

- No `unsafe fn` or function containing `unsafe { }` scores above 30 — if it does, add tests before merge or split the function
- Any unsafe code in the top-10 CRAP list is a P0 finding
- Trend should be downward across releases; rising CRAP on unsafe code is debt accumulating in the most dangerous place possible

**Caveat:** cargo-crap is v0.2.0 (May 2026). Pin the version in CI. The CLI flags may shift before 1.0.

## Cross-language equivalents

If you're reviewing FFI bindings that include the C side of the boundary:

| Ecosystem | Mutation testing | CRAP |
|-----------|------------------|------|
| C / C++ | `mull` | Compute by hand: `pmccabe` complexity + `gcov`/`lcov` coverage, apply the formula |
| Java (JNI sources) | `PIT` (`org.pitest:pitest-maven`) | `crap4java` (JaCoCo-based reimplementation) |
| .NET (P/Invoke) | `Stryker.NET` | NDepend (commercial; integrates with dotCover/OpenCover) |
| Python (PyO3 wrappers) | `mutmut` | Compute from `radon cc` + `coverage.py` lcov |

See [`static-analysis-tools.md`](static-analysis-tools.md) for the canonical guidance and the full ecosystem table.
