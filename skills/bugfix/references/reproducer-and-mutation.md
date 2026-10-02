# Reproducer quality and mutation testing runbook

This reference is loaded on demand from the `bugfix` skill, mainly during
Phase 3 (reproducer) and Phase 6c (mutation testing). It exists because
reproducer quality's the strongest single guardrail in this skill
— a weak reproducer leaves every downstream gate open to false positives
— and because mutation testing's the only mechanical check that proves
the new test actually exercises the fix.

Examples are in Rust (`cargo test` / `cargo-mutants`) and Python (`pytest`
/ `mutmut`). The patterns translate to other ecosystems with structured
test runners and a mutation-testing tool.

## Part 1 — The four properties of a real reproducer

A reproducer test isn't just "a test that fails before the fix and passes
after." Many tests satisfy that and still fail to constrain the fix. The
bar's higher.

### Property 1 — Fails for the right reason

The test must fail with the *predicted* error class, message, and
post-state — not just *some* failure. A reproducer that fails because the
test harness misconfigured the fixture, or because an unrelated assertion
fired first, is a setup defect masquerading as a reproducer.

**Rust — pin error variant AND field values:**

```rust
// GOOD — pins variant and field
let err = run_dispatch(...).await.unwrap_err();
assert!(
    matches!(err, DispatchError::Timeout { peer, .. } if peer == expected_peer),
    "expected Timeout for peer {expected_peer:?}, got {err:?}",
);

// GOOD — pins post-state via repository query
let row: Option<TaskRow> = db.get("task", task_id).await?;
assert_eq!(row.map(|r| r.status), Some(TaskStatus::Failed));

// GOOD — pins both error and side effect
let result = dispatcher.handle(msg).await;
assert!(matches!(result, Err(DispatchError::PeerUnreachable(_))));
assert_eq!(metrics.snapshot().dispatch_failures, 1);

// BAD — accepts any error
assert!(run_dispatch(...).await.is_err());

// BAD — accepts any panic
let result = std::panic::catch_unwind(|| ...);
assert!(result.is_err());
```

**Python — pin exception type AND message substring:**

```python
# GOOD — pins exception and message
with pytest.raises(ValueError, match=r"^index .* out of range \(got -1\)$"):
    fetch_item(items, -1)

# GOOD — pins error AND observable state
with pytest.raises(IntegrityError, match="duplicate key"):
    repo.insert(record)
assert repo.count() == initial_count  # no partial write

# BAD — too loose
with pytest.raises(Exception):
    fetch_item(items, -1)

# BAD — pytest.raises swallows the diagnosis
with pytest.raises(ValueError):
    fetch_item(items, -1)
# (no match= means a *different* ValueError would silently pass)
```

### Property 2 — Initially fails on the current (broken) tree

You have to actually *run* the test on the unmodified codebase and observe
red. "I'm pretty sure it would fail" isn't evidence; only `cargo test` or
`pytest` output is. Capture the verbatim failure in the `## Reproducer`
block before writing a single line of fix code.

```bash
# Rust
cargo test --package <crate> <test_name> -- --nocapture 2>&1 | tee /tmp/repro.before

# Python
pytest path/to/test.py::test_name -xvs 2>&1 | tee /tmp/repro.before
```

If the test passes on the broken tree, your understanding of the bug's
wrong. Go back to Phase 4 — the causal hypothesis can't be right.

### Property 3 — Catches the *class* of bug, not just the literal input

The most common LLM-agent failure mode in SWE-bench analysis is "fixing
the literal case in the issue and missing siblings." The reproducer has
to defend against this. If the bug's parameterised over a range of inputs
or states, the reproducer needs to be parameterised too.

**Decision tree:**

- **Single, irreducible failing input?** (e.g., null at this one
  specific call site that can never be null elsewhere). One example test
  is fine; document why no sibling cases exist.
- **Range of inputs (numeric, size, length)?** Use `#[rstest]` (Rust) or
  `pytest.mark.parametrize` (Python) to cover {0, 1, boundary-1,
  boundary, boundary+1, max, max+1, negative, MAX/MIN of the type}.
- **State machine or sequence of operations?** Use a stateful proptest /
  Hypothesis state machine (Layer 4 — see test-pyramid.md).
- **Concurrency / ordering?** Use `loom` or `shuttle` for Rust;
  `pytest-asyncio` with deterministic schedulers or `Hypothesis` stateful
  testing for Python.

