# Proactive bug discovery patterns

This reference is loaded on demand from the `bugfix` skill during Phase 0
(Bug Discovery), which runs only when the user invoked the skill without
a specific target. It documents the scan patterns, prioritisation rules,
and stop conditions used to build a bug candidate list autonomously.

The whole point of Phase 0 is to find bugs without asking the user what
to fix. Asking "what should I look at?" is the failure mode this phase
exists to prevent.

## Phase 0 mental model

You're a code archaeologist arriving in a new project. You have an hour.
What do you check first? In order:

1. **Recent activity** (git history) — what's been churning?
2. **Live signals** (logs, issue tracker, test failures) — what's
   currently broken?
3. **Code smells** (TODO, unwrap, swallowed except) — what does the team
   already know is broken?
4. **Drift** (ADR vs code, spec vs tests) — what does the documentation
   claim that the code doesn't deliver?
5. **Test hygiene** (skipped / flaky / slow) — what's hiding behind a
   `#[ignore]`?

Each scan contributes candidates. Score them, pick one, proceed.

## Scan 0a — Recent activity

```bash
# Recent bug-shaped commits (catches both new bugs and adjacent
# unfixed cases near recent fixes)
git log --since="2 weeks ago" \
    --grep="fix\|revert\|hotfix\|broken\|regression\|crash\|panic\|leak" \
    --pretty=format:"%h %s" \
    -i

# Recent reverts specifically — these often mean a fix was wrong
git log --since="2 months ago" --grep="^Revert" --pretty=format:"%h %s"

# Recent dependency bumps (potential SLSA regressions or breaking changes)
git log --since="2 weeks ago" \
    -- '**/Cargo.lock' '**/Cargo.toml' '**/package.json' '**/package-lock.json' \
       '**/go.sum' '**/go.mod' '**/Pipfile.lock' '**/poetry.lock' \
    --pretty=format:"%h %s"

# Recently deleted tests — suspicious unless paired with a replacement
git log --diff-filter=D --since="2 weeks ago" -- '**/tests/**' '**/test_**'
git log --diff-filter=D --since="2 weeks ago" -- '**/*.test.ts' '**/*.test.js'

# Files with the most changes in the last month (churn = bug magnet)
git log --since="1 month ago" --pretty=format:"" --name-only | \
    sort | uniq -c | sort -rn | head -20
```

**What to look for:**

- A revert that wasn't followed by a re-fix → the bug it tried to address
  may still be open.
- Dependency bumps to a major version with no migration note in the
  commit → possible breakage.
- Deleted tests not replaced → coverage gap.
- High-churn files → high bug density (Microsoft Research finding from
  the early 2000s, still holds).

## Scan 0b — Logs and issue tracker

```bash
# Project-local log files modified recently
find . -name '*.log' -mtime -7 -not -path '*/node_modules/*' -not -path '*/target/*'

# Common error patterns in those logs (case-insensitive)
find . -name '*.log' -mtime -7 -exec grep -lE 'ERROR|FATAL|panic|SIGSEGV|unhandled|traceback|stack ?trace' {} +

# Frequency analysis — which errors repeat?
find . -name '*.log' -mtime -7 -exec cat {} + | \
    grep -E 'ERROR|FATAL|panic' | \
    sort | uniq -c | sort -rn | head -20

# Recent issue-tracker bugs (GitHub)
gh issue list --label bug --state open --limit 20 2>/dev/null

# GitLab
glab issue list --label bug --state opened --limit 20 2>/dev/null

# Sentry / Linear references inside the codebase
rg -n 'SENTRY-[0-9]+|LINEAR-[A-Z]+-[0-9]+|GH-[0-9]+|GL-[0-9]+' \
    --type-add 'src:*.{rs,py,c,h,go,ts,js,rb,java}' -tsrc
```

**What to look for:**

- A repeating error in logs with high frequency but no matching open
  issue → silent failure.
