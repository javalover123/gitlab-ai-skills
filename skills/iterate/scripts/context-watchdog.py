#!/usr/bin/env python3
"""
PreToolUse watchdog — detects when context usage crosses the rotation
threshold and triggers automatic context rotation instead of waiting for
compaction.

Mechanism:
  1. Parse the transcript at $transcript_path, find the most recent
     assistant message's usage fields, and sum input + cache_read +
     cache_creation to get effective context size.
  2. If usage exceeds threshold (default 70% of window), write a handover
     marker to /tmp/claude-rotation-<user>-<pane>.md, detach rotator.sh
     (if present — see scripts/ in this skill) which will tmux send-keys
     `/clear` into the pane, and return a PreToolUse deny decision so the
     about-to-run tool does not execute. If rotator.sh isn't present, the
     handover is still written but the tool is allowed through instead of
     denied, since nothing would ever send `/clear` to unstick it.
  3. Otherwise exit silently with no output (allow the tool).

Configuration (via env vars):
  CLAUDE_CONTEXT_WINDOW       — total tokens in the model's window
                                 (default 1_000_000 for opus[1m])
  CLAUDE_ROTATION_THRESHOLD   — fraction 0..1 at which to rotate
                                 (default 0.70 → rotate at 70% used)
  CLAUDE_ROTATION_DISABLE     — set to "1" to disable rotation entirely

Hook input JSON (stdin):
  {
    "session_id": "...",
    "transcript_path": "/home/.../sessions/<id>.jsonl",
    "cwd": "...",
    "hook_event_name": "PreToolUse",
    "tool_name": "...",
    "tool_input": {...}
  }

Returns on stdout (only when blocking):
  {"hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": "<message to Claude>"
   }}

Silence + exit 0 otherwise.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

ROTATION_THRESHOLD = float(os.environ.get("CLAUDE_ROTATION_THRESHOLD", "0.70"))
DISABLED = os.environ.get("CLAUDE_ROTATION_DISABLE") == "1"

DEFAULT_WINDOW = 200_000
EXTENDED_WINDOW = 1_000_000

# Models whose default tier is already 1M tokens (no [1m] suffix needed).
NATIVELY_EXTENDED_MODELS = (
    "claude-sonnet-4-6",
    "claude-sonnet-4-7",
    "sonnet-4-6",
    "sonnet-4-7",
)

SCRIPT_DIR = Path(__file__).resolve().parent
ROTATOR = SCRIPT_DIR / "rotator.sh"


def project_state_dir() -> Path:
    """Project-local `.iterate/` directory for rotation/handover state.

    Falls back to `/tmp/claude-rotation-state/` when that directory isn't
    writable — the watchdog has to keep working even outside its primary
    use case.
    """
    project_root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    path = Path(project_root) / ".iterate"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = Path(tempfile.gettempdir()) / "claude-rotation-state"
        path.mkdir(parents=True, exist_ok=True)
    return path


def fail_silent(exc: BaseException) -> None:
    """Never block a tool call because our watchdog errored. Log + allow."""
    try:
        log_dir = project_state_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "watchdog-errors.log", "a") as f:
            f.write(f"{time.time()}: {type(exc).__name__}: {exc}\n")
    except Exception:
        pass
    sys.exit(0)


def read_hook_input() -> Dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def last_assistant(transcript_path: str) -> Optional[Dict[str, Any]]:
    """Return the most recent assistant `message` dict from the transcript."""
    path = Path(transcript_path)
    if not path.exists():
        return None

    last = None
    with open(path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "assistant":
                continue
            msg = obj.get("message")
            if isinstance(msg, dict):
                last = msg
    return last


def window_for_model_string(model: str) -> Optional[int]:
    """Map a model string to its context window size.

    Returns None if the model is unrecognized so callers can fall through
    to the next source of truth.
    """
    if not model:
        return None
    m = model.lower()
    if "[1m]" in m:
        return EXTENDED_WINDOW
    for tag in NATIVELY_EXTENDED_MODELS:
        if tag in m:
            return EXTENDED_WINDOW
    if "opus" in m or "haiku" in m:
        return DEFAULT_WINDOW
    if "sonnet" in m:
        # Older sonnets are 200K; newer are 1M. Without a version, assume
        # the more conservative default so we don't rotate too late.
        return DEFAULT_WINDOW
    return None


def read_settings_model(path: Path) -> str:
    try:
        with open(path, "r") as f:
            data = json.load(f)
        m = data.get("model")
        return m if isinstance(m, str) else ""
    except Exception:
        return ""


def detect_context_window(last_msg: Optional[Dict[str, Any]], cwd: str) -> int:
    """Work out the model's context window from the most reliable signal.

    Priority:
      1. CLAUDE_CONTEXT_WINDOW env override (explicit number)
      2. CLAUDE_MODEL env var
      3. Project-local .claude/settings.json
      4. Global ~/.claude/settings.json
      5. Transcript's last assistant `model` field
      6. DEFAULT_WINDOW
    """
    raw = os.environ.get("CLAUDE_CONTEXT_WINDOW", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass

    for candidate in (
        os.environ.get("CLAUDE_MODEL", ""),
        read_settings_model(Path(cwd) / ".claude" / "settings.json") if cwd else "",
        read_settings_model(Path.home() / ".claude" / "settings.json"),
        (last_msg or {}).get("model") or "",
    ):
        win = window_for_model_string(candidate)
        if win is not None:
            return win

    return DEFAULT_WINDOW


def effective_context(usage: Dict[str, Any]) -> int:
    """Sum the fields that count toward live context size."""
    def get_int(key: str) -> int:
        v = usage.get(key, 0)
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    return (
        get_int("input_tokens")
        + get_int("cache_read_input_tokens")
        + get_int("cache_creation_input_tokens")
    )


def sanitize_pane(pane: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in pane)


def handover_path(pane: str) -> Path:
    user = os.environ.get("USER", "user")
    handover_dir = project_state_dir() / "handover"
    handover_dir.mkdir(parents=True, exist_ok=True)
    return handover_dir / f"rotation-{user}-{sanitize_pane(pane)}.md"


def write_handover(pane: str, used: int, window: int, session_id: str) -> Path:
    path = handover_path(pane)
    body = (
        f"# Context Rotation Handover\n\n"
        f"- Timestamp (unix): {int(time.time())}\n"
        f"- Tmux pane: {pane}\n"
        f"- Previous session_id: {session_id}\n"
        f"- Tokens used at rotation: {used} / {window} "
        f"({used / window:.1%})\n\n"
        f"## Instruction for next session\n\n"
        f"Context was cleared to prevent compaction. This is NOT a stop "
        f"signal — the /iterate loop is still active and the user has "
        f"pre-authorized it. Your rules for the resumed session:\n\n"
        f"1. Run `/iterate` immediately to re-derive the current gap list "
        f"against MEMORY.md, specs, ADRs, and the threat model. Do not "
        f"ask the user to re-invoke.\n"
        f"2. DO NOT run baseline verification. The project state at "
        f"rotation time is the current state — trust it. The Verification "
        f"Budget rule forbids `cargo check --workspace`, `cargo test "
        f"--workspace`, and any re-verify-everything pass when nothing has "
        f"been edited yet.\n"
        f"3. DO NOT write a 'picking up where we left off' summary. The "
        f"iteration log is the handover record. Your first Edit/Write "
        f"tool call should land within the first three tool calls of the "
        f"resumed session.\n"
        f"4. DO NOT number iterations. No 'iteration N+1'. Describe what "
        f"changed instead.\n"
        f"5. DO treat any 'deferred', 'Partial', 'placeholder', 'awaits', "
        f"or 'follow-up' annotation as the definition of the next task.\n"
        f"6. DO NOT ask the user via AskUserQuestion whether to continue. "
        f"The loop is still active; check-in is disabled.\n"
    )
    path.write_text(body)
    return path


def spawn_rotator(pane: str, handover: Path) -> bool:
    """Detach rotator.sh so it survives this hook exiting.

    Passes the project root as the third arg so the rotator's own
    diagnostic log lands in `<project>/.iterate/logs/rotator.log`
    instead of `/tmp/`.

    Returns whether the rotator was actually spawned. The caller must not
    deny tool calls on a rotation it never started — nothing else ever
    sends `/clear`, so a denial with no rotator running would stall the
    session with every tool call denied forever.
    """
    if not ROTATOR.exists():
        return False
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd() or ""
    try:
        subprocess.Popen(
            ["bash", str(ROTATOR), pane, str(handover), project_dir],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        return True
    except Exception as exc:
        fail_silent(exc)
        return False


def deny(reason: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


def main() -> None:
    if DISABLED:
        sys.exit(0)

    pane = os.environ.get("TMUX_PANE", "")
    if not pane:
        # Not in tmux; we have no mechanism to inject /clear.
        sys.exit(0)

    try:
        hook_input = read_hook_input()
    except Exception as exc:
        fail_silent(exc)
        return

    transcript_path = hook_input.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    try:
        last_msg = last_assistant(transcript_path)
    except Exception as exc:
        fail_silent(exc)
        return

    if not last_msg or not isinstance(last_msg.get("usage"), dict):
        sys.exit(0)

    usage = last_msg["usage"]
    cwd = hook_input.get("cwd", "")
    window = detect_context_window(last_msg, cwd)
    used = effective_context(usage)
    fraction = used / window if window > 0 else 0.0

    if fraction < ROTATION_THRESHOLD:
        sys.exit(0)

    # If a handover was written very recently for this pane, rotation is
    # already in flight — don't pile up another one.
    handover = handover_path(pane)
    if handover.exists():
        age = time.time() - handover.stat().st_mtime
        if age < 60:
            # Still allow the tool; rotator is already working.
            sys.exit(0)

    session_id = hook_input.get("session_id", "")
    try:
        path = write_handover(pane, used, window, session_id)
        rotator_spawned = spawn_rotator(pane, path)
    except Exception as exc:
        fail_silent(exc)
        return

    if not rotator_spawned:
        # rotator.sh isn't present (or failed to launch): nothing will
        # ever send /clear, so denying here would stall the session with
        # every tool call denied forever. Allow the tool through instead;
        # the agent keeps running against the now-tight context budget
        # rather than getting stuck.
        return

    deny(
        f"Context rotation triggered: {used:,} / {window:,} tokens used "
        f"({fraction:.0%}). This is NOT a stop signal for the /iterate "
        f"loop — rotation preserves loop state by writing a handover file "
        f"and re-invoking the skill in a clean session.\n\n"
        f"Handover written to {path}. A fresh session will start "
        f"momentarily via /clear; it will auto-resume via /iterate and "
        f"pick up the next gap. Stop issuing tool calls now — the rotator "
        f"is taking over.\n\n"
        f"Do NOT summarize the session for the user. Do NOT write a "
        f"'ran out of context' message. Do NOT mark the loop as done. The "
        f"handover file is the only record needed; the next session will "
        f"read it and continue."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        fail_silent(exc)