**Rust — bug class via `rstest`:**

```rust
#[rstest]
#[case::empty(vec![])]
#[case::single(vec![1])]
#[case::boundary_minus_one(vec![1; MAX_BATCH - 1])]
#[case::boundary(vec![1; MAX_BATCH])]
#[case::boundary_plus_one(vec![1; MAX_BATCH + 1])]
#[case::oversize(vec![1; MAX_BATCH * 2])]
fn batch_dispatch_respects_invariant(#[case] input: Vec<u32>) {
    let result = batch_dispatch(input.clone());
    assert!(
        result.dispatched_count() <= MAX_BATCH,
        "invariant violated for input len {}", input.len(),
    );
}
```

**Python — bug class via `pytest.mark.parametrize`:**

```python
@pytest.mark.parametrize("input_size", [
    pytest.param(0, id="empty"),
    pytest.param(1, id="single"),
    pytest.param(MAX_BATCH - 1, id="boundary_minus_one"),
    pytest.param(MAX_BATCH, id="boundary"),
    pytest.param(MAX_BATCH + 1, id="boundary_plus_one"),
    pytest.param(MAX_BATCH * 2, id="oversize"),
])
def test_batch_dispatch_respects_invariant(input_size):
    result = batch_dispatch([1] * input_size)
    assert result.dispatched_count <= MAX_BATCH, \
        f"invariant violated for input len {input_size}"
```

**Property-based version (preferred for invariants):**

```rust
// Rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn batch_dispatch_never_exceeds_max(input in prop::collection::vec(any::<u32>(), 0..1000)) {
        let result = batch_dispatch(input);
        prop_assert!(result.dispatched_count() <= MAX_BATCH);
    }
}
```

```python
# Python
from hypothesis import given, strategies as st

@given(input=st.lists(st.integers(), min_size=0, max_size=1000))
def test_batch_dispatch_never_exceeds_max(input):
    result = batch_dispatch(input)
    assert result.dispatched_count <= MAX_BATCH
```

### Property 4 — Sits at the right pyramid layer

See [test-pyramid.md](test-pyramid.md) for the full mapping. Quick
guidance:

- Pure logic, no I/O → **L1 (unit)**.
- Crosses one module boundary with in-memory fakes → **L2 (component)**.
- Requires real transport, real persistence, multi-service coordination →
  **L3 (BDD / workflow)**.
- Invariant or property over arbitrary inputs / state sequences →
  **L4 (property)** — in addition to L1 / L2 example test.

If you find yourself reaching for L3 because L1 / L2 "is hard to set up,"
that's a smell — the bug might be telling you the abstraction boundaries
are wrong. Note it as a structural concern.

## Part 2 — The revert-and-rerun protocol (Phase 6a)

After the fix lands and the reproducer goes green, you have to
mechanically prove the test exercises the fix:

```bash
# Rust
# 1. Verify green with fix
cargo test --package <crate> <test_name>

# 2. Stash only the fix files, keep the new test
git stash push -m "bugfix-revert-check" -- <fix-file-1> <fix-file-2>

# 3. Re-run; must go red WITH THE SAME ERROR as the original repro
cargo test --package <crate> <test_name> -- --nocapture
# (compare to /tmp/repro.before — same error variant, same message?)

# 4. Restore the fix
git stash pop
```

```bash
# Python — same shape
pytest path/to/test.py::test_name
git stash push -m "bugfix-revert-check" -- <fix-file-1> <fix-file-2>
pytest path/to/test.py::test_name -xvs
git stash pop
```

**Failure modes this protocol catches:**

- Test passes both before and after the fix → the test doesn't exercise
  the fixed code path. Return to Phase 3.
- Test fails on revert but with a *different* error → the test reproduces
  *a* bug, just not the one reported. Either you found a second bug
  (record it; out of scope) or the diagnosis's wrong (return to Phase 4).
- Test fails on revert with the same error → ✓ reproducer confirmed.

## Part 3 — Flaky reproducers: when the test isn't deterministic

A test that fails sometimes and passes other times can still be a real
reproducer — but you have to constrain the non-determinism before
declaring `GATE 3: PASS`. Flakiness during diagnosis is itself a bug; a
reproducer that masks it produces a fix that masks it.

### Diagnosing the source of flakiness

