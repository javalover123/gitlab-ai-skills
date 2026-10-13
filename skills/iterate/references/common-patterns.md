# Common Iteration Patterns

## Verification Budget

Verification tools (test runners, linters, full builds) cost time and tokens; spend them deliberately, not reflexively.

- **During the inner loop:** run narrow, targeted invocations scoped to what you just changed — a single test file, `cargo check` instead of a full `cargo test`, a lint pass on the one module you touched. Confirm the specific fix works before moving to the next gap.
- **At validation checkpoints:** run the full suite (all tests, full lint, full build) to confirm nothing else regressed, before updating the iteration log or declaring the project complete.
- **Never verify without changing code in the same turn.** A turn that only runs tests/lint/build with no accompanying `Edit`/`Write`/`MultiEdit` call is a read-only pass, not an iteration — `check-completion.py`'s Stop hook blocks on this (the "verification-only turn" check) and expects you to pick a gap and make a concrete change instead.

This is the rule `check-completion.py` and `SKILL.md` both refer to as the "verification budget."

## Security-First Iteration

When you're drowning in security debt, tackle it first — before anything else. Run security-specific tools (cargo-audit, gosec, bandit), fix every vulnerability you find, then add tests so they can't creep back in. Document your security assumptions and threat model so you don't forget why you made certain choices.

## Test-Driven Gap Closure

For correctness gaps, write the test first. Make sure it fails for the right reason, implement the minimal fix, then verify it passes. This locks in the behavior you want.

## Batch Quality Improvements

Got a ton of small quality issues? Group them by file or module, fix everything in one file at a time, run quality tools after each one, then commit. Atomic changes keep your git history sane.

## Coverage-Driven Completion

Start by generating a coverage report to see what's untested. Identify critical paths that aren't covered, write tests for those first, then fill in edge cases. Re-run coverage to verify you've actually improved things, then repeat until you're happy with the numbers.

## Edge Cases

**Conflicting quality rules:**
- Follow your project's existing style over generic recommendations
- If .editorconfig or .rustfmt.toml exists, those rules win
- Document exceptions in comments

**Perpetual issues:**
- If a gap can't be fixed (external dependency issue), document why and track it
- Add it to known issues in your README
- Create an upstream bug report if applicable

**Test flakiness:**
- Don't consider iteration complete with flaky tests
- Fix or skip flaky tests explicitly
- Document your investigation in the iteration log

**Performance vs. quality trade-offs:**
- Don't sacrifice correctness for performance
- Measure before making it faster
- Document your trade-off decisions

## Troubleshooting

**"Too many gaps, it's overwhelming"**
→ Focus on P0 (security) only for the first iteration. Ignore P2/P3 until you've cleared P0/P1.

**"Tools are giving false positives"**
→ Suppress them with inline comments and justification. Document in your iteration log.

**"Coverage isn't improving"**
→ Check if your tests are actually running new code paths. Use coverage tools' HTML reports to visualize what's happening.

**"Iterations aren't converging"**
→ New gaps appearing each iteration means you've got an unstable foundation. Lock down the architecture before continuing.

**"Unclear what 'complete' means"**
→ Define completion criteria upfront. Use the quality gates checklist as your baseline.
