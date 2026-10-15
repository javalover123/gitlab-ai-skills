# Orchestration mechanics

This reference is loaded on demand from the `iteratotron` skill during
Phase 6 (dispatch) and the success path of Phase 7 (reconcile). It
covers the worktree lifecycle, the iterate-subagent invocation contract
in detail, and the merge/conflict protocols that keep parallel iterate
runs from colliding.

The fundamental challenge is different from bug-burndown's: each
iterate subagent runs a *long, multi-iteration loop* in its own
context, with its own stop hook firing repeatedly until completion.
The orchestrator's job is to give that loop the right starting
conditions, isolate it, accept its verdict, then verify the verdict
semantically.

## Scope queue entry schema

Each scope record in `${session_dir}/scope_queue.jsonl` is a single
JSON object on its own line. Append-only; updates write a new line
referencing the prior `id` (latest wins).

```json
{
  "id": "SCOPE-7f3a9c1e",
  "schema_version": 1,
  "session_id": "20260516-152217-bf2a",
  "created_at": "2026-05-16T15:25:18Z",
  "updated_at": "2026-05-16T15:25:18Z",

  "kind": "cargo-crate",
  "name": "agent-compiler",
  "primary_path": "crates/agent-compiler",
  "secondary_paths": [],
  "language": "rust",

  "linked_artefacts": {
    "spec": "docs/specs/agent-compiler.md",
    "adrs": ["docs/adr/0042-agent-trait-design.md"],
    "threat_model": "docs/threat-models/agents.md",
    "stories": ["docs/stories/STORY-187.md"]
  },

  "iteration_log": "crates/agent-compiler/.iterate/iteration-log.md",
  "last_iterate_status": "Partial — FR-014 stub remaining",
  "last_iterate_session_id": "20260415-091422-c1d4",
  "last_complete_claim_at": null,

  "needs_all_aboard": false,

  "gap_summary": {
    "P0": 4,
    "P1": 12,
    "P2": 8,
    "P3": 3,
    "stop_bias_findings": 6,
    "severity_lifted_findings": 4
  },

  "recurrence": {
    "recurring": false,
    "prior_log_match": null,
    "prior_session_id": null
  },

  "dependency": {
    "blocks": ["SCOPE-9b2e1a04"],
    "blocked_by": [],
    "related_scopes": ["SCOPE-3c4f8a02"]
  },

  "estimate": {
    "cost": "M",
    "expected_iterate_cycles": 3,
    "requires_human_review": false
  },

  "priority_rank": 1,
  "priority_reasons": [
    "4 severity-lifted findings (spec FR-014 marked Implemented, impl is stub)",
    "P0 count = 4",
    "blocks SCOPE-9b2e1a04"
  ],

  "status": "queued",
  "attempt_count": 0,
  "worktree": null,
  "branch": null,
  "completion_sha": null,
  "lessons_learned": []
}
```

Status values:

- `queued` — ready for dispatch.
- `in_flight` — currently running iterate subagent.
- `awaiting_review` — iterate subagent finished, Phase 7 reviewing.
- `complete` — Phase 7 APPROVED, merged to integration.
- `needs_rebase` — merge conflict; auto-rebase pending or failed.
- `blocked` — subagent hit a genuine blocker; needs human input.
- `insufficient` — Phase 7 returned INSUFFICIENT; back to queue.
- `needs_human` — Phase 7 returned NEEDS_HUMAN; not re-dispatchable.
- `requires_decomposition` — scope too large; surface to user.
- `skipped_recently_complete` — filtered at Phase 2.

## Worktree lifecycle

### Create