- An open bug issue with an attached stack trace → ready-made input for
  Phase 1.
- A `SENTRY-1234` reference in a `TODO` comment → unresolved error
  category.

## Scan 0c — Code smells

```bash
# TODO / FIXME / XXX / HACK comments by priority
rg -n 'TODO:?\s*security|FIXME:?\s*auth|XXX:?\s*crypto|HACK:?\s*bypass' -ti
# These are P0 candidates — security-tagged technical debt.

# General TODO / FIXME (P2 unless context elevates)
rg -n 'TODO|FIXME|XXX|HACK' \
    --type-add 'src:*.{rs,py,c,h,go,ts,js,rb,java,nix}' -tsrc

# Rust unwrap / expect without safety justification
rg -n -B1 '\.unwrap\(\)|\.expect\(' --type rust | \
    rg -v '// SAFETY:|// PANIC:'

# Rust panic / unimplemented / todo!() in non-test code
rg -n 'panic!\(|unimplemented!\(|todo!\(' --type rust -g '!**/tests/**'

# Python broad exception swallowing
rg -n 'except Exception:|except:\s*$|except:\s*pass' --type py

# JavaScript / TypeScript catch-and-ignore
rg -n '} catch \(.*\) \{\s*\}|\.catch\(\(\) => \{\}\)' --type js --type ts

# Go: errors deliberately ignored
rg -n ', _ :?= |^\s*_ = ' --type go

# C: unchecked return values from risky functions
rg -n 'strcpy|strcat|gets|sprintf' --type c --type cpp
# (Also: prefer strlcpy/strlcat — see openbsd-knf-style)

# Misused unsafe
rg -n 'unsafe \{' --type rust -B2 | rg -v '// SAFETY:'
```

**What to look for:**

- A security-tagged TODO → P0, regardless of how stale it is.
- `unwrap()` in a code path the user can hit → null-deref or
  panic-on-malformed-input.
- `except: pass` → almost certainly swallowing a real error.
- `unsafe {}` without a `// SAFETY:` justification → soundness audit
  candidate.

## Scan 0d — Drift between docs and code

```bash
# Find ADRs and their referenced files
find docs/adr docs/decisions -name '*.md' 2>/dev/null | while read adr; do
    echo "=== $adr ==="
    grep -oE '[a-zA-Z_/.-]+\.(rs|py|c|h|go|ts|js)' "$adr" | sort -u
done

# Then for each referenced file, check it exists and the function/symbol
# named in the ADR is still present. A missing file or symbol is drift.

# Find spec scenarios and their test references
find specs docs/specs features -name '*.md' -o -name '*.feature' 2>/dev/null

# Threat-model mitigation drift
rg -n 'mitigation:|control:|enforced by:' docs/security/ docs/threat-model/ 2>/dev/null
# Then check each cited mechanism still exists in code.
```

**What to look for:**

- ADR says "we use mutex X for invariant Y" but the code path now uses
  `RwLock` — silent invariant drop.
- Spec scenario references `test_foo` but `test_foo` doesn't exist.
- Threat model says "rate limiting enforced by middleware Z" but Z's been
  removed.

## Scan 0e — Test-suite health

```bash
# Skipped tests (Rust + Python + JS)
rg -n '#\[ignore\]|@pytest.mark.skip|@pytest.mark.xfail|it\.skip\(|test\.skip\(' \
    --type rust --type py --type ts --type js

# Slow tests (last N runs, if profile data exists)
test -f .nextest-profile.json && jq '.tests | sort_by(.duration) | reverse | .[0:10]' \
    .nextest-profile.json 2>/dev/null

# Tests that have been #[ignore]'d for more than a month
rg -n '#\[ignore' --type rust | while read line; do
    file=$(echo "$line" | cut -d: -f1)
    git log -1 --format="%ar | $line" -- "$file" 2>/dev/null
done | sort

# Run the full suite, capture failures and flakes
cargo nextest run 2>&1 | grep -E 'FAIL|FLAKY' || true
pytest -x --tb=no -q 2>&1 | grep -E 'FAILED|ERROR' || true
```

