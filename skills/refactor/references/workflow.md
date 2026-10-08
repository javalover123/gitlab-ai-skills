# Universal Refactoring Workflow

Six phases, each with a checklist. Don't skip phases — the whole point is that you can
prove things got better, not just *feel* like they did.

## Phase 1: Baseline Establishment

Before you change a single line, capture the current state. You can't demonstrate
improvement without a starting point.

```
Baseline Checklist:
- [ ] Run existing tests, record pass/fail state
- [ ] Measure current test coverage percentage
- [ ] Catalog existing helper libraries/packages/crates
- [ ] Document current code metrics (complexity, duplication, file sizes)
- [ ] Record number of linter warnings/errors
- [ ] Capture git state (branch, last commit hash)
```

**Why this matters:** If you don't record the baseline, you'll end up saying "I think
it's better now" instead of "coverage went from 62% to 78%." Numbers don't lie. Feelings do.

## Phase 2: Analysis

Now you're hunting. Run language-specific linters and static analysis tools, then look
for patterns the automated tools miss.

```
Analysis Checklist:
- [ ] Run language-specific linters and static analysis
- [ ] Detect anti-patterns using language-specific rules
- [ ] Find duplicate code and DRY violations
- [ ] Identify missing documentation on public APIs
- [ ] Find magic strings/numbers that should be constants
- [ ] Detect inline logic that should use centralized helpers
- [ ] Assess test coverage gaps
```

Use the detection commands from your language's rules file. Every language reference
includes a "Detection Commands" section with copy-paste commands you can run immediately.

For duplication-specific tools and complexity thresholds, see
[duplication-detection.md](duplication-detection.md).

## Phase 3: Prioritization

Sort your findings. Work top-down — don't polish formatting while security holes sit open.

**Critical (P0 — fix before anything else):**
- Security vulnerabilities (injection, memory safety, auth bypass)
- Crashes and panics in production paths
- Data corruption risks
- Undefined behavior

**High (P1 — core gaps):**
- Architecture violations (code in wrong layer/module)
- Large duplicate blocks (100+ lines)
- Missing error handling or resource leaks
- High cyclomatic complexity (>20)

**Medium (P2 — quality improvements):**
- Style violations and unnecessary complexity
- Minor duplication (50-100 lines)
- Missing documentation for public APIs
- Suboptimal patterns that hurt readability

**Low (P3 — track for later):**
- Minor style preferences
- Test file duplication (often intentional for clarity)
- Performance micro-tuning without profiling data

## Phase 4: Test-First Refactoring

This is the heart of the workflow. For each finding, follow this cycle strictly.

```
Refactoring Cycle:
- [ ] Write or improve tests BEFORE changing code
- [ ] Tests establish expected behavior baseline
- [ ] Make incremental changes (one logical change at a time)
- [ ] Run tests after EVERY change
- [ ] Commit each working increment
- [ ] Never refactor multiple areas simultaneously
```

**Why test-first?** If you can't write a test for the code, you don't understand it well
enough to refactor it. The test is proof that you know what the code does *now*, so you
can verify it still does the same thing *after* your changes.

**Why one change at a time?** When tests break, you need to know exactly which change
caused the failure. If you've touched four files in four different ways, good luck
debugging that.

## Phase 5: Verification

After each batch of refactoring, prove you haven't introduced new problems.

```
Verification Checklist:
- [ ] All original tests still pass
- [ ] All new tests pass
- [ ] Coverage improved or maintained (never decreased)
- [ ] Code metrics improved (complexity, duplication counts)
- [ ] Linter warnings reduced or eliminated
- [ ] Documentation added for new/changed public APIs
```

If coverage decreased, you've either deleted tested code without replacing the tests, or
you've introduced untested code. Both need fixing before you move on.

## Phase 6: Reporting

Generate a before/after summary. Be specific about what you measured and what changed.
Don't round up, don't claim improvements you haven't verified.

```markdown
## Refactoring Summary

### Metrics
| Metric              | Before | After | Delta |
|---------------------|--------|-------|-------|
| Test coverage       | X%     | Y%    | +Z%   |
| Lint warnings       | N      | M     | -K    |
| Cyclomatic max      | A      | B     | -C    |
| Duplicate blocks    | D      | E     | -F    |

### Changes Made
- [Category]: What changed, where (file:line)
- [Category]: What changed, where (file:line)

### Remaining Items
- [What wasn't addressed and why]
```

The "Remaining Items" section isn't optional. Every refactoring session leaves some
things untouched — be honest about what's left.
