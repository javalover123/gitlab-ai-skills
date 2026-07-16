# Stop-bias-pattern catalogue

This reference is loaded on demand from the `iteratotron` skill during
Phase 3c (stop-bias scan), Phase 4b (recurrence detection of patterns
across sessions), and Phase 7 (adversarial completion review). It is
the catalogue of patterns that look like completion but aren't —
including the LLM-hallucination tells that distinguish "code that was
written" from "code that was hallucinated to satisfy a checklist".

These patterns are the iteratotron-specific value-add over running
`iterate` alone. `iterate` already has a "scan harder if no obvious
next gap" protocol; iteratotron pre-computes the scan across all
scopes so the orchestrator can prioritise correctly, and it adds the
hallucination-detection patterns that come from observing LLM
implementation drift in the wild.

## The twelve pattern families

Families 1-6 are the classic implementation-lying-about-itself patterns.
Families 7-9 come from harness baseline data (mutation, CRAP, coverage)
when a runtime-harness session (built via `harness-builder`) has produced
`.test-effectiveness/baseline.json`. Families 10-12 are cross-session
recurrence signals — each one requires ≥ 2 sessions of evidence before
it fires, so they only become actionable when iteratotron's been driven
against the same project repeatedly.

### Family 1 — Stub implementations

A function whose body does not do the work its signature and name
promise. The presence of a stub is not necessarily a bug; the absence
of a tracking artefact is. Every stub must be linked to a
spec/ADR/story row that says "this is intentionally not yet
implemented".

**Rust patterns:**

```bash
# Functions returning empty collections as if they're real data
rg -tP -e 'fn\s+\w+[^{]+\{\s*(Ok\(vec!\[\]\)|Ok\(HashMap::new\(\)\)|Ok\(BTreeMap::new\(\)\)|Ok\(Vec::new\(\)\)|return\s+vec!\[\];?|return\s+HashMap::new\(\);?)\s*\}' \
  --multiline --multiline-dotall

# Functions returning Err(NotImplemented) or similar
rg -tP -e 'fn\s+\w+[^{]+\{\s*Err\((Box::new\()?(\w+Error::)?(NotImplemented|Unimplemented|TodoError)' --multiline

# Functions returning the zero value of their type
rg -tP -e 'fn\s+\w+[^{]+->\s*(\w+)\s*\{\s*\1::default\(\)\s*\}' --multiline
rg -tP -e 'fn\s+\w+[^{]+->\s*(bool|u\d+|i\d+|usize|isize)\s*\{\s*(false|0|0\.\d+|"")\s*\}' --multiline
```

**Python patterns:**

```bash
# Functions whose entire body is `pass` or `return None` or returns a literal
rg -tP -e '^def\s+\w+\([^)]*\)(?:\s*->\s*[^:]+)?:\s*\n\s*(pass|return\s+(None|\[\]|\{\}|""|0|False))$' \
  --multiline --multiline-dotall

# raise NotImplementedError
rg -tP -e 'raise\s+NotImplementedError' 

# Single-statement function bodies returning empty/default
rg -tP -e '^def\s+\w+[^:]+:\s*\n\s+return\s+(\[\]|\{\}|""|0|False|None|\(\)|set\(\))$' \
  --multiline --multiline-dotall
```

**Go patterns:**

```bash
rg -e 'func\s+\w+[^{]+\{\s*return\s+(nil|\[\][^{]+\{\}|"")\s*\}' --multiline
rg -e 'return\s+errors\.New\("not implemented"\)'
rg -e 'panic\("(not implemented|unimplemented|TODO)"\)'
```

**TypeScript / JavaScript:**

```bash
rg -e 'function\s+\w+[^{]+\{\s*return\s+(\[\]|\{\}|""|null|undefined|0|false);?\s*\}' --multiline
rg -e 'throw\s+new\s+Error\("(Not implemented|Unimplemented|TODO)"\)'
```

For each match, the finding records:

- File, line, function name, signature.
- The stub body verbatim.
- Whether the function is exported / public (severity multiplier).
- Whether the function is called anywhere (orphan stubs are less
  severe than stubs called from real code paths).