```bash
create_scope_worktree() {
    local scope_id="$1"
    local baseline_sha="$2"
    local session_id="$3"

    local branch="iteratotron/${session_id}/${scope_id}"
    local worktree_path=".iteratotron/${session_id}/worktrees/${scope_id}"

    git worktree add -b "$branch" "$worktree_path" "$baseline_sha"

    # Mirror the scope record into the worktree so the subagent has it
    mkdir -p "${worktree_path}/.iteratotron"
    cp "${session_dir}/scopes/${scope_id}.md" \
       "${worktree_path}/.iteratotron/scope-context.md"

    # Mirror the pre-computed gap inventory + stop-bias findings
    cp "${session_dir}/scopes/${scope_id}-gaps.md" \
       "${worktree_path}/.iteratotron/gap-inventory.md"
    cp "${session_dir}/scopes/${scope_id}-stopbias.md" \
       "${worktree_path}/.iteratotron/stop-bias-findings.md"

    # Ensure the iterate skill's iteration-log location exists; if the
    # scope has a prior log, copy it forward so the subagent sees
    # historical entries (per iterate's "trusted sources" rule).
    if [[ -f "${worktree_path}/$(jq -r .iteration_log "${session_dir}/scopes/${scope_id}.json")" ]]; then
        true  # log exists in worktree (cheap, since worktree is hardlinked)
    fi

    echo "$worktree_path"
}
```

Notes:

- Worktrees are created from `baseline_sha`, NOT from `HEAD`. The
  baseline is fixed at session start so all subagents see a consistent
  starting state.
- Compile caches: same as bug-burndown — pre-warm with
  `cargo build` once on baseline; the resulting `target/` is hardlinked
  into each new worktree.
- Subagents may modify their worktree's `target/`; this does not
  affect other worktrees (each has its own).

### Destroy (success path)

After Phase 7 APPROVED and successful merge to integration:

```bash
destroy_scope_worktree() {
    local worktree_path="$1"
    local branch="$2"

    git worktree remove "$worktree_path" --force
    git branch -D "$branch" 2>/dev/null || true  # branch may be merged
}
```

### Retain (insufficient / blocked / needs_human)

DO NOT destroy. Move to a stable location and keep the branch alive:

```bash
mv "${session_dir}/worktrees/${scope_id}" \
   "${session_dir}/needs_human/${scope_id}"
# Branch retained; user can checkout to inspect or continue.
```

## The iterate-subagent invocation contract

Each subagent is launched via the `Task` tool with a prompt assembled
from the scope record. The prompt structure is fixed (see SKILL.md
§6c), but the content varies per scope.

### Prompt assembly

```python
def assemble_subagent_prompt(scope: dict) -> str:
    parts = []

    parts.append(f"You are running the `iterate` skill in maximum-rigor mode "
                 f"against scope {scope['id']} ({scope['name']}), inside an "
                 f"isolated git worktree.\n\n")
    parts.append(f"# Working directory\n{scope['worktree_path']}\n\n")
    parts.append(f"# Scope\n")
    parts.append(f"- Kind: {scope['kind']}\n")
    parts.append(f"- Path(s): {scope['primary_path']}\n")
    parts.append(f"- Language: {scope['language']}\n")
    parts.append(f"- Branch: {scope['branch']}\n")
    parts.append(f"- Iteration log: {scope['iteration_log']}\n\n")

    parts.append(f"# Linked design artefacts\n")
    for k, v in scope['linked_artefacts'].items():
        parts.append(f"- {k}: {v}\n")
    parts.append("\n")

    if scope['needs_all_aboard']:
        parts.append("# STEP 0 OVERRIDE\n\n")
        parts.append("This scope is missing one or more required documentation\n")
        parts.append("artefacts. Before starting your iterate loop:\n\n")
        parts.append("1. Invoke /all-aboard to bootstrap missing artefacts.\n")
        parts.append("2. After /all-aboard returns, proceed to iterate's Step 1.\n\n")

    parts.append("# Pre-computed gap inventory\n\n")
    parts.append("Use this as your starting list. iterate's Step 1 ('Assess\n")
    parts.append("Current State') is partially pre-computed; you do NOT need\n")
    parts.append("to re-run baseline verification per iterate's verification\n")
    parts.append("budget rule.\n\n")
    parts.append(load_file(scope['gap_inventory_path']))
    parts.append("\n\n")

    parts.append("# Pre-computed stop-bias-pattern findings\n\n")
    parts.append("Severity-lifted findings (documentation lies about reality)\n")
    parts.append("are P0. Address them first within iterate's priority order.\n\n")
    parts.append(load_file(scope['stop_bias_findings_path']))
    parts.append("\n\n")

    if scope['recurrence']['recurring']:
        parts.append("# THIS SCOPE WAS PREVIOUSLY CLAIMED COMPLETE\n\n")
        parts.append(f"Prior completion: {scope['recurrence']['prior_log_match']}\n")
        parts.append(f"Prior fix SHA: {scope['recurrence']['prior_fix_sha']}\n")
        parts.append(f"What changed since: {scope['recurrence']['diff_since']}\n\n")
        parts.append("Investigate why the prior completion is no longer\n")
        parts.append("accurate. Possible causes:\n")
        parts.append("- New stop-bias patterns introduced by other work.\n")
        parts.append("- Spec/ADR/threat-model updated, leaving impl behind.\n")
        parts.append("- The prior implementation was hallucinated; it never\n")
        parts.append("  actually worked, just passed the stop hook.\n\n")
        parts.append("Prior LESSONS_LEARNED:\n")
        parts.append(scope['recurrence']['prior_lessons'])
        parts.append("\n\n")

    parts.append("# Constraints\n\n")
    parts.append("- Work ONLY inside the working directory above.\n")
    parts.append("- Follow `iterate`'s Single-Turn Autonomy rules — never\n")
    parts.append("  stop between iterations.\n")
    parts.append("- Honour `iterate`'s verification-budget rule — crate-scoped\n")
    parts.append("  checks, never workspace-wide.\n")
    parts.append("- Honour `iterate`'s stopping-bias kill list — no banned\n")
    parts.append("  phrases, no iteration ordinals, no 'deferred is a stopping\n")
    parts.append("  reason'.\n")
    parts.append("- Run your stop hook (`check-completion.py`) before declaring\n")
    parts.append("  done.\n\n")

    parts.append("# Return contract\n\n")
    parts.append("When your stop hook passes:\n")
    parts.append("1. Final iteration-log entry: `complete (YYYY-MM-DD): all\n")
    parts.append("   Step 6 criteria passed, stop hook confirmed.`\n")
    parts.append("2. List of commits on this branch.\n")
    parts.append("3. Short manifest of changes (files, gap categories closed,\n")
    parts.append("   stop-bias patterns eliminated, doc artefacts touched).\n\n")
    parts.append("If you hit a genuine blocker (the only valid stops per\n")
    parts.append("iterate's rules):\n")
    parts.append("- State the blocker in one sentence.\n")
    parts.append("- Describe what would unblock.\n")
    parts.append("- Append a LESSONS_LEARNED entry.\n")

    return "".join(parts)