**What to look for:**

- A test ignored "temporarily" 8 months ago → probably hides a real bug.
- A test in the slowest 10 → may be slow because it's doing too much, and
  may be flaky as a result.
- A genuinely failing test on `main` → fix it, that's literally the job.

## Prioritisation

For each candidate, score:

| Dimension | P0 | P1 | P2 |
|---|---|---|---|
| Security impact | Touches auth / crypto / supply chain / trust boundary / PII | Adjacent to security path | None |
| Correctness impact | Causes wrong output, data loss, silent failure | Causes degraded performance, recoverable errors | Cosmetic / DX |
| Reproducer signal | Stack trace, error log, or failing test exists | Symptom described | Inferred from code smell |
| Drift severity | Code contradicts ADR / spec / threat model | Doc silent on the case | Style / naming drift |
| User-facing | Yes, currently broken | Yes, edge case | Internal only |

A candidate is P0 if it hits **any** P0 row. P1 if it hits any P1 and no
P0. P2 otherwise.

**Tie-break order between same-P candidates:**

1. Most concrete reproducer signal (stack trace > error log > TODO comment).
2. Most recent activity (active churn > stale).
3. Smallest blast radius (one module > cross-cutting refactor).
4. Best-documented authoritative source (ADR > spec > inferred from code).

## Emitting the candidate list

```
## Discovery candidates

| # | Priority | Source | Description | Reproducer signal |
|---|---|---|---|---|
| 1 | P0 | src/auth/session.rs:142 | unwrap() on session.user_id in hot path | call site reachable from POST /login |
| 2 | P0 | logs/svc-auth.log:1023 | repeating "session not found" ERROR, 47/day | error message + trace_id available |
| 3 | P1 | docs/adr/0042.md | ADR says X, code says Y | three-way diff prepared |
| 4 | P1 | tests/auth/test_session.rs:33 | #[ignore] since 2025-09-12 | test body present, just disabled |
| 5 | P2 | src/auth/login.rs:88 | TODO: handle expired tokens | comment only |
| 6 | P2 | src/auth/login.rs:104 | except Exception: pass | swallowed error |

Selected target: #1 (P0, unwrap() in auth hot path, most concrete signal).

Proceeding to Phase 1 with this candidate.
```

The user gets to see your reasoning. They can interrupt and redirect, but
you don't proactively ask them to choose.

## Stop conditions

**No candidates after all five scans:** emit the `## No bugs found`
report from SKILL.md Phase 0h. Don't fabricate a candidate.

**Genuinely tied P0s that can't be ranked objectively AND the user would
benefit from picking:** `AskUserQuestion` with the candidates as options.
This is the one acceptable use of `AskUserQuestion` in Phase 0.

**Discovery taking longer than ~5 tool calls per scan:** you're scope
creeping. Stop the current scan and move to the next.

## Scaling Phase 0 to large codebases

For monorepos or codebases with thousands of files:

- Restrict each scan to one or two top-level directories at a time.
- Use `--max-count=20` on `rg` to cap per-file matches.
- Run `git log` with `--max-count=50` to avoid pulling years of history.
- Spawn a subagent (`general-purpose`) for the discovery itself to keep
  the main context lean. Have it return only the candidate list.

## What Phase 0 doesn't cover

- **Performance regressions** — use `analyze-build`, `rust-performance-optimizer`,
  or profiler-based skills instead.
- **Security audits** (full STRIDE / threat modelling) — that's
  `security-assessment`. Phase 0 only catches security bugs visible in
  the surface scans.
- **Architecture review** — that's `code-review` or domain-specific
  review skills.

Phase 0 finds *bugs*, not *opportunities for improvement*. If the
discovery scan keeps surfacing "we should refactor X," that's a signal
to hand off to `refactor` or `implementation-review` instead.