Work through these in order:

1. **Time dependency.** Does the test depend on wall-clock time, sleep
   intervals, or system clock granularity? Symptoms: passes on a fast
   machine, fails on a slow one (or vice versa). **Fix:** inject a fake
   clock; never `sleep`.
2. **Iteration order.** Does the test depend on `HashMap` / `dict`
   iteration order? Python 3.7+ guarantees insertion order; Rust
   `HashMap` randomises by default. **Fix:** sort before comparing, or
   use ordered types (`BTreeMap`, `OrderedDict`).
3. **Concurrency / scheduling.** Does the test fail under load or with
   different thread schedules? **Fix:** model with `loom` / `shuttle`
   (Rust) or `Hypothesis` stateful testing (Python). If the bug only
   manifests under a specific schedule, that schedule's the reproducer.
4. **Resource contention.** Shared ports, shared database namespaces,
   shared temp files. **Fix:** ephemeral resources per test
   (`tcp://*:0`, per-test UUID namespaces, `tempfile.mkdtemp`).
5. **External dependencies.** Network calls to real services, even in
   tests. **Fix:** mock or use a recorded fixture (e.g., `vcrpy`,
   `mockito`).
6. **Process-global state.** Environment variables, logger
   configuration, static singletons. **Fix:** reset between tests with a
   fixture; or design the code to take the state as an argument.

### The flakiness budget

Some bugs are inherently non-deterministic (e.g., specific cache
eviction patterns, GC-triggered failures). For these:

- Don't aim for 100% reproduction. Aim for a high enough hit rate that
  CI catches regressions.
- Run the test many times in the reproducer block to establish a
  baseline. A test that fails 30 / 100 times before the fix and 0 / 1000
  after is solid evidence.
- Document the residual flakiness in `## Remaining Risks` at Phase 9.

```bash
# Rust — run a test 100 times, report failure rate
for i in {1..100}; do
    cargo test --package <crate> <test_name> -q 2>&1 | tail -1
done | sort | uniq -c

# Python — same shape via pytest-repeat
pytest path/to/test.py::test_name --count=100 -x --tb=no -q
```

### When the bug *only* reproduces under load

For race conditions that only fire under contention, schedule-randomising
test runners exist:

- **Rust:** `loom` (proves all interleavings of `Arc`, `Mutex`,
  `AtomicX` for a small state space).
- **Rust:** `shuttle` (random schedule fuzzing — explores more
  schedules than loom but doesn't prove exhaustively).
- **Python:** `Hypothesis` `stateful` tests with `random` strategies.
- **Cross-language:** `chaos-mesh` or `toxiproxy` for network-level
  fault injection at L3.

## Part 4 — Mutation testing (Phase 6c)

Mutation testing answers a question no other tool answers: *if I made a
small wrong change to the fix, would any test catch it?* A surviving
mutant on the fix's changed lines proves the test suite doesn't constrain
the fix — even if every test passes.

### cargo-mutants for Rust

**Installation (one-time):**

```bash
cargo install cargo-mutants --locked
```

**Preview what'd be mutated (no test runs):**

```bash
cargo mutants --in-diff <(git diff HEAD) --list
```

This is useful for sanity-checking scope before a long run.

**Standard invocation in a bugfix session:**

```bash
# Mutate only the lines changed in the current diff vs HEAD
cargo mutants --in-diff <(git diff HEAD) --timeout-multiplier 2.0

# More aggressive: include uncommitted changes vs base branch
cargo mutants --in-diff <(git diff origin/main) --timeout-multiplier 2.0

# Limit to specific files when iterating
cargo mutants --file crates/dispatcher/src/handler.rs

# Faster feedback during iteration
cargo mutants --in-diff <(git diff HEAD) --jobs 4 --baseline skip
```

**Reading the output:**

```
PASS    src/handler.rs:142: replace == with !=     ← BAD: mutant survived
CAUGHT  src/handler.rs:143: replace > with >=      ← GOOD: a test failed
TIMEOUT src/handler.rs:150: replace match arm      ← needs longer timeout
UNVIABLE src/handler.rs:155: replace expression    ← didn't compile; ignore
```

- `CAUGHT` (or `MISSED` depending on version) on every mutant in changed
  lines → **Phase 6c passes.**
- Any `PASS` / surviving mutant on changed lines → **add a test that
  kills it**, or the fix's unconstrained.
- `TIMEOUT` → raise `--timeout-multiplier`. If it still times out, the
  test's too slow at this layer — consider moving down a layer (L2 →
  L1), splitting the test, or limiting the mutation to lines that don't
  invoke the slow path.
