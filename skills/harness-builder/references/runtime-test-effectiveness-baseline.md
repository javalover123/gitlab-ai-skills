# Test-effectiveness baseline and delta contract

This reference defines the shared on-disk artefacts the harness produces
on iteration 1 (full baseline) and on every subsequent iteration (delta
against changed files only). `bug-burndown`, `iterate`, and `iteratotron`
all read from these files — keep the format stable.

The contract is intentionally tool-agnostic: mutation testing, CRAP, and
coverage tools differ per ecosystem, but the unified JSON envelope below
is what downstream skills consume.

## On-disk layout

```
.test-effectiveness/                   # top-level dotfile, auto-gitignored
├── baseline.json                      # iteration 1 full scan
├── baseline.lcov                      # iteration 1 coverage trace (LCOV)
├── baseline-changed.json              # files changed since baseline_sha
├── iter-NNN/
│   ├── delta.json                     # this iteration's changed-file scan
│   ├── delta.lcov                     # coverage trace scoped to changes
│   ├── triage-input.json              # raw findings handed to Pass 3 Haiku
│   └── triage-verdict.json            # Haiku verdicts (per-finding)
└── manifest.yaml                      # baseline metadata
```

Auto-gitignore the directory on first write (same pattern as
`.bug-burndown/` and `.iteratotron/`):

```bash
ensure_gitignored ".test-effectiveness/"
```

## manifest.yaml

```yaml
baseline_sha: <commit SHA at iter 1>
baseline_created: <ISO-8601 UTC>
baseline_tools:
  mutation: cargo-mutants 25.3.0
  crap: cargo-crap 0.2.0
  coverage: cargo-llvm-cov 0.6.21
ecosystem: rust | go | python | ruby | nix | mixed
fallback_active: false              # true when cargo-crap missing and hand-computed
```

## Unified findings envelope

Every entry in `baseline.json` and every `iter-NNN/delta.json` is one
object of this shape:

```json
{
  "kind": "mutation-survivor | crap-hotspot | coverage-cliff",
  "tool": "cargo-mutants | mutmut | gremlins | mutant | stryker | mull | cargo-crap | radon | cyclop | rubycritic | llvm-cov | coverage.py | ...",
  "file": "<repo-relative path>",
  "fn": "<function or module name, when known>",
  "line": 142,
  "evidence": "<the mutation diff OR the CRAP score+CC+cov OR the uncovered branch ID>",
  "linked_artefact": "<ADR-NN | STORY-N | SPEC-FR-N | TM-XXX-N | null>",
  "linked_status": "implemented | partial | not-started | null",
  "severity_seed": "P0 | P1 | P2 | P3"
}
```

`severity_seed` is the harness's first cut. Downstream skills lift it via
their own rules (bug-burndown Phase 3, iteratotron stop-bias-pattern
catalogue) — most commonly via the **doc-claimed-done lift**: if
`linked_status == "implemented"` the seed bumps from P1 → P0 because the
documentation is claiming a behaviour the tests can't actually verify.

## Per-kind evidence shapes

### Mutation survivors

```json
{
  "kind": "mutation-survivor",
  "tool": "cargo-mutants",
  "file": "crates/dispatcher/src/handler.rs",
  "fn": "handle_message",
  "line": 142,
  "evidence": {
    "mutation_op": "replace == with !=",
    "mutation_diff": "-    if status == Status::Ready {\n+    if status != Status::Ready {",
    "killed": false,
    "elapsed_s": 8.2
  },
  "linked_artefact": "STORY-187",
  "linked_status": "implemented",
  "severity_seed": "P0"
}
```

A mutation survivor on a line inside a doc-claimed-implemented artefact
is the most damning combination — the implementation is hollow.

### CRAP hotspots

```json
{
  "kind": "crap-hotspot",
  "tool": "cargo-crap",
  "file": "crates/orchestrator/src/scheduler.rs",
  "fn": "next_dispatchable",
  "line": 64,
  "evidence": {
    "crap": 156.0,
    "complexity": 12,
    "coverage": 0.12
  },
  "linked_artefact": "ADR-0042",
  "linked_status": "implemented",
  "severity_seed": "P1"
}
```

