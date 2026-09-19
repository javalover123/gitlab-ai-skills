# Dispatcher mechanics

This reference is loaded on demand from the `bug-burndown` skill during
Phases 6-7. It specifies the parallel dispatch loop: worktree creation,
subagent invocation, result collection, branch merging, and conflict
handling.

The goal is to run N bugfix subagents simultaneously without their work
colliding, while preserving every guarantee the `bugfix` skill makes
about evidence and verification.

## Core principle: branch isolation via git worktrees

Each dispatched bug gets its own git worktree, branched from the
session's `baseline_sha`. The subagent operates entirely within that
worktree; it cannot see or touch the other subagents' work. When the
subagent finishes, the parent merges its branch back into the
integration branch.

This gives us:

- **True parallelism** — N file systems, N test suites, N caches; no
  contention on `target/` or `__pycache__/`.
- **Clean revertability** — a bad fix can be dropped by deleting the
  worktree and branch; the integration branch is never touched until
  reconciliation succeeds.
- **Honest test runs** — each subagent's "all four pyramid layers
  green" assertion is against its own checkout, not a shared workspace
  contaminated by other in-flight changes.

The alternative (a single workspace with sequential subagents) loses
all three properties for ~30% throughput. Not worth it.

## Worktree lifecycle

### Create

```bash
create_worktree() {
    local bug_id="$1"
    local baseline_sha="$2"
    local session_id="$3"
    local worktree_root="${4:-.bug-burndown/${session_id}/worktrees}"

    local branch="bugfix/${session_id}/${bug_id}"
    local worktree_path="${worktree_root}/${bug_id}"

    # Create branch at baseline, with the worktree
    git worktree add -b "$branch" "$worktree_path" "$baseline_sha"

    # Initialise the bugfix skill state inside the worktree
    mkdir -p "${worktree_path}/.bugfix"
    cp "${session_id_dir}/findings/${bug_id}.md" \
       "${worktree_path}/.bugfix/bug-context.md"

    # Touch the bugfix-active marker (for require-dod hook)
    touch "${worktree_path}/.bugfix/active-${SUBAGENT_SESSION_ID}"

    echo "$worktree_path"
}
```

Worktree creation is fast (seconds) because git uses hard links by
default. Compile caches are NOT shared; each worktree builds from
scratch the first time. This is the dominant time cost — consider:

- **Pre-warm the cache** before the first dispatch by running
  `cargo build` once on the baseline; the resulting `target/` is
  hard-linked into each new worktree.
- **Use `sccache`** or `cargo-mold` to share compile artefacts across
  worktrees. Set `RUSTC_WRAPPER=sccache` in the environment passed to
  each subagent.

### Destroy (success path)

```bash
destroy_worktree() {
    local worktree_path="$1"
    local branch="$2"

    git worktree remove "$worktree_path" --force
    git branch -D "$branch" 2>/dev/null || true   # branch may be merged
}
```

Worktrees are destroyed only after reconciliation succeeds (Phase 7a)
and the branch is merged. Destroying earlier loses the fix.

### Retain (blocked / human-review path)

When a subagent reports BLOCKED or INSUFFICIENT, do NOT destroy the
worktree. It contains:

- The diagnostic instrumentation the subagent added during Phase 2-4.
- The partial fix attempt (in case the human can continue from there).
- The LESSONS_LEARNED log.

These are valuable to a human reviewer. Move the worktree to
`${session_dir}/needs_human/${bug_id}/` and record the location in
`report.md`.

## Subagent invocation

The dispatcher launches each bugfix subagent via the `Agent` tool,
with the `bugfix` skill loaded. The prompt is assembled deterministically
from the queue entry.

### Prompt template