```

### Subagent isolation

Launch via `Task` with:

- Working directory: the worktree path.
- Context fork: yes (fresh context window).
- Tool allowance: same as iterate's `allowed-tools` plus
  `SkillInvocation` (for `/all-aboard`, `/spec-create`, etc.).
- Timeout: per-scope (default 90 min, configurable).

The subagent does NOT see the parent's plan, the scope queue, or other
subagents' progress. This is desirable — context isolation keeps each
iterate run honest about its own scope.

### Hook interaction

The iterate skill's frontmatter includes:

- `SessionStart` hook (re-asserts iterate's protocol on context
  compaction).
- `PreToolUse` hook (`context-watchdog.py`).
- `Stop` hook (`check-completion.py`).

These run inside the subagent's context. iteratotron does not interfere
with them. The Stop hook is the authoritative completion signal that
gates Phase 7 entry.

### What the subagent returns to iteratotron

When the subagent's loop ends (stop hook passed OR genuine blocker), it
emits a structured "return" message that the parent parses. Suggested
format:

```yaml
# At the end of the subagent's final message:
---
iteratotron_return:
  scope_id: SCOPE-7f3a9c1e
  outcome: complete | blocked
  branch: iteratotron/20260516-152217-bf2a/SCOPE-7f3a9c1e
  commits: [a3f8e2d1, b9c4..., d8e7...]
  stop_hook_verdict: passed
  manifest:
    files_changed: 12
    tests_added: 18
    gaps_closed:
      P0: 4
      P1: 12
      P2: 6
      P3: 2
    stop_bias_eliminated:
      stub: 3
      placeholder: 2
      partial: 1
    doc_artefacts:
      created: [docs/adr/0061-...]
      updated: [docs/specs/agent-compiler.md]
  lessons_learned:
    - "Stub implementations in trait impls were paired with doc
       comments claiming retry logic; both had to be fixed."
  blocker: null  # only present if outcome=blocked