### Family 2 — Placeholders (explicit "not done" markers)

Code that explicitly announces itself as a placeholder. These are
easier to find but harder to disambiguate from intentional WIP markers.

**Rust:**

```bash
rg -tP -e '\b(unimplemented!|todo!|panic!\("(TODO|not yet|unimplemented|FIXME)' --multiline
rg -tP -e 'unreachable!\(\s*"(TODO|not yet|unimplemented|placeholder)' --multiline
```

**Python:**

```bash
rg -tP -e 'raise\s+NotImplementedError'
rg -tP -e '^\s*\.\.\.\s*$'  # bare ellipsis as function body
```

**General comments:**

```bash
rg --pcre2 -e '//\s*(TODO|FIXME|HACK|XXX)' -e '#\s*(TODO|FIXME|HACK|XXX)' -e '/\*\s*(TODO|FIXME|HACK|XXX)' --line-number
```

The TODO scan is noisy. Filter heuristics:

- Look for TODOs **without** a tracking issue reference. A TODO like
  `// TODO: tune this — #4521` is fine; `// TODO: implement` is
  not. Regex: `TODO[:\s]+(?!\s*[#A-Z]+-?\d+|@\w+)`.
- Categorise by what follows the TODO: "implement", "wire", "finish",
  "complete" → P0/P1; "tune", "clean up" → P2/P3.
- Ignore TODOs in generated code (look for `// @generated` or
  `// DO NOT EDIT` banners nearby).

### Family 3 — Partial / Draft / Deferred annotations in artefacts

These are the ones `iterate` explicitly bans as stopping conditions
but iteratotron must enumerate to prioritise them.

**Sources:** specs, ADRs, threat models, stories, CHANGELOG, iteration
logs, READMEs.

**Patterns:**

```bash
# Status: Partial / Draft / Deferred in any artefact
rg --pcre2 -e '^\s*(Status|status):\s*(Partial|Draft|Deferred|WIP|In[\s-]?Progress)' \
  docs/

# Inline annotations
rg --pcre2 -e '\b(deferred|placeholder|awaiting|pending|follow[-\s]?up|not yet wired|stub|TODO|FIXME|HACK|XXX)\b' \
  docs/ --line-number

# Spec FR rows whose status column is not "Implemented"
rg --pcre2 -e '^\|\s*FR-\d+\s*\|.*\|\s*(Partial|Draft|Deferred|WIP)\s*\|' docs/specs/

# Threat-model mitigations not marked implemented
rg --pcre2 -e '^\|.*TM-[A-Z]+-\d+.*\|.*\|\s*(?!✅).*\|' docs/threat-models/
```

For each match:

- The artefact path:line.
- The annotation type (Status / inline word).
- The surrounding context (the FR / mitigation / story / ADR being
  annotated).
- Whether the linked implementation exists.

### Family 4 — Disabled tests

A test that exists in the code but doesn't run. Always a P1 or higher
finding — if a test is there, somebody believed the behaviour mattered.

**Patterns:**

```bash
# Rust #[ignore]
rg -tP -e '#\[ignore(\s*=\s*"[^"]*")?\]' --line-number

# pytest skip / xfail
rg -e '@pytest\.mark\.(skip|skipif|xfail)' --line-number

# unittest skip
rg -e '@unittest\.skip(If|Unless)?\(' --line-number

# JS/TS skipped tests
rg -e '\b(it|describe|test)\.skip\(' --line-number
rg -e '\bxit\(|\bxdescribe\(' --line-number

# Go skipped tests (less common, but a skip call inside a test is the signal)
rg -e 't\.Skip\(' --line-number
```

For each:

- The test function name and file:line.
- The skip reason (if provided).
- Whether the skip reason references a tracking issue (good) or just
  says "TODO" / "fix this later" (bad).
- The age of the skip annotation (`git blame` to find when added).
  Older skips are higher-severity — they indicate the test has been
  abandoned, not paused.

