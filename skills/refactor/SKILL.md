---
name: refactor
description: "Performs codebase review and systematic refactoring for code quality, reliability, maintainability, and test coverage across Go, Rust, Python, C, and Nix. Use when running quality improvement passes, reviewing code for anti-patterns, cleaning up technical debt, improving test coverage, or when the user mentions refactor, code quality, or review-code."
version: 1.0.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# Codebase Refactoring

Make a codebase better — find anti-patterns, duplication, missing docs,
underused helpers, and coverage gaps, then fix them one verified change at a
time. Not "looks better" — *tests prove it's better*.

## When to use

- Starting a quality pass on an existing codebase, or cleaning up debt before a
  release.
- Reviewing for anti-patterns and duplication after a feature lands.
- Improving coverage in undertested areas, or verifying nothing regressed after
  a big change.

## Quick start

1. Detect languages and load only the matching rules (below).
2. Catalog existing helper libraries **before** writing anything new.
3. Baseline: run tests, measure coverage, capture CRAP + mutation-survivor
   counts, count lint warnings.
4. Analyze with the loaded rules' detection commands.
5. Prioritize (P0–P3) and work through findings test-first.
6. Verify: tests pass, metrics improved, no new debt.

Full six-phase workflow with checklists: [references/workflow.md](references/workflow.md).

## Language detection

Load **only** the rules that match the project's marker files:

| Markers | Language | Rules |
|---|---|---|
| `go.mod`, `*.go` | Go | [references/go-rules.md](references/go-rules.md) |
| `Cargo.toml`, `*.rs` | Rust | [references/rust-rules.md](references/rust-rules.md) |
| `pyproject.toml`, `setup.py`, `*.py` | Python | [references/python-rules.md](references/python-rules.md) |
| `Makefile`+`*.c`/`*.h`, `CMakeLists.txt` | C | [references/c-rules.md](references/c-rules.md) |
| `flake.nix`, `*.nix` | Nix | [references/nix-rules.md](references/nix-rules.md) |

Also load [references/database-patterns.md](references/database-patterns.md) for
SQL/db code and [references/http-api-patterns.md](references/http-api-patterns.md)
for client/server code when relevant.

## Phase 1 — Baseline

Capture the current state before changing anything: test pass/fail, coverage %,
CRAP scores for in-scope modules, mutation-survivor count on the diff baseline,
lint warning count, and code metrics (complexity, duplication, file sizes).

**Critical rule — catalog helpers first.** Before any refactoring, list existing
public helpers (`grep -r '^func ' pkg/util/`, `rg '^pub fn' crates/shared*/`,
`rg '^def |^class ' src/utils/`) and write them down. Then *use* them — don't
reinvent or wrap what already exists. Patterns:
[references/helper-library-patterns.md](references/helper-library-patterns.md).

## Phase 2 — Analysis

Run the loaded rules' detection commands. Look for anti-patterns (unwrap in Rust,
ignored errors in Go, bare except in Python, unchecked malloc in C, `with` abuse
in Nix), duplication, missing docs on public APIs, magic values, inline logic
that should call a helper, test gaps, and security smells. Duplication tools and
thresholds: [references/duplication-detection.md](references/duplication-detection.md).

## Phase 3 — Priority matrix

Work top-down:

- **P0 blockers** — security holes (injection, memory safety, auth bypass),
  crashes/panics in production paths, data corruption, UB.
- **P1 core gaps** — architecture violations, large duplicate blocks (100+
  lines), missing error handling / resource leaks, cyclomatic complexity >20.
- **P2 quality** — style, minor duplication (50–100 lines), missing public-API
  docs, suboptimal patterns ([references/refactoring-catalog.md](references/refactoring-catalog.md)).
- **P3 later** — style preferences, test duplication (often intentional), micro
  perf.

Run CRAP-driven target selection **before** prioritizing: the CRAP score
(`comp² × (1 − cov)³ + comp`) finds code that's both complex and undertested —
exactly where refactoring without test backing is most dangerous. Treat every
function above threshold 30 as a Phase 4 candidate whose first move is *add
tests, then refactor*.

## Phase 4 — Test-first refactoring

Per finding, no exceptions: (1) write/improve tests for the code **before**
changing it — if you can't test it, you don't understand it well enough to
refactor; (2) make one logical change; (3) run tests, revert if red; (4) commit
each working increment. After adding tests, run mutation testing (`cargo mutants
--in-diff <(git diff origin/main)` or the language equivalent) — a surviving
mutant means the test passes regardless of correctness; fix it before
refactoring. Test patterns: [references/test-improvement.md](references/test-improvement.md).

## Phase 5 — Verification

After each batch: all original + new tests pass; coverage improved or flat
(never down); lint warnings reduced; no new duplication; helper catalog updated;
docs added for new/changed public APIs.

## Phase 6 — Reporting

Emit a before/after summary with a metrics table (coverage, lint warnings, max
complexity, duplicate blocks, CRAP > 30 count, mutation survivors), the changes
made (with file:line), and remaining items. State what you measured — don't
round up, and don't claim a metric improved without running the command.

## Static-analysis tools

| Language | Linter | Security | Test effectiveness |
|---|---|---|---|
| Go | golangci-lint | gosec, govulncheck | go-mutesting |
| Rust | clippy (pedantic) | cargo-audit, cargo-deny | cargo-mutants + cargo-crap |
| Python | ruff, mypy | bandit, pip-audit | mutmut |
| C | clang-tidy, cppcheck | flawfinder | mull |
| Nix | statix, deadnix | — | — |

Run the linter and security scanner before and after; the delta tells you if
you're improving things.

## Key rules

- **No wrapper functions** — if a helper exists, call it directly.
- **No duplicate helpers** — search before writing.
- **Constants for repeated literals** — anything appearing 3+ times.
- **Normalization must be idempotent** — `normalize(normalize(x)) == normalize(x)`.

## References

- [references/workflow.md](references/workflow.md) — full six-phase workflow
- [references/helper-library-patterns.md](references/helper-library-patterns.md) — helper cataloging
- [references/documentation-standards.md](references/documentation-standards.md) — doc requirements by language
- [references/test-improvement.md](references/test-improvement.md) — test patterns and coverage goals
- [references/duplication-detection.md](references/duplication-detection.md) — tools and thresholds
- [references/refactoring-catalog.md](references/refactoring-catalog.md) — before/after patterns
- Language rules: [go](references/go-rules.md), [rust](references/rust-rules.md), [python](references/python-rules.md), [c](references/c-rules.md), [nix](references/nix-rules.md)
- Ecosystem: [database](references/database-patterns.md), [http/api](references/http-api-patterns.md)
