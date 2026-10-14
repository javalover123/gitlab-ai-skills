#!/usr/bin/env python3
"""
Stop hook for the iteratotron skill.

Blocks Claude from ending the turn while the session's scope queue still has
dispatchable or in-flight work AND the session time budget hasn't been hit.
The queue is the deterministic completion oracle — Phase 5 populates it from
the gap audit, and the orchestrator's job is to drain it.

Reads `.iteratotron/CURRENT` to find the active session, then inspects
`.iteratotron/<session-id>/scope_queue.jsonl` and `state.json` (for
`started_at` and `budgets.time_budget_seconds` — see
references/state-schema.md). If any scope is in a non-terminal status
(queued / in_flight / re-evaluate / needs_rebase / introduced_regression),
and the time budget hasn't expired, the hook returns a `decision: block`
response telling Claude to keep dispatching.

Skipped when:
- The active session is subagent context (parent_task_id present) — the
  subagent runs `iterate`'s own hook, not the orchestrator's.
- `stop_hook_active` signals a stop attempt with no tool call since the
  last block — see should_skip()'s docstring for why that's safe.
- No `.iteratotron/CURRENT` exists (no active session).
- The session time budget is exhausted (returns approve with a note).

Configuration:
- Terminal statuses (treated as "done"): complete, blocked, needs_human,
  skipped_recently_complete, requires_human_review.
- Non-terminal statuses (treated as "still working"): queued, in_flight,
  re-evaluate, needs_rebase, introduced_regression (reverted and re-queued,
  so still unfinished).

Exit protocol per Claude Code hooks spec:
- Print JSON `{"decision": "block", "reason": "..."}` to stdout → keep going
- Print JSON `{"decision": "approve", "reason": "..."}` → allow stop
- Print empty JSON `{}` → no-op (default behaviour)
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

TERMINAL_STATUSES = {
    "complete",
    "blocked",
    "needs_human",
    "skipped_recently_complete",
    "requires_human_review",
}
NON_TERMINAL_STATUSES = {
    "queued",
    "in_flight",
    "re-evaluate",
    "needs_rebase",
    # A regression is reverted and re-queued, so it's unfinished work.
    "introduced_regression",
}


def read_hook_input():
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def emit_and_exit(output):
    print(json.dumps(output))
    sys.exit(0)


def should_skip(hook_input):
    """Skip when in subagent context, or when stop_hook_active signals the
    agent tried to stop again with zero tool calls since the last block.

    Per Claude Code's hooks reference, `stop_hook_active` is true only on
    a stop attempt that directly follows a block with no intervening tool
    call; Claude Code's own consecutive-continuation counter (the one
    behind its 8-attempt cap) resets on every tool call, and this flag
    tracks the same streak. So in a healthy loop — block, agent edits a
    file, agent tries to stop again — this flag is false on that next
    attempt, and the hook runs its normal gap check. It's only true when
    the agent ignored the block reason entirely and tried to stop again
    having done nothing; re-blocking in that exact case can't change the
    outcome, so approving is correct (Claude Code's own cap would force
    the turn to end after 8 such attempts regardless).
    """
    if hook_input.get("stop_hook_active"):
        return True
    if (
        hook_input.get("parent_task_id")
        or hook_input.get("agent_type")
        or hook_input.get("is_subagent")
    ):
        return True
    return False


SESSION_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")


def find_active_session_dir():
    """Resolve the active session directory.

    Prefers `.iteratotron/CURRENT` (a file containing the session id —
    see references/state-schema.md "Active-session pointer"), since
    that's the canonical, unambiguous source of truth Phase 1 writes.
    Falls back to the most recently modified `.iteratotron/<session-id>/`
    directory so the hook still engages even if that pointer was never
    written (e.g. an older session bootstrapped before this convention,
    or a step that skipped writing it) rather than silently approving
    every stop because load_session_state() found nothing.
    """
    base = Path(".iteratotron")
    current_file = base / "CURRENT"
    if current_file.is_file():
        session_id = current_file.read_text().strip()
        if session_id:
            session_dir = base / session_id
            if session_dir.is_dir():
                return session_dir

    if not base.is_dir():
        return None
    candidates = [
        d for d in base.iterdir() if d.is_dir() and SESSION_ID_RE.match(d.name)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.stat().st_mtime)


def load_session_state():
    """Return (session_dir, queue_entries, manifest) or None if no active session."""
    session_dir = find_active_session_dir()
    if session_dir is None:
        return None

    queue_path = session_dir / "scope_queue.jsonl"
    if not queue_path.is_file():
        # Phase 5 hasn't produced the queue yet — session is still in
        # discovery / audit. Allow stop only if nothing else flags work
        # in progress. Treat as "no entries" so the caller can decide.
        queue_entries = []
    else:
        # The file is append-only; per orchestration.md, an update for an
        # existing scope writes a NEW line with the same `id` rather than
        # rewriting in place, and "latest wins". Dedupe by `id` here,
        # keeping the last occurrence, so a scope that went
        # queued -> complete doesn't leave its stale `queued` line still
        # counted as non-terminal work and block the hook forever.
        latest_by_id = {}
        for index, line in enumerate(queue_path.read_text().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Entries without an `id` can't be deduped; key them uniquely
            # by position so they're still counted individually.
            latest_by_id[entry.get("id", f"__no_id_{index}")] = entry
        queue_entries = list(latest_by_id.values())

    # references/state-schema.md defines `started_at` (top-level) and
    # `budgets.time_budget_seconds` (nested) in state.json — there is no
    # manifest.yaml anywhere in this skill. Reading the wrong file/keys
    # meant this was always empty, so the time-budget exit never fired.
    state_path = session_dir / "state.json"
    manifest = {}
    if state_path.is_file():
        try:
            session_state = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            session_state = {}
        manifest["start_time"] = session_state.get("started_at")
        manifest["time_budget_seconds"] = (session_state.get("budgets") or {}).get(
            "time_budget_seconds"
        )

    return session_dir, queue_entries, manifest


def time_budget_exhausted(manifest):
    """Return True if the session's time budget has expired."""
    start_time = manifest.get("start_time")
    budget_seconds = manifest.get("time_budget_seconds")
    if not start_time or not budget_seconds:
        return False
    try:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        return elapsed >= float(budget_seconds)
    except (ValueError, TypeError):
        return False