### Family 5 — Orphan scaffolding

Code that exists but is gated off from doing anything. Two sub-kinds:

**5a. Unused-suppressed code:**

```bash
# Rust
rg -tP -e '#\[allow\((dead_code|unused|unused_imports|unused_variables)\)\]'

# Python noqa
rg -tP -e '#\s*noqa(?::\s*F\d+)?'  # noqa for F401 = unused import, etc

# ESLint disable
rg -tP -e '/\*\s*eslint-disable.*\*/|//\s*eslint-disable-(line|next-line)'

# Go //nolint
rg -e '//\s*nolint:\s*(deadcode|unused)'
```

**5b. Feature flags defined but never enabled:**

```bash
# Find Cargo features and check whether any other crate enables them
cargo metadata --no-deps --format-version 1 \
  | jq -r '.packages[] | .features | to_entries[] | "\(.key)"' \
  | sort -u > /tmp/defined_features
# Then check which features are referenced in other crates' [dependencies]
# and in build/test invocations. Features defined but never enabled
# anywhere are orphan scaffolding.

# For other languages: search for feature flag conditionals where the
# flag isn't set anywhere in the config
```

These findings are often P2/P3 individually but **escalate to P0/P1**
when paired with a spec/ADR that says the feature is implemented.
That's the severity-lift case in Family 6.

### Family 6 — LLM-hallucination tells

The most iteratotron-specific category. These are patterns observed in
LLM-generated code that *look* like real implementations but, on close
inspection, do not do the thing.