- `UNVIABLE` → ignore; these are mutants that produce uncompilable code,
  not behavioural changes.

**Common surviving-mutant patterns and what they mean:**

| Mutant survived            | What it tells you                              |
|----------------------------|------------------------------------------------|
| Replace `==` with `!=`     | Test doesn't check the equality path           |
| Replace `+` with `-`       | Test doesn't check the arithmetic result       |
| Replace `>` with `>=`      | Boundary case untested                         |
| Delete `!` (negation)      | Test doesn't distinguish true / false branch   |
| Replace block with `()`    | The function's return value's never asserted   |
| Replace `Ok(x)` with `Err` | No test exercises the success branch           |
| Delete a side-effecting line | The side effect isn't asserted               |

### mutmut for Python

```bash
pip install mutmut

# Run only on changed files
mutmut run --paths-to-mutate=path/to/changed.py

# Results
mutmut results
mutmut show <id>   # see what the surviving mutant did
```

`mutmut`'s slower than `cargo-mutants` because Python lacks the
compile-time filtering. Be aggressive about scoping (`--paths-to-mutate`)
and consider running it in CI on a nightly cadence rather than per-PR.

### When mutation testing's too slow

For large codebases, full-suite mutation runs can take hours. This skill
mitigates that by **only mutating lines in the diff** (`--in-diff`). Even
on a large workspace this usually completes in a few minutes for a
focused fix.

If a single fix touches more than 50 lines, mutation testing might still
be slow. Two options:

1. **Tighten the diff** (often the right answer — large diffs are a
   smell that the fix is doing more than one thing).
2. **Run mutation testing on the most critical lines only** — usually
   the new conditional logic, new error handling, and the lines that
   restore the invariant. Note in DoD which lines were mutated.

## Part 4b — Consuming the harness-produced baseline

When the `harness-builder` skill (runtime mode) or a recent `bug-burndown` session
populated `.test-effectiveness/baseline.json` and
`.test-effectiveness/iter-NNN/delta.json`, the bugfix skill should read
them before running its own local mutation pass. Two reasons:

1. The harness already mutated this code — re-running it from scratch
   duplicates 1–5 minutes of work per fix.
2. The harness's Pass 3 Haiku triage has already classified each finding
   as `real-bug`, `test-gap`, `dead-code`, `stub-implementation`, or
   `acceptable-debt`. The bugfix skill should respect those verdicts when
   choosing how to handle the diff.

### Reading the artefacts in Phase 4 (diagnosis)

```bash
baseline=".test-effectiveness/baseline.json"
latest_delta=".test-effectiveness/iter-*/delta.json"
verdicts=".test-effectiveness/iter-*/triage-verdict.json"

if [[ -f "$baseline" ]]; then
    # Find findings touching files in the bug's blast radius
    jq --arg file "src/dispatcher.rs" \
       'map(select(.file == $file))' "$baseline" "$latest_delta"
fi
```

When the bug's blast-radius file matches a `mutation-survivor` or
`crap-hotspot` finding, the diagnosis (Phase 4) should call this out:
"this bug sits in a CRAP-156 function flagged by the baseline; the
suite already can't tell whether this fix is correct without new tests".

### Running mutation testing in Phase 6c

The diff-scoped `cargo mutants --in-diff` invocation still runs locally
on the fix's changed lines. The harness baseline is for *context*, not
for replacing the per-fix gate. Specifically:

- If the harness baseline lists a surviving mutant on a line the fix
  touched, the fix's new test MUST kill that mutant. Verify by
  re-running `cargo mutants --in-diff <(git diff HEAD)` and looking
  for `CAUGHT` against the same mutation_op.
- If the harness baseline lists a CRAP hotspot in the touched
  function, the fix should either reduce CRAP (by adding tests or
  splitting the function) or carry a justification in DoD.

### Severity overrides

The harness's `triage-verdict.json` can short-circuit Phase 4 in two
cases:

- `verdict: stub-implementation` on the file/fn — the original bug
  report is likely a *symptom* of the stub. Phase 4 should widen scope
  to ask "should we be replacing the stub instead of fixing this single
  failure?" before proceeding.