```
You are running the `bugfix` skill in maximum-rigor mode, against
a single bug, inside an isolated git worktree.

# Working directory
${worktree_path}

# Bug to fix
ID:       ${bug.id}
Title:    ${bug.title}
Severity: ${bug.severity}
Kind:     ${bug.kind}

## Full bug context (from triage)

${bug context markdown — the full findings record, including raw
extracts from each source that observed this bug}

## Prior art

${if bug.recurrence.recurring:}
**THIS BUG HAS BEEN SEEN BEFORE.**
Prior bugfix log entry: ${bug.recurrence.prior_log_match}
Prior fix SHA: ${bug.recurrence.prior_fix_sha}
Prior status: ${bug.recurrence.prior_status}
${if prior_status == "fixed":}
This is a REGRESSION. The prior fix did not hold, OR a new code path
re-introduced the same defect. Investigate why — the prior fix's
LESSONS_LEARNED are below.
${endif}

Prior LESSONS_LEARNED:
${quoted log entry}
${endif}

${if bug.dependency.related:}
## Related bugs in this session
${list of related bug IDs with one-line titles}
${endif}

${if bug.recurrence.pattern_id:}
## Pattern siblings
This bug matches pattern ${pattern_id}. Other sites with the same
pattern (some may be in other worktrees right now):
${list of sites}
Use the same structural approach for consistency, but produce your
own reproducer test for this specific site.
${endif}

# Constraints

- Work ONLY inside ${worktree_path}. Do not edit files outside.
- All four pyramid layers must be green before declaring done.
- Mutation survivors on changed lines: 0.
- Adversarial review must return APPROVED, not "looks reasonable".
- Documentation deltas (ADR, spec, threat model, user story) MUST be
  filed via the companion skills (`/adr-create`, `/spec-create`, etc.)
  if triggered. The skills work fine inside a worktree.
- Branch you are on: ${branch}. Commit your fix to this branch; do
  not push to `${integration_branch}` directly.

# Return contract

When you complete, emit:

1. The `bugfix` Definition-of-Done checklist with every box ticked and
   cited evidence (test output, file:line, command results).
2. The final commit SHA(s) on ${branch}.
3. Any LESSONS_LEARNED entries (these will be aggregated into the
   bugfix log).
4. Any companion artefacts created (ADR paths, spec scenario paths,
   etc.).

If you hit the circuit breaker (5 hypotheses falsified, all four
context rungs exhausted, reproducer not deterministic), emit a BLOCKED
report with:

- The simplest experiment that would unblock you.
- The specific tool, access, or piece of information you need.
- LESSONS_LEARNED so the next session does not retry the same approach.

If your Phase 8 adversarial review returns INSUFFICIENT, do NOT force
APPROVED. Return INSUFFICIENT with the named phase to revisit.
```

### Subagent isolation

When invoking via the `Agent` tool, set:

- **Working directory** to the worktree path. The subagent should
  treat that as the repo root.
- **Context fork**: subagent gets a fresh context window. It does not
  see the parent's plan or other subagents' work. This is desirable
  for honest verification.
- **Tool allowance**: same as the `bugfix` skill's `allowed-tools`
  list, scoped to the worktree.

## The dispatch loop

```python
def dispatch_loop(queue, parallelism=5, time_budget_s=7200):
    start = time.time()
    in_flight = {}              # bug_id -> subagent_handle
    finished_queue = []
    blocked_for_now = set()     # bugs whose blockers haven't fixed yet

    while True:
        elapsed = time.time() - start
        if elapsed >= time_budget_s:
            log("time budget exhausted; draining in-flight")
            break

        # Fill available slots
        while len(in_flight) < parallelism:
            next_bug = pick_dispatchable(queue, in_flight, finished_queue,
                                         blocked_for_now)
            if next_bug is None:
                break  # no dispatchable bug right now
            worktree = create_worktree(next_bug.id, baseline_sha, session_id)
            handle = launch_subagent(next_bug, worktree)
            next_bug.status = "in_flight"
            next_bug.worktree = worktree
            next_bug.attempt_count += 1
            write_queue_update(next_bug)
            in_flight[next_bug.id] = handle

        if not in_flight:
            log("no in-flight subagents and nothing dispatchable; exiting")
            break

        # Wait for any subagent to finish
        finished_id, result = wait_for_any(in_flight, timeout_s=60)
        if finished_id is None:
            continue   # poll cycle; check budget again

        del in_flight[finished_id]
        reconcile(finished_id, result)    # Phase 7

    # Drain in-flight gracefully
    for bug_id, handle in in_flight.items():
        result = wait_for(handle, timeout_s=300)
        if result is None:
            mark_bug_status(bug_id, "interrupted")
        else:
            reconcile(bug_id, result)
```

### `pick_dispatchable` logic

A bug is dispatchable when ALL hold:

1. `status == "queued"` or `status == "re-evaluate"`.
2. Every entry in `dependency.blocked_by` has `status == "fixed"`.
3. `requires_human_review == False`.
4. `bug.id not in blocked_for_now` (recent failures need cooldown).

Among dispatchable bugs, pick the one with the lowest `priority_rank`.

If no bug is dispatchable but the in-flight set is non-empty, return
`None` and wait — once an in-flight bug finishes, new bugs may become
dispatchable.

### Slot allocation across sources