These tells are harder to find with regex alone; some require
adversarial review (Phase 7's subagent reads the code). The patterns
below are starting heuristics — they raise the probability that the
adversarial reviewer should look more carefully.

#### 6a. Suspiciously-uniform placeholder values

```bash
# Hardcoded "example", "test", "foo", "User", "localhost:8080", "127.0.0.1"
# in non-test code paths
rg -tP -e '"(example\.com|example\.org|user@example|localhost:8080|127\.0\.0\.1|admin@example|test@example)"' \
  --type-not test --type-not spec

# Magic-number placeholders that should obviously be configurable
rg -tP -e '\b(42|123|9999|0xdeadbeef|0xcafebabe)\b' --type rust

# Strings that look like prompts to the LLM that leaked through
rg -tP -e '"(your\s+(actual|real)\s+\w+\s+here|replace this with|TODO: fill|placeholder text)"' -i
```

#### 6b. Print-instead-of-do patterns

The code "implements" something by logging what it would do:

```bash
# Rust: function that mostly just prints/traces
rg -tP -e 'fn\s+\w+[^{]+\{\s*(println!|tracing::info!|tracing::debug!|log::info!)\("(Would|Should|TODO).*"\)' \
  --multiline

# Python: function that mostly just print()s
rg -tP -e 'def\s+\w+[^:]+:\s*\n\s+print\(f?"(Would|Should|TODO|Placeholder)' \
  --multiline --multiline-dotall

# Detect: function body is exclusively log/print calls (no state mutation
# or return of non-default value)
```

#### 6c. Trait/interface impls that are all unimplemented

```bash
# Rust: impl block where every method is unimplemented!()
# (Easier as a multi-line scan than a single regex)
rg -tP -e 'impl\s+\w+\s+for\s+\w+\s*\{[^}]*unimplemented!\(\)[^}]*\}' --multiline --multiline-dotall
```

Heuristic to escalate: if an impl block has ≥3 methods and every
method's body is one line of `unimplemented!()` / `todo!()` / `pass` /
`throw new Error("Not implemented")`, that's not WIP — that's a
hallucinated impl block.

#### 6d. Tautological tests

Tests that assert on the test's own setup output rather than the code
under test. These pass without testing anything.

```python
# Bad example:
def test_compute_total():
    items = [{"price": 10}, {"price": 20}]
    total = sum(item["price"] for item in items)   # the test does the sum
    assert total == 30                              # asserts on its own sum
    # Should have been: assert compute_total(items) == 30
```

These are hard to find by regex. Heuristic flags:

- Test function whose `assert` statement references variables that
  were only set within the test itself, not via a call into the code
  under test.
- Test function with no imports of the module under test (it tests
  Python's built-ins or its own setup).
- Test function whose body has no function calls into the module that
  matches its name (e.g., `test_compute_total` should call
  `compute_total`).

This pattern is best identified by the adversarial reviewer subagent
during Phase 7, but a coarse scan can find candidates:

```bash
# Tests that don't import anything from the project's module space
rg -tP -e '^def\s+test_\w+' --files-with-matches \
  | while read testfile; do
      module="$(basename "$(dirname "$testfile")")"
      if ! grep -qE "from\s+${module}|import\s+${module}" "$testfile"; then
          echo "$testfile: may not test the module"
      fi
  done
```

#### 6e. Documentation lies

Doc comments that describe behaviour the code does not exhibit. The
adversarial reviewer's three-way diff (Phase 7b) catches these
systematically; the pre-scan can flag candidates by:

- Function whose doc comment mentions "retry", "cache", "timeout",
  "concurrent", or other behavioural keywords whose implementation
  shows no corresponding constructs.
- Function whose doc comment cites an ADR or spec ID that doesn't
  exist in the repo.

```bash
# Functions whose docstring/doccomment mentions an ADR/spec/story that doesn't exist
rg -tP -e '(?://|##|""")\s+(?:See|Refs?|Per)\s+(ADR-\d+|SPEC-\d+|STORY-\d+|FR-\d+)' \
  --line-number --no-filename \
  | awk '{print $NF}' | sort -u \
  | while read ref; do
      # Check whether the referenced artefact exists
      if ! rg -lF "$ref" docs/ >/dev/null 2>&1; then
          echo "$ref: referenced in code but not in docs/"
      fi
  done
```

#### 6f. Suspicious patterns specific to common LLM outputs

These are tells observed from working with Claude/GPT/etc-generated
code in long sessions:

- **`// rest unchanged` / `# ... (rest of the function omitted)`**
  comments in non-diff contexts. Indicates partial regeneration that
  was committed.

```bash
rg --pcre2 -e '(?://|#)\s*(rest\s+(of|unchanged)|other\s+\w+\s+omitted|previously\s+defined|\.{3}\s*omitted)' \
  --line-number
```

- **Code that imports types not declared anywhere.** This often
  happens when the LLM hallucinated a sibling module that doesn't
  exist.

```bash
# Rust: find use statements whose target doesn't compile
# (best surfaced by running cargo check, but iteratotron's verification
# budget rule restricts that — so do a static check first)
rg -tP -e '^use\s+crate::([\w:]+)' --no-filename \
  | awk -F'::' '{print $2}' | sort -u \
  | while read mod_path; do
      # Check if any file declares this module
      if ! rg -lP -e "^(pub\s+)?mod\s+$(echo "$mod_path" | cut -d: -f1)" --type rust >/dev/null; then
          echo "use crate::$mod_path: target may not exist"
      fi
  done
```

- **API signatures that don't match their documented contract.** A
  function whose return type is `Result<T, E>` but whose doc comment
  describes when it returns a `Vec<T>`. Mismatch detection requires
  the adversarial review.

### Family 7 — Mutation-survivor cluster

Source: `.test-effectiveness/baseline.json` and the per-iteration
`iter-NNN/delta.json` produced by a `harness-builder`-generated runtime harness (or a native
`cargo mutants --in-diff` / `mutmut` / `gremlins` run when no
baseline). A *cluster* is **three or more surviving mutants on lines
inside the same module or symbol** — a single survivor is a test gap,
a cluster is a sign the module's tests are theatrical.

The cluster pattern matters because it's directional: one survivor
means "add this test"; a cluster means "the suite for this module is
not load-bearing and the implementation may be hollow regardless of
whether the public tests pass". Treat clusters as completion regressions,
not as polish items.

Detection:

- Group baseline/delta entries by `(file, fn)` where `kind ==
  mutation-survivor`. Three or more in the same group = cluster.
- The harness's `triage-verdict.json` may already mark individual
  mutants as `stub-implementation` — a single stub-implementation
  verdict in a cluster lifts the whole cluster to P0 regardless of
  count.
- Recurrence: when the same `(file, fn, mutation_op)` triple appears
  in two sessions across a 30-day window, the test added between
  sessions didn't kill the mutant. Treat as P0 with
  `recurring: mutation-survival`.

Severity seed: P1; lifted by both the doc-claimed-done rule and by
recurrence.

### Family 8 — CRAP-hotspot plateau

Source: same baseline/delta files, `kind == crap-hotspot`. The
*plateau* qualifier matters: a single elevated CRAP score is normal in
older or load-bearing code; a CRAP > 30 that **persists or grows across
≥ 2 sessions despite added tests** is the pattern — it means the
team's response to the hotspot has been to add tests around the
complexity rather than reduce the complexity. CRAP doesn't budge
because cyclomatic complexity dominates the formula once you're past
CC ≈ 20.

This is the "iterate keeps adding tests but the score doesn't move"
trap. The right response is refactor-for-testability — split the
function, extract conditional clusters into typed states, or rewrite
the algorithm. Iterate subagents that try to close a plateau with more
tests will fail.

Detection:

- Track CRAP score history per `(file, fn)` in the completion-log
  corpus (see `recurrence-detection.md § CRAP-regression recurrence`).
- Plateau = CRAP > 30 in current session AND CRAP > 30 in at least one
  prior session in the last 30 days AND coverage on that function
  increased since the prior session.
- Tag `pattern: crap-hotspot-plateau, suggested_action: refactor-for-testability`.
  The iterate-subagent prompt for a plateau finding should include
  the directive **"do not propose more tests as the resolution; the
  prior session already tried that path"**.

Severity seed: P1; doc-claimed-done lift applies.

### Family 9 — Coverage cliff at trust boundary

Source: baseline/delta `kind == coverage-cliff` entries where the
linked artefact is a threat-model entry (TM-XXX-NNN) OR where the file
is imported by code in `THREATMODEL.md`'s data-flow diagram. A
coverage cliff in arbitrary code is a P2 polish item; a coverage cliff
on a mitigation is a P0 because an untested mitigation isn't actually a
mitigation.

Detection:

- Walk `THREATMODEL.md` for STRIDE table rows with `Mitigation:` lines
  citing specific files or symbols.
- For each, check baseline/delta for any function in that file with
  `module_coverage < 0.5`.
- Cross-reference: if the function is named in a mitigation row AND
  appears as `coverage-cliff` in baseline/delta, lift to P0 unconditionally
  (no doc-claimed-done check needed — the threat model itself is the doc
  claiming the mitigation exists).

Severity seed: P0 when linked to threat-model; P2 otherwise.

### Family 10 — Snapshot churn

A snapshot file (insta, syrupy, rspec-snapshot, cupaloy) that flips
state across ≥ 2 iterations of the same iteratotron session is almost
never a "fix the snapshot" finding — it's the test crystallising a
nondeterminism source somewhere else in the system (clock, RNG,
ordering of a hashmap iteration, async task scheduling). Adding the
snapshot back doesn't close the gap; pinning the nondeterminism source
or asserting on a stable projection does.

Source: scope's snapshot tooling reports unreviewed or churning
snapshots across iterations. Recurrence is detected by comparing
snapshot file paths + their content hashes against the prior session's
log entries for the same scope.

Detection:

- `cargo insta pending-snapshots` (or equivalent per language) returns
  non-empty across consecutive iterations.
- Two consecutive iterations' completion-log entries for the same scope
  cite the same snapshot file as "reviewed" with different content hashes.
- A test's flaking rate inside the loop correlates with a snapshot file
  edit in the same iteration.

The iterate-subagent prompt for a snapshot-churn finding must forbid
"re-snapshot and move on" as the resolution; the next iterate cycle
has to either pin the nondeterminism source (mock the clock, seed the
RNG, sort the iteration order) or refactor the assertion to a stable
projection (filter out the volatile field, hash only the deterministic
subset).

Severity seed: P2 on first observation; **P1** after second observation;
**P0** after third — the snapshot is no longer testing the implementation,
it's noise.

### Family 11 — Supply-chain debt plateau

When the same `(ecosystem, package, advisory_id)` triple shows up in
`cargo-deny` / `govulncheck` / `pip-audit` / `bundle audit` / `vulnix`
output across ≥ 3 sessions without being closed, that's debt accumulating,
not work-in-progress. The fix isn't "wait for upstream" — it's either
(a) upgrade the dependency, (b) replace it, or (c) document a VEX
(Vulnerability Exploitability eXchange) justification explaining why the
advisory is not reachable in this codebase. `govulncheck -format openvex`
emits the right OpenVEX shape for (c).

Source: `.iteratotron/completion-log/index.jsonl` recurrence corpus
matching prior session entries that emitted the same advisory ID.

Detection:

- After Phase 3's per-language supply-chain scan, look up each advisory
  ID in the corpus.
- Three matches across distinct prior sessions → STOP-PAT lift; subagent
  prompt requires a decision among (upgrade / replace / VEX) before
  the gate closes.

The iterate-subagent prompt for a supply-chain debt finding must explicitly
list the three resolution paths and require the subagent to commit one;
"upgrade later" is not a valid resolution at this point.

Severity seed: P1 (matches the underlying advisory). Lifts to **P0** after
third session. Doc-claimed-done lift does not apply — the advisory itself
is the doc claim.

### Family 12 — Verification time regression

When bolero / Kani / shuttle / madsim proof or simulation time on the
same harness grows > 50% session-over-session, the verification suite is
either accumulating new states the harness can't reduce, or one of the
recent changes introduced a hot path the prover has to chase
exponentially. Either way, "wait longer" isn't the next step; the
property needs simplification or the harness needs decomposition.

Source: `.test-effectiveness/iter-NNN/` timing data plus the completion
log's recorded `tier3_seconds` per scope per session. The orchestrator
captures wall-clock for each Tier-3 invocation and compares against the
last run on the same harness.

Detection:

- Compute time deltas per harness across the last 3 sessions.
- 50% increase or more → fire the finding.
- 100% increase or more → P0 (the suite is regressing into
  unverifiability).

The iterate-subagent prompt must forbid "raise the timeout" or "skip the
harness" as resolutions. Valid moves: decompose the harness into smaller
properties, narrow the `kani::any()` input range, simplify the loop bound,
or split the property into multiple parallel runs each verifying a
subset.

Severity seed: P2 on first observation; **P1** on 50% session-over-session
growth; **P0** on 100% growth or when the harness now exceeds its
budget.

## Severity-lift table

The severity-lift rule (from SKILL.md §3c) raises a finding's priority
when paired with documentation that claims completion. Full table:

| Finding family       | Default | Lifted to (when paired with docs claiming `Implemented` / `✅ IMPLEMENTED` / `Done`) |
|----------------------|---------|------------------------------------------------------------------------------------|
| Stub (private fn)    | P2      | P1                                                                                 |
| Stub (public fn)     | P1      | **P0**                                                                             |
| Placeholder (`todo!()`) | P1   | **P0**                                                                             |
| Partial annotation   | (in artefact, not impl) — its existence IS the finding | n/a                       |
| Disabled test        | P2      | P1 (and P0 if the test was authoritative for an FR row marked Implemented)         |
| Orphan scaffolding   | P3      | P1 (`#[allow(dead_code)]` on a whole module claimed Implemented)                   |
| Hallucination tells  | P2      | **P0**                                                                             |
| Mutation-survivor cluster | P1 | **P0** (and **P0** regardless on `stub-implementation` triage verdict OR recurrence) |
| CRAP-hotspot plateau | P1      | **P0** (and the iterate prompt forbids "add more tests" as the resolution)         |
| Coverage cliff at trust boundary | P0 when linked to threat-model | n/a — already P0; the threat model is the doc claim |
| Snapshot churn | P2 (first obs) → P1 (second) → P0 (third) | n/a — pin nondeterminism or fix projection; resnapshot is forbidden |
| Supply-chain debt plateau | P1 → **P0** after 3 sessions | n/a — advisory is the doc claim; require upgrade / replace / VEX |
| Verification time regression | P2 → P1 (50% growth) → P0 (100% growth or budget exceeded) | n/a — decompose the harness or simplify the property |

The rule is single-sentence: **documentation lying about reality is
the most dangerous class of finding.** A stub nobody claims to have
done is just unfinished work; a stub that the spec says is done is a
trust failure.

Mechanically: at Phase 3, after collecting the stop-bias finding, look
up the file:line in the cross-reference index built from
artefact-status scans. If the finding's location is within the
implementation of an FR/story/mitigation marked complete in any
artefact, apply the lift.

## Pattern-match-against-prior-fixes (recurrence)

For each stop-bias finding, also check against the completion-log's
embedded corpus of previously-eliminated stop-bias patterns. If
finding similarity (semantic, not just structural) > 0.85 to a prior
elimination:

- **Same scope as prior**: the "fix" never actually replaced the
  placeholder. Severity lift to P0. Tag `prior_fix_did_not_take:
  true`.
- **Different scope from prior**: the same anti-pattern has spread.
  Tag `pattern_propagation: <prior_log_id>`. Consider promoting to a
  proper pattern entry in the bugfix log if it appears in ≥2 scopes.

## Filtering noise

The scans above produce some false positives. The triage pipeline
filters:

1. **Generated code**: skip files with `@generated`, `DO NOT EDIT`,
   `/* eslint-disable */` blanket banners, or paths matching
   `**/target/**`, `**/dist/**`, `**/__pycache__/**`,
   `**/*.pb.rs`, `**/*.pb.go`.
2. **Vendored**: skip `vendor/`, `third_party/`, `node_modules/`.
3. **Examples / fixtures**: scoped detection — a placeholder in
   `examples/` or `tests/fixtures/` is intentional and not a finding,
   unless the example is named in spec/ADR as a runnable
   demonstration that the user will see.
4. **Commented-out code**: a stub-shaped pattern inside a `/* ... */`
   or `# ...` comment block is not a finding.

Each filter is configurable via `.iteratotron.yaml`:

```yaml
stop_bias_scan:
  exclude_paths:
    - "**/target/**"
    - "**/__pycache__/**"
    - "**/*.generated.rs"
  generated_markers:
    - "@generated"
    - "DO NOT EDIT"
  example_paths_intentional: true
```

## What feeds into the iterate-subagent prompt

When a scope is dispatched, the iterate-subagent's prompt includes
the stop-bias findings as a pre-computed P0/P1 work list. The
subagent does NOT re-scan; it acts on the findings.

Specifically:

```
# Stop-bias-pattern findings (pre-computed; address as part of your
# iterate loop. Severity-lifted findings are P0.)

## Severity-lifted (documentation claims complete but implementation
## is not):
- STOP-7f3a9c: crates/agent-compiler/src/dispatch.rs:142 — stub
  implementation; FR-014 in spec/agent-compiler.md marked Implemented.
  Doctrine: implement the real dispatch logic; update spec only if
  the design changes.
- STOP-9b2e1a: crates/agent-compiler/src/lib.rs:88 — unimplemented!()
  in trait impl; ADR-0042 says this trait is implemented for
  AgentCompiler.

## New stop-bias patterns:
- STOP-3c4f8a: crates/agent-graph/src/builder.rs:201 — disabled test
  (#[ignore = "TODO"]); no tracking issue.
- ...

## Recurrence (these patterns were eliminated in prior sessions but
## have reappeared):
- STOP-cd1234 (recurring from session 20260415-...): same shape as
  prior finding in agent-graph; likely the prior fix was reverted or
  a new code path re-introduced the pattern.
```

The subagent uses these as starting work; its own scanning (per
iterate's instructions) confirms or extends them.
