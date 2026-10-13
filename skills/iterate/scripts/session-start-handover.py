#!/usr/bin/env python3
"""
SessionStart handover reader.

Runs on every session start (fresh, resume, or /clear). Injects extra
context in two independent cases:

1. **Rotation handover.** If a context-rotation handover file exists in
   /tmp for the current tmux pane and is fresh, inject it as the primary
   resume directive. Then rename the handover so subsequent
   SessionStarts don't re-trigger.

2. **In-flight iterate loop.** If the project has an iteration log whose
   last entry does NOT end with "COMPLETE" (the sentinel the skill
   writes when all stopping criteria pass), inject a resume directive
   that bans baseline verification and tells Claude to pick up the next
   gap in-turn.

Either, both, or neither can fire. Exits silently with no output when
there's nothing to inject — the common case for regular session starts
on completed projects.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

MAX_AGE_SECONDS = 300

ITERATION_LOG_CANDIDATES = [
    # Preferred — project-local .iterate/ dir, allowlistable without
    # touching .claude/ which often requires per-write prompts.
    ".iterate/iteration-log.md",
    ".iterate/iterate-log.md",
    # Legacy locations — kept so existing repos keep working.
    ".claude/iteration-log.md",
    ".claude/iterate-log.md",
    "docs/ITERATION-LOG.md",
    "ITERATION-LOG.md",
]

DEFERRAL_SENTINEL_PATTERNS = [
    r"\bdeferred\b",
    r"\bpartial\b",
    r"\bplaceholder\b",
    r"\bawaiting\b",
    r"\bpending\b",
    r"\bnot\s+yet\s+wired\b",
    r"\bfollow-?up\b",
    r"\bgaps?\s+remain\b",
    r"\bcontinuing\b",
]


# -------------------------------------------------------------------
# Rotation handover (pre-existing behaviour)
# -------------------------------------------------------------------

def sanitize_pane(pane: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in pane)


def project_state_dir() -> Path:
    """Project-local `.iterate/` directory for rotation/handover state.

    Falls back to `/tmp/claude-rotation-state/` when that directory isn't
    writable.
    """
    project_root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    path = Path(project_root) / ".iterate"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        import tempfile
        path = Path(tempfile.gettempdir()) / "claude-rotation-state"
        path.mkdir(parents=True, exist_ok=True)
    return path


def handover_path(pane: str) -> Path:
    """Resolve the rotation handover marker path.

    Prefers `<project>/.iterate/handover/rotation-<user>-<pane>.md`. The
    legacy `/tmp/claude-rotation-<user>-<pane>.md` is checked as a
    fallback so handovers written by an older watchdog still get picked
    up when the new code reads them.
    """
    user = os.environ.get("USER", "user")
    sanitized = sanitize_pane(pane)
    new_path = project_state_dir() / "handover" / f"rotation-{user}-{sanitized}.md"
    new_path.parent.mkdir(parents=True, exist_ok=True)
    if new_path.exists():
        return new_path
    legacy = Path("/tmp") / f"claude-rotation-{user}-{sanitized}.md"
    if legacy.exists():
        return legacy
    return new_path


def read_rotation_handover() -> Optional[str]:
    """Return the rotation handover body if present and fresh."""
    pane = os.environ.get("TMUX_PANE", "")
    if not pane:
        return None

    path = handover_path(pane)
    if not path.exists():
        return None

    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return None

    if age > MAX_AGE_SECONDS:
        try:
            path.unlink()
        except OSError:
            pass
        return None

    try:
        body = path.read_text()
    except OSError:
        return None

    try:
        path.rename(path.with_suffix(".md.consumed"))
    except OSError:
        pass

    return body


# -------------------------------------------------------------------
# In-flight iterate loop detection
# -------------------------------------------------------------------

def find_iteration_log() -> Optional[Path]:
    """Look for an iteration log in the current project directory."""
    cwd = Path(os.getcwd())
    for candidate in ITERATION_LOG_CANDIDATES:
        path = cwd / candidate
        if path.is_file():
            return path
    return None


def inspect_iteration_log(path: Path) -> Optional[Tuple[str, bool]]:
    """
    Return (last_line_summary, loop_in_flight) or None if unreadable.

    loop_in_flight is True when the last non-empty line does NOT end with
    a "COMPLETE" sentinel and/or DOES contain deferral keywords.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (IOError, UnicodeDecodeError):
        return None

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None

    last = lines[-1]
    summary = last[:280]

    # Completion sentinel: literal "COMPLETE" at end-of-line (case-insensitive).
    # Allow trailing markdown formatting like `.**` so bold-wrapped sentinels
    # such as `**LOOP COMPLETE.**` are recognised as complete.
    is_complete = bool(re.search(r"\bcomplete[.!?*\s]*$", last, re.IGNORECASE))
    has_deferral = any(
        re.search(p, last, re.IGNORECASE) for p in DEFERRAL_SENTINEL_PATTERNS
    )

    loop_in_flight = (not is_complete) or has_deferral
    return summary, loop_in_flight


def build_iterate_resume_message(log_path: Path, summary: str) -> str:
    """Compose the SessionStart resume directive."""
    return (
        "An /iterate loop appears to be in flight in this project. The last "
        f"entry in `{log_path}` does not mark the loop as COMPLETE:\n\n"
        f"    {summary}\n\n"
        "Resume the loop as follows — and do NOT treat this as a new turn "
        "starting that needs a preamble:\n\n"
        "  1. DO NOT run baseline verification. The project state at the end "
        "     of the previous session is the current state — trust it. Do "
        "     not run `cargo check --workspace`, `cargo test --workspace`, "
        "     or any re-verify-everything pass. The skill's Verification "
        "     Budget rule forbids it.\n"
        "  2. DO NOT write a 'picking up where we left off' summary. The "
        "     iteration log already records the handover. Issue your first "
        "     Edit/Write tool call within the first three tool calls of "
        "     this session.\n"
        "  3. DO NOT number iterations. No 'iteration N+1' ordinals, no "
        "     'Iter N:' log-line prefixes. Describe what changed instead.\n"
        "  4. DO treat any 'deferred', 'Partial', 'placeholder', 'awaits', "
        "     or 'follow-up' annotation in the last log line as the "
        "     definition of the next task. Scan docs/stories/, docs/specs/, "
        "     and docs/threat-models/ for those keywords and pick the "
        "     highest-priority one.\n"
        "  5. DO NOT ask the user whether to continue. The user pre-"
        "     authorized the loop when they invoked /iterate; check-in is "
        "     disabled until every Step 6 stopping criterion passes.\n\n"
        "If your first three tool calls are read-only (Bash/Read/Grep), "
        "you are over-verifying — pivot directly to a code change."
    )


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------

def main() -> None:
    messages: list[str] = []

    rotation_body = read_rotation_handover()
    if rotation_body:
        messages.append(
            "Context was just cleared via automatic rotation (previous "
            "session crossed the token threshold). You **MUST** now run "
            "`/iterate` to continue iteration — do not summarize, do not "
            "ask the user, do not wait. A fresh gap-analysis pass against "
            "MEMORY.md, specs, ADRs, and the threat model will re-derive "
            "everything you need.\n\nHandover record:\n\n" + rotation_body
        )

    log_path = find_iteration_log()
    if log_path is not None:
        result = inspect_iteration_log(log_path)
        if result is not None:
            summary, in_flight = result
            if in_flight:
                messages.append(build_iterate_resume_message(log_path, summary))

    if not messages:
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n\n---\n\n".join(messages),
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