---
```

The parser is forgiving (the structured block is parsed if present;
otherwise the parent uses heuristics on the prose). If the return is
malformed, the scope goes to `needs_human` with a note.

## The dispatch loop in detail

```python
def dispatch_loop(queue, parallelism=3, session_budget_s=14400):
    start = time.time()
    in_flight = {}              # scope_id -> handle
    blocked_for_now = set()
    seq_pending = []            # for sequential-dispatch scopes
                                # (needs_all_aboard)

    while True:
        elapsed = time.time() - start
        if elapsed >= session_budget_s:
            log("session budget exhausted; draining")
            break

        # If any needs_all_aboard scopes are pending, run them serially
        # BEFORE filling other slots (per Phase 5 sanity check).
        if seq_pending and not in_flight:
            scope = seq_pending.pop(0)
            run_synchronously(scope)
            continue

        # Fill parallel slots
        while len(in_flight) < parallelism:
            scope = pick_dispatchable(queue, in_flight, blocked_for_now)
            if scope is None:
                break
            if scope.needs_all_aboard:
                seq_pending.append(scope)
                continue
            launch_in_worktree(scope)
            in_flight[scope.id] = scope

        if not in_flight and not seq_pending:
            log("queue exhausted; exiting")
            break

        # Wait for any subagent to finish
        finished = wait_for_any(in_flight, timeout_s=60)
        if finished is None:
            continue

        for scope_id in finished:
            scope = in_flight.pop(scope_id)
            result = collect_subagent_return(scope)
            if result.outcome == 'complete':
                review_verdict = run_adversarial_review(scope, result)
                if review_verdict == 'APPROVED':
                    reconcile_success(scope, result)
                elif review_verdict == 'INSUFFICIENT':
                    requeue_with_lessons(scope, result, review_verdict)
                else:  # NEEDS_HUMAN
                    move_to_needs_human(scope, result)
            else:  # blocked
                handle_blocker(scope, result)

    # Drain in-flight
    for scope_id, scope in in_flight.items():
        result = wait_for(scope, timeout_s=300)
        if result is None:
            mark_status(scope, 'interrupted')
        else:
            # same reconcile path
            ...
