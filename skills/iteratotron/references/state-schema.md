# `.iteratotron/state.json` schema

Genesis persists every state mutation to disk via atomic-rename. This
reference documents the canonical schema so consumers (resume, done
predicate, traceability matrix, human-review) can parse it
deterministically.

## Top-level layout

```jsonc
{
  "schema_version": "1.0.0",
  "project_id": "example",
  "session_id": "20260525-152217-a3b1",
  "started_at": "2026-05-25T15:22:17Z",
  "phase": "inner_loop",                  // "bootstrap" | "gap_analysis" | "plan" | "inner_loop" | "done_predicate" | "complete"

  "constitution": {
    "path": ".specify/memory/constitution.md",
    "sha256": "...",
    "amended_during_session": false
  },

  "budgets": {
    "time_budget_seconds": 28800,         // 8h default
    "cost_budget_usd": 100.00,
    "parallel_outer": 2,
    "parallel_inner": 3
  },

  "baseline_sha": "...",                  // HEAD when iteratotron started
  "integration_branch": "main",

  "harness_vector": {
    // see references/harness-vector.md for the full per-language schema
  },

  "scope_queue": [
    // one entry per top-level scope (the top-level orchestrator sees these — iteratotron
    // sees the inner sub-scopes inside its own session dir)
  ],

  "bug_queue": [
    // one entry per finding routed for bug-burndown
  ],

  "cost_log": [
    // append-only — one entry per subprocess invocation
  ],

  "tier3_timing": [
    // append-only — one entry per Tier-3 run, used by Family 12 (verification time regression)
  ],

  "recurrence_index": ".iteratotron/recurrence.jsonl",

  "traceability_csv": ".iteratotron/traceability.csv",

  "in_toto_layout": ".iteratotron/in-toto/layout.json",

  "stop_reason": null                     // populated when iteratotron ends; one of: "done_predicate_passed", "time_budget_exhausted", "cost_budget_exhausted", "circuit_breaker:<reason>", "user_interrupt"
}
```

## Scope queue entry

