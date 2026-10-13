# Progress Tracking

Create an iteration log at `.iterate/iteration-log.md` (preferred — keeps log writes outside `.claude/` so they don't trigger per-write permission prompts), or in the project root. Update it at the end of each iteration cycle.

## Iteration Log Template

```markdown
# Iteration Log — Project Name

## Iteration 1 — YYYY-MM-DD

**Gaps identified:** 23 (8 security, 6 correctness, 7 quality, 2 coverage)
**Gaps addressed:** 8 (all security)
**Status:** Continuing (correctness gaps remain)

### Changes:
- Fixed buffer overflow in parse_input() (security)
- Updated rusqlite to patch CVE-2024-XXXX (security)
- Added input validation to API endpoints (security)

### Metrics:
- Test coverage: 45% → 52%
- Clippy warnings: 23 → 15
- Security issues: 8 → 0

## Iteration 2 — YYYY-MM-DD

**Gaps identified:** 15 (0 security, 6 correctness, 7 quality, 2 coverage)
**Gaps addressed:** 6 (all correctness)
**Status:** Continuing (quality gaps remain)

### Changes:
- Fixed failing test_concurrent_access (correctness)
- Completed stub implementation of export_data() (correctness)
- Removed TODO in auth module, implemented proper session handling (correctness)

### Metrics:
- Test coverage: 52% → 67%
- Clippy warnings: 15 → 7
- Failing tests: 6 → 0

## Iteration 3 — YYYY-MM-DD

**Gaps identified:** 9 (0 security, 0 correctness, 7 quality, 2 coverage)
**Gaps addressed:** 9 (all remaining)
**Status:** Complete (zero gaps)

### Changes:
- Fixed all clippy warnings (quality)
- Added missing unit tests for edge cases (coverage)
- Documented all public APIs (quality)

### Final Metrics:
- Test coverage: 67% → 84%
- Clippy warnings: 7 → 0
- All quality gates: PASS

**LOOP COMPLETE.**
```

The final line matters: `session-start-handover.py` scans the log's last line for a literal "complete" sentinel to decide whether a new session should resume the loop. Without one, a genuinely finished project still gets a resume directive on its next session start. End the log with a line like `**LOOP COMPLETE.**` once every gate passes — not partway through, and not alongside words like "deferred" or "pending" on that same line, which keep the loop flagged as in-flight even next to "complete".

## Tips

- Don't wait until you're done to write the log — update it as you work
- Track both gaps found and gaps addressed so you can see convergence
- Metrics before/after each iteration make it obvious when you're making progress (or stuck)
- If new gaps appear each cycle, you've hit an architectural instability — lock down the design before continuing