```

### `pick_dispatchable` logic

A scope is dispatchable when ALL hold:

1. `status` is `queued`, `insufficient` (re-attempt), or `re-evaluate`.
2. Every entry in `dependency.blocked_by` has `status == complete`.
3. `requires_human_review == False`.
4. `attempt_count < max_attempts` (default 3).
5. Not in `blocked_for_now` cooldown.

Within dispatchable scopes, sort by `priority_rank` ascending and
return the lowest-rank.

### Time budget handling

When `(elapsed > 0.9 * session_budget_s)`:

- Stop accepting new dispatches.
- Allow in-flight subagents to complete (iterate's loop will honour
  its own circuit breaker eventually).
- Move queued scopes to `resumable_queue.jsonl`.

The iterate skill is responsible for its own internal time management;
iteratotron does NOT impose iterate-internal timeouts.

## Merge protocol

### Success path

```bash
reconcile_complete() {
    local scope_id="$1"
    local worktree_path="$2"
    local branch="$3"

    # Capture all commits in the branch
    local commits
    commits="$(git -C "$worktree_path" rev-list --reverse "$baseline_sha".."$branch")"

    cd "$repo_root" || return 1

    # Attempt merge with a structured commit message
    if git merge --no-ff "$branch" \
        -m "iteratotron(${scope_id}): drive ${scope_name} to completion

$(cat "${worktree_path}/.iterate/iteration-log.md" | tail -20)

Scope: ${scope_id}
Session: ${session_id}
Adversarial review: APPROVED"; then

        # Re-run scope-scoped checks against integration HEAD
        if rerun_scope_checks "$scope_id"; then
            mark_status "$scope_id" "complete" \
                --completion-sha "$(git rev-parse HEAD)"
            destroy_scope_worktree "$worktree_path" "$branch"
            update_completion_log "$scope_id" "complete" "$commits"
            re_evaluate_dependents "$scope_id"
        else
            git reset --hard HEAD~1
            mark_status "$scope_id" "completion_lost_in_merge"
            log "WARNING: ${scope_id} completion did not hold in integration"
        fi
    else
        git merge --abort
        mark_status "$scope_id" "needs_rebase"
    fi
}
```

### Conflict path

```bash
reconcile_conflict() {
    local scope_id="$1"
    local worktree_path="$2"

    # Auto-rebase once
    git -C "$worktree_path" fetch origin "$integration_branch" 2>/dev/null
    if git -C "$worktree_path" rebase "$integration_branch"; then
        reconcile_complete "$@"
    else
        git -C "$worktree_path" rebase --abort
        mark_status "$scope_id" "needs_human" \
            --reason "rebase conflict against in-session scope merges"
        # Worktree retained for human resolution
    fi
}
```

Semantic conflicts between iterate runs (e.g., two scopes both modify
the same trait in incompatible ways) require human resolution. The
auto-rebase only resolves textual conflicts; if rebase fails, the
scope is escalated.

### Cross-scope regression detection

After every successful merge, re-evaluate scopes whose
`dependency.related_scopes` includes the just-merged scope:

```bash
reevaluate_related() {
    local merged_scope_id="$1"

    local related
    related="$(jq -r --arg id "$merged_scope_id" '
        select(.dependency.related_scopes[]? == $id) | .id
    ' "${session_dir}/scope_queue.jsonl")"

    for scope_id in $related; do
        local current_status
        current_status="$(get_status "$scope_id")"
        if [[ "$current_status" == "complete" ]]; then
            # Run the scope's iteration-log claim against current state
            if ! verify_completion_claim "$scope_id"; then
                # The merged scope broke a previously-complete scope
                git revert --no-edit HEAD
                mark_status "$merged_scope_id" "broke_related"
                requeue "$merged_scope_id" --escalate
                log "REGRESSION: ${merged_scope_id} broke ${scope_id}; reverted"
                # Note: we revert the merge, not the related scope's prior fix
            fi
        fi
    done
}
```

This is the cross-scope safety net. Less common than bug-burndown's
because iterate scopes are designed to be more independent, but
inevitable when feature-area scopes overlap with crate scopes.

## Failure modes and recoveries

| Failure                              | Recovery                                                              |
|--------------------------------------|-----------------------------------------------------------------------|
| Worktree creation fails              | Reduce parallelism by 1; retry; 3 fails → halt                        |
| Subagent never returns               | Timeout (default 90 min); mark interrupted; retain wt                 |
| Subagent's stop hook never passes    | Timeout fires → mark needs_human; retain wt                            |
| Subagent reports blocker             | Mark blocked; retain wt; do not re-dispatch                            |
| Phase 7 INSUFFICIENT                 | Requeue with new findings; attempt_count++                            |
| Phase 7 NEEDS_HUMAN                  | Move to needs_human; do not re-dispatch                                |
| Merge conflict                       | Auto-rebase once; if conflict → needs_human                            |
| Scope's completion lost post-merge   | Revert; mark completion_lost_in_merge                                 |
| Cross-scope regression               | Revert; escalate; requeue                                              |
| Test cache corruption                | Delete affected wt's `target/`; subagent rebuilds                      |
| iterate skill version mismatch       | Surface in report; halt new dispatches; user decision                  |
| `/all-aboard` failure                | Mark needs_human (doc creation requires user attention)                |

## Parallelism tuning

Same considerations as bug-burndown — default 3, max 5 without override.

iterate runs are CPU-heavy (frequent test/build cycles per iteration).
A single iterate subagent on a ExampleApp-like Rust workspace can saturate
2-4 cores during build phases. Practical recommendation:

```bash
mem_gb=$(($(free -g | awk '/^Mem:/ {print $2}')))
cores=$(nproc)
max_parallel=$(( mem_gb / 6 < cores / 3 ? mem_gb / 6 : cores / 3 ))
max_parallel=$(( max_parallel > 5 ? 5 : max_parallel ))
max_parallel=$(( max_parallel < 1 ? 1 : max_parallel ))
```

iterate's per-subagent compile is heavier than bugfix's because iterate
runs many cycles. For ExampleApp specifically (tokio + SurrealDB + Rig +
17 agents), cap at 2 unless the workstation has 32GB+ RAM and a fast
NVMe SSD.

## Cleanup at session end

- Worktrees for `complete` scopes destroyed at reconcile time.
- Worktrees for `needs_human` / `blocked` / `needs_rebase` moved to
  `${session_dir}/needs_human/${scope_id}` (plain dirs, not git
  worktrees). Branches kept.
- Worktrees for `insufficient` scopes that were re-queued and
  eventually completed: destroyed normally. If they timed out before
  completion, treated as `needs_human`.
- All `iteratotron/*` branches for `complete` scopes are deleted
  (merged into integration).
- Session dir added to `.gitignore` if not already.

---

## Iterate-subagent invocation contract

The orchestrator dispatches each scope via the `Agent` tool with the `iterate`
skill loaded. The prompt is assembled deterministically from the scope record:

```
You are running the `iterate` skill in maximum-rigor mode against
a single scope, inside an isolated git worktree.

# Working directory
${worktree_path}

# Scope
Scope ID:      ${scope.id}
Kind:          ${scope.kind} (cargo-crate / feature-area / story / etc)
Path(s):       ${scope.paths}
Iteration log: ${worktree_path}/.iterate/iteration-log.md

# Linked design artefacts
Spec:         ${scope.linked.spec}
ADRs:         ${scope.linked.adrs}
Threat model: ${scope.linked.threat_model}
Stories:      ${scope.linked.stories}

${if scope.needs_all_aboard:}
**STEP 0 OVERRIDE:** This scope is missing one or more of {spec, ADRs,
threat model}. Before starting your iterate loop, invoke /all-aboard
to bootstrap them. Only proceed to iterate's Step 1 after /all-aboard
returns successfully.
${endif}

# Pre-computed gap inventory (don't re-derive; use as a starting list)
${gap inventory from Phase 3, in iterate's expected output format}

# Stop-bias-pattern findings to address as P0/P1
${stop-bias findings, with severity-lifted ones at top}

${if scope.recurrence.recurring:}
**THIS SCOPE WAS PREVIOUSLY CLAIMED COMPLETE.**
Prior completion: ${scope.recurrence.prior_log_match}
Prior fix SHA:    ${scope.recurrence.prior_fix_sha}
What changed since:
${list of commits since prior completion that touched this scope}

The prior completion claim is no longer accurate. Investigate why —
new stop-bias patterns introduced, spec updated leaving the
implementation behind, or hallucinated implementation that never
actually worked.

Prior LESSONS_LEARNED:
${quoted from prior log entry}
${endif}

# Constraints

- Work ONLY inside ${worktree_path}.
- Follow `iterate`'s Single-Turn Autonomy rules — don't stop between
  iterations.
- Honour `iterate`'s verification-budget rule — crate-scoped checks,
  never workspace-wide.
- Honour `iterate`'s stopping-bias kill list — no banned phrases, no
  iteration ordinals.
- Run your stop hook (`check-completion.py`) before declaring done.
- Branch you're on: ${branch}.

# Return contract

When your stop hook passes:

1. Final one-line iteration-log entry: `complete (YYYY-MM-DD): all
   Step 6 criteria passed, stop hook confirmed.`
2. The list of commits on ${branch}.
3. A short manifest of what changed: files touched, gaps closed by
   category, stop-bias patterns eliminated.
4. Status of doc artefacts: which were created/updated, which were
   merely referenced.

If you hit a genuine blocker (the only valid stops per iterate's
rules):

- State the blocker in one sentence.
- Describe what would unblock (user decision, missing credential,
  external dep).
- Append a LESSONS_LEARNED entry.

If your stop hook BLOCKS you, treat that as iterate intends — keep
going within the same turn. Don't return control to the parent until
the hook passes OR a genuine blocker is hit.
```

### Subagent isolation

When invoking via the `Agent` tool, set:

- **Working directory** to the worktree path.
- **Context fork**: subagent gets a fresh context. It doesn't see the
  parent's plan or other subagents' work. That's desirable for honest
  verification.
- **Tool allowance**: same as the `iterate` skill's `allowed-tools`
  list, scoped to the worktree.

### Time budget per subagent

- Per-scope timeout: 90 minutes default (configurable via manifest).
- Session timeout: as specified in arguments (default 4 hours).
- When the session budget's nearly exhausted, stop accepting new
  dispatches; let in-flight subagents complete to their stop-hook
  verdict. Move remaining queued scopes to `resumable_queue.jsonl`.