Optionally, enforce per-source slot quotas to avoid one collector's
output starving others. For example: at most 1 of 3 slots may be on
`spec-drift` findings at once (they're expensive). Encode this as a
manifest field if useful.

## Slot semaphore integration

When a verification harness is on PATH, the dispatcher does NOT pre-acquire
heavy compile/test slots before launching a subagent. The subagent
acquires its own slots inside the bugfix skill via
the verification harness's `verify run` command (see the `bugfix` skill's "Verification
through verify run" section). This is the right shape because:

- Most subagent wall-clock time is non-verification (reading code,
  editing, thinking). Pre-acquiring a heavy slot for the whole
  subagent lifetime would idle 50–80% of the slot budget.
- The slot semaphore inside `verify run` bounds the actually-expensive
  work (cargo build, cargo test, pytest, vitest), so cranking
  `parallelism` to 5 doesn't risk OOM.
- Verification commands run by separate subagents on the same
  worktree HEAD sha cooperatively cache-hit each other via the
  verify cache, so identical work isn't repeated.

### Capability check at Phase 1d

Before dispatching, query the harness's slot-status command and compare
capacity to the requested parallelism:

```bash
# $HARNESS is your project's verification-harness binary, if it provides one.
capacity=$("$HARNESS" --work-dir .bug-burndown/<session-id> slot status | jq .capacity)
if (( capacity < 2 * parallelism )); then
    parallelism=$(( capacity / 2 ))
    parallelism=$(( parallelism < 1 ? 1 : parallelism ))
    log "parallelism reduced to $parallelism — reason: slot capacity $capacity < 2 × requested"
fi
```

The `2 × parallelism` rule: even when
subagents each acquire only one medium slot (weight 2) at a time, you
want headroom for the case where two subagents both happen to be in
their verification phase. A capacity of 8 supports 4 subagents
comfortably; 5 only if you accept one will block briefly.

### Prewarm

Before launching the first subagent, run the active language profile's
prewarm command (typically `cargo build --workspace`) once on the
baseline. This populates `sccache` / `GOCACHE` so the first subagent
to verify doesn't pay full compile cost. The prewarm step is best-effort:
if it fails, log a warning and continue — a cold cache costs time, not
correctness.

### Slot semaphore unavailable

If a verification harness isn't on PATH (e.g. running bug-burndown outside a
a large checkout), cap `parallelism` at 2 and emit:

```
slot semaphore unavailable — capping parallelism at 2
```

Two concurrent full workspace builds is the rough ceiling for a 16 GB
host without OOM. Above that, install a verification harness or run a
single subagent at a time.

## Reconciliation (Phase 7 mechanics)

### Success: merge protocol

```bash
reconcile_success() {
    local bug_id="$1"
    local worktree_path="$2"
    local branch="$3"

    # Capture the fix SHA(s)
    local fix_sha
    fix_sha="$(git -C "$worktree_path" rev-parse "$branch")"

    # Run sanity in the integration branch BEFORE merging
    # (full test suite is the subagent's job; this is a quick gate)
    cd "$repo_root" || exit 1

    # Attempt merge
    if git merge --no-ff "$branch" \
        -m "fix(${bug_id}): ${bug.title}

$(cat "${worktree_path}/.bugfix/dod-"*.md)

Closes: ${bug_id}
Session: ${session_id}"
    then
        # Re-run the bug's reproducer against the merged state
        if rerun_bug_reproducer "$bug_id" "$fix_sha"; then
            mark_bug_status "$bug_id" "fixed" --fix-sha "$fix_sha"
            destroy_worktree "$worktree_path" "$branch"
            update_bugfix_log "$bug_id" "fixed" "$fix_sha"
            reevaluate_dependents "$bug_id"
        else
            # Reproducer doesn't pass in integration; revert
            git reset --hard HEAD~1
            mark_bug_status "$bug_id" "reproducer_lost_in_merge"
            log "WARNING: ${bug_id} reproducer passed in worktree, failed in integration"
        fi
    else
        # Merge conflict
        git merge --abort
        mark_bug_status "$bug_id" "needs_rebase"
        log "merge conflict on ${bug_id}; leaving worktree for rebase"
        # Worktree retained for the next loop iteration to retry
    fi
}
```

### The conflict-rebase loop

When a merge conflicts, the dispatcher attempts auto-rebase ONCE:

```bash
git -C "$worktree_path" fetch origin
git -C "$worktree_path" rebase "$integration_branch"
if [[ $? -eq 0 ]]; then
    # Rebase succeeded; re-attempt merge
    reconcile_success "$@"
else
    git -C "$worktree_path" rebase --abort
    mark_bug_status "$bug_id" "needs_human" \
        --reason "rebase conflict against in-session fixes"
fi
```

If rebase fails (genuine semantic conflict between two in-session
fixes), surface to human review. Do NOT attempt to auto-resolve —
semantic conflicts between fixes are exactly the situation where the
burndown skill should pause.