- `verdict: dead-code` — the bug may simply not be reachable. Verify
  the call graph (`cargo machete` for Rust, `vulture` for Python,
  `deadcode` for Go) before writing a fix. The right fix might be
  deleting the dead code, not fixing it.

`real-bug` and `test-gap` verdicts don't override anything — they
confirm the standard bugfix workflow applies.

### When the baseline is stale

`.test-effectiveness/manifest.yaml` records `baseline_sha`. If `git
merge-base HEAD <baseline_sha>` is more than ~50 commits behind, treat
the baseline as advisory only — too much has changed since it was
generated. The harness will refresh on its next iteration; the bugfix
session shouldn't try to refresh it inline.

## Part 5 — Differential testing (for refactor-style fixes)

When the fix's a refactor that should preserve behaviour (renaming,
restructuring, replacing one implementation with another), an extra
guardrail's available: run both the old and new implementations on a
shared corpus of inputs and assert their outputs match.

**Rust pattern:**

```rust
#[test]
fn refactor_preserves_behaviour() {
    let inputs = recorded_inputs::load("tests/corpus/dispatcher.jsonl");
    for input in inputs {
        let old = old_implementation::process(&input);
        let new = new_implementation::process(&input);
        assert_eq!(old, new, "diverged on input: {input:?}");
    }
}
```

**Python pattern:**

```python
@pytest.mark.parametrize("input", load_corpus("tests/corpus/dispatcher.jsonl"))
def test_refactor_preserves_behaviour(input):
    old = old_implementation.process(input)
    new = new_implementation.process(input)
    assert old == new, f"diverged on input: {input}"
```

The corpus should include:

- Every input from the original failing test suite.
- A handful of edge cases (empty, max-size, unicode, malformed).
- Outputs from a recent production trace, if available.

Differential tests are temporary — they live for the duration of the
refactor and get deleted once the old implementation's removed. Don't
ship them as permanent regression tests.

## Part 6 — Common reproducer anti-patterns to refuse

Reject any reproducer that looks like these. They masquerade as
reproducers but don't constrain the fix.

| Anti-pattern                            | Why it fails                                    |
|-----------------------------------------|-------------------------------------------------|
| `assert!(result.is_err())` with no variant pin | Any error passes — fix could change error class |
| `pytest.raises(Exception)` without `match=` | Catches unrelated exceptions too               |
| Test that only checks return value, never side effects | Misses persistence / log / metric bugs |
| Test that mocks the unit under test     | Tests the mock, not the code                    |
| Test with `sleep` waiting for async work | Flaky; promotes timing-mask "fixes"             |
| Test that sets up state via the same code it tests | Circular; fix in setup hides fix in code under test |
| Test asserting on a log line as the *only* observable | Logs aren't contracts; assert on state too |
| Test marked `#[ignore]` or `xfail` "for now" | A skipped test isn't a reproducer at all      |
| Test with a per-test sleep > 1s         | The bug's masked by timing rather than caught   |

## Part 7 — Quality checklists

Before emitting `GATE 3: PASS`:

```
- [ ] Test name describes the behaviour, not the bug (no "test_bug_1234")
- [ ] Failure mode pinned: error variant + message substring + post-state
- [ ] Verbatim failure output captured pre-fix
- [ ] Bug class covered: parametrize / proptest / state machine if applicable
- [ ] Sits at the right pyramid layer (justify in one sentence)
- [ ] Sibling call sites grep'd; siblings covered or explicitly out of scope
- [ ] Test doesn't depend on production code's broken behaviour to set up
- [ ] No `sleep`, no broad except, no `is_err()`-only assertions
- [ ] Will survive future refactors of internals (asserts on contract,
      not implementation detail)
- [ ] Flakiness understood: deterministic, OR documented hit rate with
      sources of non-determinism identified
```

Before emitting `GATE 6: PASS`:

```
- [ ] Revert-and-rerun: red with same error pre-fix, green post-fix
- [ ] Mutation survivors on changed lines: 0
- [ ] If any mutant survived and was killed by a new assertion, the new
      assertion checks contract behaviour, not implementation
- [ ] Mutation run covered the lines that restore the invariant, not just
      the lines that handle the symptom
- [ ] For refactor-style fixes, differential test on shared corpus
      passes (or N/A)
```
