#!/usr/bin/env python3
"""
Stop hook for the bug-burndown skill.

Blocks Claude from ending the turn while the session's bug queue still has
dispatchable or in-flight work AND the session time budget hasn't been hit.
The queue is the deterministic completion oracle — Phases 3-5 populate it
from log / test / issue / drift collection, and the orchestrator's job is
to drain it.

Reads `.bug-burndown/CURRENT` to find the active session, then inspects
`.bug-burndown/<session-id>/queue.jsonl` and `manifest.yaml`. If any bug
is in a non-terminal status (queued / in_flight / re-evaluate /
needs_rebase / introduced_regression), and the time budget hasn't expired,
the hook returns `decision: block` telling Claude to keep dispatching.

Skipped when:
- Subagent context (parent_task_id present) — the bugfix subagent runs
  its own DoD hook, not the orchestrator's.
- `stop_hook_active` is true (infinite-loop guard).
- No `.bug-burndown/CURRENT` exists.
- Session time budget exhausted (approve with note).
- Session is harness-driven (manifest.origin contains "harness")
  AND we're NOT the harness-spawned subprocess (BUG_BURNDOWN_HARNESS_DRIVEN
  env var unset). This is the contract that lets an interactive Claude
  session see a leftover harness session without getting blocked. The
  harness that owns the autonomy contract sets BUG_BURNDOWN_HARNESS_DRIVEN=1
  on the claude --print it spawns to drive its session; inside THAT
  subprocess this hook fires normally.

Exit protocol:
- `{"decision": "block", "reason": "..."}` → keep going
- `{"decision": "approve", "reason": "..."}` → allow stop
- `{}` → no-op
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

TERMINAL_STATUSES = {
    "fixed",
    "blocked",
    "needs_human",
    "skipped",
    "requires_human_review",
    "introduced_regression",
}
NON_TERMINAL_STATUSES = {
    "queued",
    "in_flight",
    "re-evaluate",
    "needs_rebase",
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
    if hook_input.get("stop_hook_active"):
        return True
    if (
        hook_input.get("parent_task_id")
        or hook_input.get("agent_type")
        or hook_input.get("is_subagent")
    ):
        return True
    return False


def load_session_state():
    current_file = Path(".bug-burndown/CURRENT")
    if not current_file.is_file():
        return None

    session_id = current_file.read_text().strip()
    if not session_id:
        return None

    session_dir = Path(f".bug-burndown/{session_id}")
    if not session_dir.is_dir():
        return None

    queue_path = session_dir / "queue.jsonl"
    queue_entries = []
    if queue_path.is_file():
        for line in queue_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                queue_entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    manifest_path = session_dir / "manifest.yaml"
    manifest = {}
    if manifest_path.is_file():
        for line in manifest_path.read_text().splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            manifest[key.strip()] = value.strip().strip('"').strip("'")

    return session_dir, queue_entries, manifest


def is_harness_driven_session(manifest):
    """Manifest written by an external harness (a verification harness or
    similar) carries `origin: a verification harness` or another `*-harness`
    value. Interactive /bug-burndown invocations don't set origin."""
    origin = manifest.get("origin", "").lower()
    return "harness" in origin


def is_active_burndown_subprocess():
    """True if we're running inside the Claude session that was
    explicitly spawned to drive THIS burndown. The harness sets
    BUG_BURNDOWN_HARNESS_DRIVEN=1 on the env of its `claude --print
    "/bug-burndown resume:..."` invocation, so child processes (this
    hook included) see it. Interactive Claude Code sessions don't."""
    return os.environ.get("BUG_BURNDOWN_HARNESS_DRIVEN") == "1"


def time_budget_exhausted(manifest):
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
        emit_and_exit({})

    session_dir, queue_entries, manifest = state

    # Harness-driven session contract: a session whose manifest declares
    # an external harness origin is only autonomously-enforced from
    # inside the harness-spawned subprocess. Other Claude sessions
    # (typically an interactive Claude Code instance that happens to
    # see the harness's session pointer) should be allowed to stop —
    # the harness is the owner, not them.
    if is_harness_driven_session(manifest) and not is_active_burndown_subprocess():
        sys.stderr.write(
            f"bug-burndown: skipping autonomy enforcement — session "
            f"{session_dir} is harness-driven "
            f"(manifest.origin={manifest.get('origin', 'unset')}) but "
            f"BUG_BURNDOWN_HARNESS_DRIVEN is unset, so this Claude session "
            f"isn't the spawned burndown subprocess.\n"
        )
        emit_and_exit({})

    if not queue_entries:
        # Phases 3-5 haven't produced a queue yet, or the queue is
        # legitimately empty. Don't block — the orchestrator might be
        # mid-collection.
        emit_and_exit({})

    counts, breakdown = count_by_status(queue_entries)

    if counts["non_terminal"] == 0:
        emit_and_exit({
            "decision": "approve",
            "reason": (
                f"bug-burndown queue drained: {counts['terminal']} bugs in "
                f"terminal states ({', '.join(f'{k}={v}' for k, v in breakdown.items())}). "
                f"Phase 8 may finalise."
            ),
        })

    if time_budget_exhausted(manifest):
        emit_and_exit({
            "decision": "approve",
            "reason": (
                f"Session time budget exhausted. "
                f"{counts['non_terminal']} non-terminal entries remain — "
                f"Phase 8 should write resumable_queue.jsonl now."
            ),
        })

    breakdown_str = ", ".join(f"{k}={v}" for k, v in sorted(breakdown.items()))
    reason = (
        f"bug-burndown Stop hook: {counts['non_terminal']} bug(s) still need "
        f"work in {session_dir}/queue.jsonl ({breakdown_str}). Don't stop. "
        f"Per the Autonomy contract: dispatch the next highest-priority "
        f"dispatchable bug via the Agent tool, reconcile its result, then "
        f"re-check. The session ends only when every entry reaches a "
        f"terminal status (fixed / blocked / needs_human / skipped) OR the "
        f"time budget in manifest.yaml expires."
    )

    emit_and_exit({"decision": "block", "reason": reason})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"bug-burndown check-completion hook error: {e}\n")
        print("{}")
        sys.exit(0)