### Regression detection (cross-fix)

After every successful merge, run the test suite of the *related*
bugs from this session — entries with overlapping blast radius:

```bash
detect_introduced_regressions() {
    local merged_bug_id="$1"
    local affected_bugs
    affected_bugs="$(jq -r --arg id "$merged_bug_id" '
        select(.dependency.related[] == $id)
        | .id
    ' "${session_dir}/queue.jsonl")"

    for related in $affected_bugs; do
        if [[ "$(get_status "$related")" == "fixed" ]]; then
            # Re-run that bug's reproducer; if it now fails, regression
            if ! rerun_bug_reproducer "$related"; then
                # Revert the most-recent merge
                git revert --no-edit HEAD
                mark_bug_status "$merged_bug_id" "introduced_regression"
                requeue_bug "$merged_bug_id" --escalate-severity
                log "REGRESSION: ${merged_bug_id} broke ${related}; reverted"
            fi
        fi
    done
}
```

This is the cross-fix safety net. It catches the case where two
parallel fixes individually pass their gates but interact badly when
merged.

## Failure modes and recoveries

| Failure                             | Recovery                                              |
|-------------------------------------|-------------------------------------------------------|
| Worktree creation fails (disk full) | Reduce parallelism by 1; retry; if 3 fails, halt     |
| Subagent never returns              | Timeout (default 90 min); mark interrupted; retain wt|
| Subagent crashes mid-run            | Mark crashed; retain worktree; do not re-dispatch yet|
| Merge conflict                      | Auto-rebase once; if conflict persists → needs_human |
| Reproducer fails post-merge         | Revert; mark `reproducer_lost_in_merge`; investigate |
| Regression introduced               | Revert; escalate severity; re-queue                   |
| Subagent reports BLOCKED            | Mark blocked; retain worktree; do not re-dispatch    |
| Subagent reports INSUFFICIENT       | Mark blocked; retain wt; if attempt_count<2, re-queue|
| Test cache corruption               | Delete affected wt's `target/`; let subagent rebuild  |
| Auth token expired (gh, GitLab)     | Pause dispatch; prompt user; resume on refresh        |

## Parallelism tuning

Default `parallelism = 5`. The slot semaphore
absorbs the compile/test RAM pressure that previously made `3` the
safe cap, so cranking subagent fan-out to `5` is the new baseline.

- **N=1**: degenerate; use direct bugfix invocation instead.
- **N=2**: fallback when a verification harness isn't on PATH and the host
  is RAM-constrained (< 16 GB). Without the slot semaphore, every
  worktree's verify command competes raw for RAM.
- **N=5** (default with slot semaphore active): good for any modern
  dev workstation. Most subagents spend most of their wall-clock time
  on non-verification work; the slot semaphore serializes the heavy
  parts so 5 in-flight subagents only stress the host as much as 1–2
  full verify runs.
- **N>5**: requires an explicit `parallel:N` argument AND the harness's
  slot-status command reporting `capacity >= 2 × N`. Merge contention
  typically becomes the dominant cost above 5; conflicts get frequent.

The capability check runs at Phase 1d:

```bash
# $HARNESS is your project's verification-harness binary, if it provides one.
if command -v "$HARNESS" >/dev/null; then
    capacity=$("$HARNESS" --work-dir .bug-burndown/<session-id> slot status | jq .capacity)
    if (( capacity < 2 * parallelism )); then
        parallelism=$(( capacity / 2 ))
        parallelism=$(( parallelism < 1 ? 1 : parallelism ))
    fi
else
    mem_gb=$(($(free -g | awk '/^Mem:/ {print $2}')))
    parallelism=$(( mem_gb < 16 ? 2 : 3 ))  # without slot semaphore, cap at 3
fi
```

With a slot-aware harness, the semaphore makes `parallelism=5`
safe on any 32 GB+ host. Below that, fall back to the
no-semaphore branch and live with `parallelism=2` or 3.

## Cleanup at session end

After Phase 8:

1. Worktrees for `fixed` bugs were destroyed at reconcile time.
2. Worktrees for `needs_human` bugs are moved to a stable location:
   ```bash
   mv "${session_dir}/worktrees/${bug_id}" \
      "${session_dir}/needs_human/${bug_id}"
   ```
   These are NOT git worktrees anymore (they're plain directories);
   the corresponding git branches remain so the user can `git checkout`
   them.
3. Branches for `fixed` bugs are deleted (merged into integration).
4. Branches for `needs_human` bugs are kept.
5. The session dir is added to `.gitignore` if not already there —
   it's session state, not source.