Each top-level scope (iteratotron top-level granularity — broader than
iteratotron's per-crate scopes):

```jsonc
{
  "id": "example/transport/zmq-router",
  "kind": "feature_area",                 // "feature_area" | "language_package" | "active_branch" | "open_issue" | "adr_section"
  "linked_artefacts": {
    "specs": ["specs/transport-zmq.md"],
    "adrs": ["adrs/0007-zmq-transport.md", "adrs/0014-zmq-router-pattern.md"],
    "threat_models": ["threat-models/transport.md"],
    "stories": ["stories/zmq-router.md", "stories/zmq-dealer-failover.md"]
  },
  "tier3_triggers": ["madsim", "shuttle"],
  "constitution_check": {
    "last_run": "2026-05-25T15:30:00Z",
    "result": "pass",                     // "pass" | "fail" | "needs_human"
    "violations": []
  },
  "status": "complete",                   // "queued" | "in_flight" | "needs_rebase" | "blocked" | "needs_human" | "complete"
  "attempt_count": 2,
  "iteratotron_session_id": "20260525-153000-x9y1",   // the session that ran this scope
  "worktree_path": "/var/tmp/iteratotron-worktrees/example/transport/zmq-router",
  "merged_sha": "abc123...",
  "completed_at": "2026-05-25T17:42:00Z",
  "tier1_passed": true,
  "tier2_passed": true,
  "tier3_results": {
    "shuttle": {"seeds": 50, "wall_clock_s": 1240, "verdict": "pass"},
    "madsim": {"seeds": 50, "wall_clock_s": 1860, "verdict": "pass"}
  },
  "adversarial_review": {
    "verdict": "APPROVED",
    "subsections_passed": [1, 2, 3, 4, 5, 6],
    "lessons_learned": "..."
  }
}
```

## Bug queue entry

Mirrors `bug-burndown`'s findings schema with an additional
`source_scope` field tying it back to the iteratotron scope that
surfaced it (when applicable):

```jsonc
{
  "id": "F-0042",
  "source": "madsim-seed:0xDEAD0042",     // or "tier1-mutation:...", "spec-drift:...", "constitution:Article-I.3"
  "source_scope": "example/transport/zmq-router",
  "finding_kind": "concurrency_bug",       // see bug-burndown's taxonomy
  "severity": "P0",
  "evidence": "...",
  "status": "fixed",                       // "queued" | "in_flight" | "fixed" | "wontfix" | "needs_human"
  "fixed_in_commit": "def456...",
  "attempts": 1,
  "wall_clock_s": 480,
  "cost_usd": 1.85
}
```

## Cost log entry

Every claude subprocess invocation:

```jsonc
{
  "ts": "2026-05-25T16:12:31Z",
  "scope_id": "example/transport/zmq-router",   // null for adversarial reviewer (cross-scope)
  "subagent_kind": "iteratotron",              // "iteratotron" | "iterate" | "bug-burndown" | "adversarial_reviewer" | "constitution_check" | "trigger_detector"
  "model": "claude-sonnet-4-6",
  "session_id": "20260525-...",
  "duration_ms": 1842000,
  "total_cost_usd": 4.21,
  "input_tokens": 152400,
  "output_tokens": 18230,
  "cache_creation_tokens": 0,
  "cache_read_tokens": 87600,
  "result_subtype": "success"                  // "success" | "error" | "error_max_turns" | "error_during_execution"
}
```

The session-level total cost is the sum of `total_cost_usd` across all
entries; the budget cap fires when that sum exceeds `budgets.cost_budget_usd`.

## Tier-3 timing entry

Used by Family 12 (verification time regression) detection:

```jsonc
{
  "ts": "2026-05-25T16:18:00Z",
  "tool": "shuttle",                       // "shuttle" | "madsim" | "loom" | "tlc" | "kani" | "bolero" | "wycheproof" | "schemathesis" | "nixos_test"
  "harness": "tests/router_concurrency.rs",
  "scope_id": "example/transport/zmq-router",
  "session_id": "20260525-...",
  "seeds": 50,
  "wall_clock_s": 1240,
  "verdict": "pass",                       // "pass" | "fail" | "timeout" | "budget_exhausted"
  "growth_vs_baseline": {
    "baseline_session_id": "20260518-...",
    "baseline_wall_clock_s": 820,
    "growth_pct": 51                       // 51% growth — would trigger Family 12 P1
  }
}
```

## Recurrence index entries

`.iteratotron/recurrence.jsonl` is append-only across sessions:

```jsonc
{
  "session_id": "20260525-...",
  "scope_id": "example/transport/zmq-router",
  "attempt_idx": 0,
  "planned_diff_embedding": [0.123, -0.456, ...],   // 384-dim sentence-transformer or fallback
  "outcome": "incomplete",                          // "complete" | "incomplete" | "needs_human" | "blocked"
  "diff_summary": "Added ZmqRouter::route_message; failed adversarial review (cross-scope contract change)",
  "lessons_carried": []                             // populated when subsequent attempts cite this entry
}
```

## Traceability CSV

`.iteratotron/traceability.csv` — one row per completed scope. Schema:

```csv
scope_id,specs,adrs,threat_model_entries,stories,acceptance_tests,mutation_survivors_closed,crap_max_after,coverage_after,tier3_tools_run,tier3_seeds,phase7_subsections_passed,merged_sha
```

The done predicate (`references/done-predicate.md`) walks this CSV
plus a project-level `/traceability-matrix-build` output to verify
zero unlinked artefacts before declaring `done(project) == true`.

## Atomic-rename persistence

Every state mutation:

```python
import json
import os
import tempfile

def fsync_state(state, path=".iteratotron/state.json"):
    tmpdir = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=tmpdir, prefix=".state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp, path)  # atomic on POSIX
    except Exception:
        os.unlink(tmp)
        raise
```

Use SQLite WAL when the project is large enough that JSON parsing
becomes a bottleneck. Genesis's default is JSON because most projects
don't reach that point — a 10K-line state file is fine.

## Resumability

`/iteratotron resume:<session-id>` reads `.iteratotron/<session-id>/state.json`
and re-enters Phase 3 with whichever scopes / findings are not in
terminal status. Worktrees with uncommitted changes prompt the human
via `AskUserQuestion` before any discard.

The resume logic is in `scripts/resume.py`:

```python
def resume(session_id):
    state = load_state(f".iteratotron/{session_id}/state.json")
    if state["phase"] == "complete":
        print("Session already complete; nothing to resume.")
        return
    # Re-run Phase 0 capability check (skill versions may have moved)
    # Re-run Phase 1 if any docs changed since baseline_sha
    # Skip Phase 2 if scope_queue already populated; re-prioritise instead
    # Re-enter Phase 3 with non-terminal entries
    # Phase 4 done predicate runs as soon as all entries are terminal
    ...
```

## Hooks and the Stop oracle

Genesis registers a `Stop` hook that blocks termination when:

1. `phase != "complete"` AND
2. Any `scope_queue` entry is in non-terminal status AND
3. `time_budget_seconds` and `cost_budget_usd` are both within cap.

The hook returns `{"decision": "block", "reason": "..."}` with a list
of remaining scopes and their statuses. This forces the orchestrator
back into Phase 3 dispatch rather than letting it write a premature
summary.

The hook **does not fire** in subagent context (so iteratotron's own
hook and iterate's own hook own their respective inner loops) and
**does not fire** when `stop_hook_active` is already set (infinite-loop
guard).

Implementation in `scripts/check-completion.py`.