def count_by_status(queue_entries):
    counts = {"non_terminal": 0, "terminal": 0, "unknown": 0}
    breakdown = {}
    for entry in queue_entries:
        status = entry.get("status", "unknown")
        breakdown[status] = breakdown.get(status, 0) + 1
        if status in NON_TERMINAL_STATUSES:
            counts["non_terminal"] += 1
        elif status in TERMINAL_STATUSES:
            counts["terminal"] += 1
        else:
            counts["unknown"] += 1
    return counts, breakdown


def main():
    hook_input = read_hook_input()

    project_cwd = hook_input.get("cwd")
    if project_cwd and Path(project_cwd).is_dir():
        os.chdir(project_cwd)

    if should_skip(hook_input):
        emit_and_exit({})

    state = load_session_state()
    if state is None:
        # No active iteratotron session — allow normal stop.
        emit_and_exit({})

    session_dir, queue_entries, manifest = state

    if not queue_entries:
        # Phase 5 hasn't run yet, or the queue legitimately has zero entries.
        # Don't block — the orchestrator might be mid-discovery, or there
        # really is nothing to do. Phase 1/2/3 prose handles autonomy here.
        emit_and_exit({})

    counts, breakdown = count_by_status(queue_entries)

    if counts["non_terminal"] == 0:
        # Every queue entry reached a terminal status. The session is
        # legitimately done. Let Phase 8 finalise and stop.
        emit_and_exit({
            "decision": "approve",
            "reason": (
                f"iteratotron queue drained: "
                f"{counts['terminal']} scopes in terminal states "
                f"({', '.join(f'{k}={v}' for k, v in breakdown.items())}). "
                f"Phase 8 may finalise."
            ),
        })

    if time_budget_exhausted(manifest):
        # User-defined budget hit — let Phase 8 write the resumable queue
        # and stop. The remaining work moves to the next session.
        emit_and_exit({
            "decision": "approve",
            "reason": (
                f"Session time budget exhausted. "
                f"{counts['non_terminal']} non-terminal entries remain — "
                f"Phase 8 should write resumable_queue.jsonl now."
            ),
        })

    # Queue has dispatchable / in-flight work AND budget remains. BLOCK.
    breakdown_str = ", ".join(f"{k}={v}" for k, v in sorted(breakdown.items()))
    reason = (
        f"iteratotron Stop hook: {counts['non_terminal']} scope(s) still need "
        f"work in {session_dir}/scope_queue.jsonl ({breakdown_str}). "
        f"Don't stop. Per the Autonomy contract: dispatch the next "
        f"highest-priority dispatchable scope via the Agent tool, run Phase 7 "
        f"adversarial review on its result, reconcile, then re-check. "
        f"The session ends only when every entry reaches a terminal status "
        f"(complete / blocked / needs_human / skipped) OR the time budget in "
        f"state.json's budgets.time_budget_seconds expires."
    )

    emit_and_exit({"decision": "block", "reason": reason})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Never let an unexpected exception silently approve a stop —
        # better to no-op (default behaviour) and surface the error.
        sys.stderr.write(f"iteratotron check-completion hook error: {e}\n")
        print("{}")
        sys.exit(0)