Use the canonical threshold of 30: CRAP > 30 is the trigger. The formula
`comp² × (1 − cov/100)³ + comp` (Savoia & Evans, 2007) makes the
dangerous combination — complex code with thin coverage — explode into
visible range.

When `cargo-crap` is absent, compute by hand from cyclomatic complexity
(radon for Python, cyclop for Go, rubycritic for Ruby) and lcov coverage.
Set `manifest.fallback_active: true` so consumers can flag the data as
less precise.

### Coverage cliffs

```json
{
  "kind": "coverage-cliff",
  "tool": "llvm-cov",
  "file": "crates/auth/src/session.rs",
  "fn": "refresh_token",
  "line": 88,
  "evidence": {
    "uncovered_lines": [88, 89, 91, 92],
    "uncovered_branches": ["88:T", "91:F"],
    "module_coverage": 0.42
  },
  "linked_artefact": "TM-AUTH-003",
  "linked_status": "implemented",
  "severity_seed": "P0"
}
```

Threat-model-linked code with low coverage is the highest-priority
coverage cliff — a mitigation that isn't tested is, in practice, no
mitigation.

## Baseline run (iteration 1)

Iteration 1 runs the **full** scan across the workspace and writes
`baseline.json`. The pattern per ecosystem (drop into your harness's
build phase, before iteration 1's reviewer step):

```bash
# Rust
cargo install --locked cargo-mutants cargo-llvm-cov
cargo install cargo-crap@0.2.0 || echo "cargo-crap unavailable; falling back"

cargo llvm-cov --lcov --output-path .test-effectiveness/baseline.lcov --workspace
cargo mutants --jobs "$(nproc)" --json > .test-effectiveness/baseline-mutants.json
cargo crap --lcov .test-effectiveness/baseline.lcov --format json > .test-effectiveness/baseline-crap.json
# OR (fallback): radon-equivalent + lcov-parser to hand-compute

# Go
go install github.com/go-gremlins/gremlins@latest
gremlins unleash ./... --output json > .test-effectiveness/baseline-mutants.json
go test ./... -coverprofile=.test-effectiveness/baseline.lcov
# cyclop + cobertura join is the CRAP-equivalent

# Python
pip install mutmut radon coverage
coverage run -m pytest
coverage lcov -o .test-effectiveness/baseline.lcov
mutmut run --json > .test-effectiveness/baseline-mutants.json
radon cc --total-average --json . > .test-effectiveness/baseline-cc.json

# Ruby
bundle exec mutant run --use rspec --json-dump .test-effectiveness/baseline-mutants.json
bundle exec rubycritic --format json --no-browser > .test-effectiveness/baseline-crap.json
bundle exec rspec --format SimpleCov::Formatter::LcovFormatter
```

After the tool-native files exist, a small wrapper merges them into the
unified envelope and writes `baseline.json`. The wrapper lives in the
harness binary so language-specific shape differences stay there.

## Delta run (iterations 2+)

On every iteration after the first:

```bash
changed_files=$(git diff --name-only "$baseline_sha"..HEAD -- '*.rs' '*.go' '*.py' '*.rb' 2>/dev/null)
echo "$changed_files" > .test-effectiveness/iter-NNN/changed.txt

# Mutation testing scoped to the diff (cheap)
cargo mutants --in-diff <(git diff "$baseline_sha"..HEAD) --json \
  > .test-effectiveness/iter-NNN/delta-mutants.json

# CRAP scoped to changed files (cargo-crap supports per-file filtering)
cargo crap --lcov .test-effectiveness/baseline.lcov \
           --files "$changed_files" --format json \
  > .test-effectiveness/iter-NNN/delta-crap.json

# Coverage delta — only re-run for changed crates
for crate in $(crates_owning $changed_files); do
    cargo llvm-cov -p "$crate" --lcov >> .test-effectiveness/iter-NNN/delta.lcov
done
```

`cargo mutants --in-diff` typically takes one to three minutes on a
modest diff and is the single most useful gate. CRAP recompute is cheap
because the LCOV is already there. Coverage takes the longest — only
re-run crates whose files actually changed.

Write the merged result to `.test-effectiveness/iter-NNN/delta.json` in
the unified envelope.

## Diff against the baseline

The interesting part is *which findings appeared or worsened* compared
to baseline, not the raw findings list. The wrapper computes three
classes on every delta:

- **`appeared`** — the file/fn/line/kind tuple is in delta but not in
  baseline. A new mutation survivor, a new CRAP hotspot, a new coverage
  cliff. These are the freshest signals.
- **`regressed`** — the tuple exists in both, but evidence got worse:
  CRAP score grew, coverage dropped, or a previously-caught mutation
  variant now survives. Highest signal — something the team thought was
  improving is going backwards.
- **`persisted`** — the tuple is in both unchanged. Carried forward but
  not re-prioritised. Only worth surfacing when the operator explicitly
  asks (`--include-persisted`).

The output appended to `iter-NNN/triage-input.json` carries all three
classes so Pass 3 can rank them.

## Triage input for Pass 3 (Haiku)

`iter-NNN/triage-input.json` is the prompt payload for the Haiku
hotspot-triage reviewer. Structure:

```json
{
  "iteration": 3,
  "baseline_sha": "abc1234",
  "current_sha": "def5678",
  "findings": [ /* unified envelope, with class: appeared|regressed */ ],
  "ranking_hints": {
    "doc_claimed_done": [ /* finding_ids with linked_status == implemented */ ],
    "near_threat_boundary": [ /* finding_ids in files imported by THREATMODEL targets */ ],
    "recurrence": [ /* finding_ids matching prior session entries */ ]
  }
}
```

Haiku returns `iter-NNN/triage-verdict.json` in this shape:

```json
{
  "findings": [
    {
      "finding_id": "<sha of file:fn:line:kind>",
      "verdict": "real-bug | test-gap | dead-code | stub-implementation | acceptable-debt",
      "rationale": "<one or two sentences>",
      "suggested_bug_class": "incomplete-implementation | hollow-test | refactor-for-testability | wire-up-unused | null"
    }
  ]
}
```

The verdict drives what `bug-burndown` does with the finding:

- `real-bug` → queue normally at `severity_seed`
- `test-gap` → queue as `kind: test-gap`, ask the bugfix subagent to add
  a test that kills the mutant or covers the cliff
- `dead-code` → queue as `kind: orphan-scaffolding`, ask to delete or
  wire up
- `stub-implementation` → queue at P0 regardless of `severity_seed`;
  this is a hollow completion claim
- `acceptable-debt` → record in a per-session ignore list; don't queue
  this iteration, but resurface if it appears again next session

## Consumer skill quick-reference

| Skill | What it reads | What it does with it |
|---|---|---|
| `bug-burndown` | `baseline.json` (first run), `iter-NNN/delta.json` and `triage-verdict.json` (subsequent) | Phase 2g collector turns each finding into a queue entry |
| `iterate` | Both, scoped to the current iterate scope | Step 1 gap analysis includes mutation+CRAP findings |
| `iteratotron` | Both, scoped per scope being audited | Phase 3b gap audit + Phase 3c stop-bias-pattern scan input |
| `bugfix` | Single finding from the queue | Phase 4 diagnosis context; Phase 6c mutation-test gate |

## When the baseline doesn't exist

When a consumer skill runs and `.test-effectiveness/baseline.json` is
absent, the skill must:

1. Note the absence in its session manifest (`harness_baseline: absent`).
2. Run its own local mutation+CRAP pass scoped to its work — `iterate`
   per scope, `bug-burndown` per session, `bugfix` per fix.
3. Not block on the absence; the baseline is an optimisation, not a
   prerequisite.

The harness running first is the canonical path. The skills work without
it; they just do more redundant scanning.

## Cost notes

Iteration 1's baseline is the expensive run: full-workspace mutation
testing can take 20–60 minutes on a medium codebase. Iteration 2+
deltas typically finish in 1–3 minutes because `--in-diff` limits scope
to changed lines.

Per ecosystem, rough wall-clock on a 50-crate Rust workspace:

| Phase | Iter 1 (baseline) | Iter N (delta) |
|---|---|---|
| `cargo llvm-cov` | 8–15 min | 30–90 s (changed crates only) |
| `cargo mutants` | 20–45 min | 1–3 min (`--in-diff`) |
| `cargo crap` | < 30 s | < 5 s |
| Haiku triage | ~$0.05–$0.15 | ~$0.02–$0.05 |

The baseline pays for itself on iteration 2; the harness loop typically
runs 3–10 iterations.

## Liveness — heartbeat every long-running tool (MANDATORY)

The baseline phase shells out to mutation and coverage tools that run for
**many minutes with no output until they exit** — `cargo mutants` /
`gremlins unleash ./...` / `mutmut run` are 20–60 minutes on iteration 1.
A harness that invokes these through a single blocking call
(`cmd.Output()`, `cmd.Run()`, `subprocess.run`, `Command::output()`) emits
its last log line *before* the tool starts and its next line *after* it
finishes — so to an operator on the default log the whole phase **looks
hung** for the better part of an hour. That is indistinguishable from a real
deadlock, and it's the 2026-06-16 "test-effectiveness phase hangs without
heartbeats" incident.

> **The rule:** every external test-effectiveness tool whose runtime can
> exceed ~30s MUST run under a liveness heartbeat — a background timer that
> logs a periodic `tool still running — phase alive` line with the tool name
> and elapsed seconds while the blocking call executes, and stops the moment
> the call returns (on **every** path). This mirrors the `RunPrompt` /
> `run_event_loop` agent-drive heartbeat (opencode-server-integration §4
> "Observability"); the two phases should log liveness consistently.

Requirements for the wrapper:
- Fires on a fixed interval (~30s); the **first** tick is a genuine quiet
  interval, not the instant the call started.
- Stops as soon as the wrapped call returns — **no leaked timer goroutine /
  task** that keeps logging after the tool finished.
- Propagates the wrapped call's value and error **unchanged** — it is pure
  liveness instrumentation, never alters behaviour.
- Logs a `tool finished` line with total elapsed on return, so the operator
  sees the phase advance.
- Wrap the *long poles only* — mutation (`gremlins`/`cargo mutants`/`mutmut`)
  and full-suite coverage (`go test -coverprofile ./...` / `cargo llvm-cov`).
  Fast static-analysis tools (`gocyclo`, `cargo crap`, `radon cc`) don't need
  it.

Go (canonical — `vulnmapper pkg/harness/test_effectiveness.go`):

```go
const teHeartbeatInterval = 30 * time.Second

// withHeartbeat runs fn while a background goroutine logs a periodic liveness
// line, so a blocking external command (no output until exit) is visibly
// alive. Stops on every return path; propagates fn's value/error unchanged.
func withHeartbeat[T any](ctx context.Context, tool string, fn func() (T, error)) (T, error) {
    started := time.Now()
    done := make(chan struct{})
    go func() {
        t := time.NewTicker(teHeartbeatInterval)
        defer t.Stop()
        for {
            select {
            case <-done:
                return
            case <-ctx.Done():
                return
            case <-t.C:
                slog.Info("test-effectiveness: tool still running — phase alive",
                    "tool", tool, "elapsed_secs", int(time.Since(started).Seconds()))
            }
        }
    }()
    res, err := fn()
    close(done)
    slog.Info("test-effectiveness: tool finished",
        "tool", tool, "elapsed_secs", int(time.Since(started).Seconds()))
    return res, err
}

// Wrap the long poles:
out, err := withHeartbeat(ctx, "gremlins", func() ([]byte, error) { return cmd.Output() })
_, err = withHeartbeat(ctx, "go-cover", func() (struct{}, error) { return struct{}{}, cmd.Run() })
```

Rust (tokio): spawn a `tokio::time::interval` task that logs until a
`tokio::sync::oneshot` / dropped guard cancels it; run the blocking tool on
`spawn_blocking` and `select!`/await both. Same contract: stop on return,
propagate the result, never alter behaviour.

**Required regression tests** (three minimum, by name):
1. `with_heartbeat_returns_result_and_error` — value + error propagated unchanged.
2. `with_heartbeat_emits_no_spurious_line_on_fast_call` — a sub-interval call logs zero heartbeat lines.
3. `with_heartbeat_stops_after_fn_returns` — no further heartbeat lines fire after the call returns (no leaked timer).
