#!/usr/bin/env python3
"""
Completion checker for the iterate skill's stop hook.

Determines if iteration should continue by validating all quality gates.
When gaps remain, returns exit code 1 with the gap list for Claude to address.

Uses JSON input/output per Claude Code hooks specification:
https://code.claude.com/docs/en/hooks#json-output

Configuration:
  Create .iterate.json in project root to customize scope and timeouts:
  {
    "include_paths": ["src/", "docs/"],
    "exclude_paths": ["legacy/", "old-c-code/"],
    "include_extensions": [".rs", ".md", ".toml"],
    "exclude_extensions": [".c", ".h"],
    "timeouts": {
      "default": 120,
      "cargo_audit": 120,
      "cargo_test": 300,
      "go_test": 180,
      "nix_flake_check": 300
    },
    "skip_in_background": true
  }

  Legacy nested format also supported for backward compatibility:
  {
    "include": {"paths": [...], "extensions": [...]},
    "exclude": {"paths": [...], "extensions": [...]}
  }
"""

import json
import os
import sys
import subprocess
import time
import tempfile
import re
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set


# ============================================================================
# Configuration Loading
# ============================================================================

class IterateConfig:
    """Handles scope filtering for the iterate skill based on .iterate.json config."""

    def __init__(self):
        self.include_paths: Set[str] = set()
        self.include_extensions: Set[str] = set()
        self.exclude_paths: Set[str] = set()
        self.exclude_extensions: Set[str] = set()
        self.timeouts: Dict[str, int] = {
            "default": 120,
            "cargo_audit": 120,
            "cargo_test": 300,
            "go_test": 180,
            "nix_flake_check": 300,
        }
        self.skip_in_background: bool = True
        self.custom_output_filters: List[str] = []  # Regex patterns to filter from output
        # Subprocess env overrides (e.g. CARGO_BUILD_JOBS to cap rustc parallelism on
        # large workspaces). Merged into os.environ for every run_command invocation.
        self.env: Dict[str, str] = {}
        # When cargo_scope == "per-crate", swap --workspace for -p <crate> on
        # expensive cargo invocations (test, clippy, coverage). cargo_crates lists
        # the crate names to pass; empty list falls back to workspace.
        self.cargo_scope: Optional[str] = None
        self.cargo_crates: List[str] = []
        # `.iterate.json` may override the 80% Step 6 coverage gate for
        # projects whose realistic line-coverage ceiling is bounded by
        # wire-adapter / FFI / entry-point code that can't be unit-tested
        # without integration infrastructure. None → use the 80% default.
        self.coverage_threshold: Optional[float] = None
        self._load_config()

    def _load_config(self):
        """Load configuration from .iterate.json when present in project root."""
        # Use current working directory (project root), not script location
        config_file = Path(os.getcwd()) / ".iterate.json"
        if not config_file.exists():
            return

        try:
            with open(config_file, "r") as f:
                config = json.load(f)

            # Support flat schema (preferred)
            if "include_paths" in config:
                self.include_paths = set(config["include_paths"])
            if "include_extensions" in config:
                self.include_extensions = set(config["include_extensions"])
            if "exclude_paths" in config:
                self.exclude_paths = set(config["exclude_paths"])
            if "exclude_extensions" in config:
                self.exclude_extensions = set(config["exclude_extensions"])

            # Load timeout configuration
            if "timeouts" in config and isinstance(config["timeouts"], dict):
                self.timeouts.update(config["timeouts"])

            # Load background skip setting
            if "skip_in_background" in config:
                self.skip_in_background = bool(config["skip_in_background"])

            # Load custom output filters (regex patterns)
            if "custom_output_filters" in config and isinstance(config["custom_output_filters"], list):
                self.custom_output_filters = config["custom_output_filters"]

            # Subprocess env overrides
            if "env" in config and isinstance(config["env"], dict):
                self.env = {str(k): str(v) for k, v in config["env"].items()}

            # Cargo scope override: per-crate runs avoid OOM on large workspaces
            if "cargo" in config and isinstance(config["cargo"], dict):
                cargo_cfg = config["cargo"]
                scope = cargo_cfg.get("scope")
                if scope in ("workspace", "per-crate"):
                    self.cargo_scope = scope
                crate = cargo_cfg.get("crate")
                if isinstance(crate, str):
                    self.cargo_crates = [crate]
                elif isinstance(crate, list):
                    self.cargo_crates = [str(c) for c in crate]
                if self.cargo_scope == "per-crate" and not self.cargo_crates:
                    sys.stderr.write(
                        "Warning: .iterate.json sets cargo.scope=per-crate but no "
                        "cargo.crate listed — falling back to workspace\n"
                    )
                    self.cargo_scope = None

            # Coverage threshold override (top-level key).
            if "coverage_threshold" in config:
                raw = config["coverage_threshold"]
                if isinstance(raw, (int, float)) and 0.0 <= float(raw) <= 100.0:
                    self.coverage_threshold = float(raw)
                else:
                    sys.stderr.write(
                        "Warning: .iterate.json coverage_threshold must be a number in [0, 100]; "
                        "ignoring\n"
                    )

            # Support legacy nested schema for backward compatibility
            if "include" in config:
                if "paths" in config["include"]:
                    self.include_paths = set(config["include"]["paths"])
                if "extensions" in config["include"]:
                    self.include_extensions = set(config["include"]["extensions"])

            if "exclude" in config:
                if "paths" in config["exclude"]:
                    self.exclude_paths = set(config["exclude"]["paths"])
                if "extensions" in config["exclude"]:
                    self.exclude_extensions = set(config["exclude"]["extensions"])

        except (json.JSONDecodeError, IOError) as e:
            # Don't fail the hook if config is malformed, just log it
            sys.stderr.write(f"Warning: Failed to load .iterate.json: {e}\n")

    @staticmethod
    def _path_matches(path_str: str, pattern: str) -> bool:
        """
        Match `pattern` against `path_str` as a full path segment, not a
        bare substring. A substring check (e.g. "/vendor" in path_str)
        would also match "vendor-extra/", "thirdvendor/", etc. — any
        directory name that merely starts or ends with the pattern.
        """
        pattern = pattern.rstrip("/")
        return (
            path_str == pattern
            or path_str.startswith(pattern + "/")
            or path_str.endswith(f"/{pattern}")
            or f"/{pattern}/" in path_str
        )

    def should_check_path(self, path: str) -> bool:
        """
        Check if a path passes include/exclude filters.

        Args:
            path: File or directory path to check

        Returns:
            True if the path should be checked, False if it should be skipped
        """
        path_obj = Path(path)

        # Check extension filters
        if path_obj.is_file() or "." in str(path_obj):
            ext = path_obj.suffix
            if ext:
                # If exclude extensions specified and this matches, skip
                if self.exclude_extensions and ext in self.exclude_extensions:
                    return False
                # If include extensions specified and this doesn't match, skip
                if self.include_extensions and ext not in self.include_extensions:
                    return False

        # Check path filters
        path_str = str(path_obj)

        # If exclude paths specified and this matches any, skip
        if self.exclude_paths:
            for exclude in self.exclude_paths:
                if self._path_matches(path_str, exclude):
                    return False

        # If include paths specified and this doesn't match any, skip
        if self.include_paths:
            matches_include = False
            for include in self.include_paths:
                if self._path_matches(path_str, include):
                    matches_include = True
                    break
            if not matches_include:
                return False

        return True

    def get_grep_exclude_args(self) -> List[str]:
        """
        Build grep exclusion arguments from the config filters.

        Returns:
            List of grep --exclude-dir and --exclude arguments
        """
        args = []

        # Add exclude paths as --exclude-dir
        for exclude_path in self.exclude_paths:
            # Strip trailing slash and add as exclude-dir
            dir_name = exclude_path.rstrip("/")
            args.extend(["--exclude-dir", dir_name])

        # Add exclude extensions as --exclude patterns
        for ext in self.exclude_extensions:
            # Convert .ext to *.ext pattern
            pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            args.extend(["--exclude", pattern])

        # If include extensions specified, add --include for each
        if self.include_extensions:
            for ext in self.include_extensions:
                pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
                args.extend(["--include", pattern])

        return args


# ============================================================================
# Nix Detection and Command Wrapping
# ============================================================================

def detect_nix_environment() -> Tuple[bool, Optional[str]]:
    """
    Check if the project uses Nix and pick the right shell command.

    Checks include_paths from .iterate.json first, then falls back to cwd.

    Returns:
        (uses_nix, shell_command) where shell_command is 'nix develop' or 'nix-shell'
    """
    # Check include_paths first (for monorepo setups where flake.nix is in a subdir)
    nix_root = find_language_root("flake.nix")
    if nix_root:
        return True, f"nix develop {nix_root}#"

    nix_root = find_language_root("shell.nix")
    if nix_root:
        return True, f"nix-shell {nix_root}/shell.nix"

    # Fall back to cwd-level detection
    if Path("flake.nix").exists():
        return True, "nix develop"
    elif Path("shell.nix").exists():
        return True, "nix-shell"
    return False, None


def wrap_command_for_nix(cmd: List[str], nix_shell_cmd: Optional[str]) -> List[str]:
    """
    Wrap a command in a Nix shell invocation when needed.

    Args:
        cmd: Command to run
        nix_shell_cmd: 'nix develop' or 'nix-shell' or None

    Returns:
        Wrapped command list ready to execute
    """
    if not nix_shell_cmd:
        return cmd

    # Join command into shell string
    cmd_str = " ".join(cmd)

    if nix_shell_cmd.startswith("nix develop"):
        # Handle both "nix develop" and "nix develop /path/to/flake#"
        parts = nix_shell_cmd.split()
        return parts + ["-c", "sh", "-c", cmd_str]
    elif nix_shell_cmd.startswith("nix-shell"):
        parts = nix_shell_cmd.split()
        return parts + ["--run", cmd_str]
    else:
        return cmd


# ============================================================================
# Hook Context and Utilities
# ============================================================================

def read_hook_input() -> Dict[str, Any]:
    """Read and parse JSON input from stdin that Claude sends to hooks."""
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return {}
        return json.loads(input_data)
    except json.JSONDecodeError:
        return {}


def is_background_context(hook_input: Dict[str, Any]) -> bool:
    """
    Detect if we're running in a background task or sub-agent context.

    Returns True if we should skip expensive checks to avoid resource contention.
    """
    # Check for background tasks
    if hook_input.get("background_tasks"):
        return True

    # Check if we're in a sub-agent or task context
    # These typically have task_id or agent_id in the context
    if hook_input.get("task_id") or hook_input.get("agent_id"):
        return True

    # Check for tool execution context that indicates we're not in main session
    tool_context = hook_input.get("tool_context", {})
    if tool_context.get("is_background") or tool_context.get("parent_task_id"):
        return True

    return False


def send_output(output: Dict[str, Any]) -> None:
    """Send JSON output back to Claude and exit."""
    print(json.dumps(output), file=sys.stdout)
    sys.exit(0)


def tmux_send_iterate_fallback() -> None:
    """Belt-and-braces fallback: queue `/iterate` into the tmux pane.

    The decision=block JSON we emit on the same hook call should keep
    Claude iterating without returning to the prompt. If that mechanism
    fails for any reason (bug, model mis-behavior, manual interrupt),
    this types `/iterate` into the pane so whenever Claude does reach a
    user prompt, iteration resumes.

    C-u clears any pending text first so repeated Stop hooks don't stack
    duplicate /iterate strings.

    Opt-in only (ITERATE_ENABLE_SEND_KEYS=1): typing into the user's pane
    is an undocumented side effect of a Stop hook, and the typed text can
    land mid-turn and stack up or interrupt what the user is typing.
    """
    if os.environ.get("ITERATE_ENABLE_SEND_KEYS") != "1":
        return
    pane = os.environ.get("TMUX_PANE", "")
    if not pane:
        return
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "C-u"],
            check=False, timeout=2,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "-l", "/iterate"],
            check=False, timeout=2,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "Enter"],
            check=False, timeout=2,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def hook_state_dir(skill_name: str) -> Path:
    """Resolve the project-local directory for skill hook state.

    Prefers `<project>/.iterate/hooks/<skill_name>/` so log writes don't
    touch `.claude/` (which triggers per-write permission prompts and
    breaks the iterate loop). Falls back to `/tmp/claude-code-hooks/`
    only when that directory isn't writable (read-only checkout,
    container with project mounted ro, …) — the hook still records
    something rather than silently dropping data.
    """
    project_root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    path = Path(project_root) / ".iterate" / "hooks" / skill_name
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Last-ditch fallback if the project-local dir isn't writable
        # (read-only checkout, container with project mounted ro, …).
        path = Path(tempfile.gettempdir()) / "claude-code-hooks" / skill_name
        path.mkdir(parents=True, exist_ok=True)
    return path


def log_hook(skill_name: str, hook_input: Dict[str, Any], output: Dict[str, Any], gaps: List[str]) -> None:
    """Log hook invocations for debugging and auditing.

    Writes to `<project>/.iterate/hooks/<skill>/hook-<ts>.json`. See
    [`hook_state_dir`] for the location-resolution rules.
    """
    log_dir = hook_state_dir(skill_name)

    now = datetime.now()
    timestamp = now.isoformat()
    log_file = log_dir / f"hook-{now.strftime('%Y%m%d-%H%M%S')}.json"

    log_entry = {
        "timestamp": timestamp,
        "skill": skill_name,
        "input": hook_input,
        "output": output,
        "gaps_found": gaps,
    }

    try:
        with open(log_file, "w") as f:
            json.dump(log_entry, f, indent=2)
    except OSError:
        pass  # Don't fail the hook if logging fails


def should_skip(hook_input: Dict[str, Any]) -> bool:
    """Check if we should skip iteration (subagent or background task).

    Deliberately does NOT skip on `stop_hook_active` (set by Claude Code on
    the stop that follows a block): since every subsequent stop attempt
    while gaps remain also carries this flag, skipping on it approves the
    very next stop unconditionally, ending the loop after exactly one
    block regardless of how many gaps are left — the opposite of this
    skill's "block until every gate passes" design.
    """
    # Check if this is a subagent
    if hook_input.get("parent_task_id") or hook_input.get("agent_type") or hook_input.get("is_subagent", False):
        return True

    # Check if this is a background task
    if hook_input.get("run_in_background") or hook_input.get("is_background", False):
        return True

    return False


def get_task_tracking_file(skill_name: str) -> Path:
    """Get path to task tracking file.

    Project-local under `.iterate/hooks/<skill>/background-tasks.json`
    via [`hook_state_dir`].
    """
    return hook_state_dir(skill_name) / "background-tasks.json"


def track_background_tasks(skill_name: str, task_ids: List[str]) -> Dict[str, float]:
    """
    Track when background tasks were first seen.

    Returns:
        Dict mapping task_id to timestamp of first observation
    """
    tracking_file = get_task_tracking_file(skill_name)

    # Load existing tracking data
    tracked_tasks = {}
    if tracking_file.exists():
        try:
            with open(tracking_file, "r") as f:
                tracked_tasks = json.load(f)
        except Exception:
            pass

    # Add new tasks
    now = time.time()
    updated = False
    for task_id in task_ids:
        if task_id not in tracked_tasks:
            tracked_tasks[task_id] = now
            updated = True

    # Save if updated
    if updated:
        try:
            with open(tracking_file, "w") as f:
                json.dump(tracked_tasks, f)
        except Exception:
            pass

    return tracked_tasks


def check_background_tasks(skill_name: str, task_ids: List[str]) -> Tuple[List[str], List[str], bool]:
    """
    Check background task status and runtime.

    Returns:
        (tasks_to_kill, still_running_tasks, should_wait)
        - tasks_to_kill: tasks running > 30 minutes
        - still_running_tasks: tasks still running < 30 minutes
        - should_wait: True if we should wait 60s and check again
    """
    if not task_ids:
        return [], [], False

    # Track tasks
    tracked_tasks = track_background_tasks(skill_name, task_ids)

    now = time.time()
    timeout_seconds = 30 * 60  # 30 minutes

    tasks_to_kill = []
    still_running = []

    for task_id in task_ids:
        if task_id in tracked_tasks:
            runtime = now - tracked_tasks[task_id]
            if runtime >= timeout_seconds:
                tasks_to_kill.append(task_id)
            else:
                still_running.append(task_id)
        else:
            # New task, add to still_running
            still_running.append(task_id)

    # Should wait if there are tasks still running (and none to kill, or both)
    should_wait = len(still_running) > 0

    return tasks_to_kill, still_running, should_wait


def cleanup_task_tracking(skill_name: str, task_ids: List[str]) -> None:
    """Remove completed tasks from tracking file."""
    if not task_ids:
        # No tasks - clean up the tracking file entirely
        tracking_file = get_task_tracking_file(skill_name)
        if tracking_file.exists():
            try:
                tracking_file.unlink()
            except Exception:
                pass
        return

    tracking_file = get_task_tracking_file(skill_name)
    if not tracking_file.exists():
        return

    try:
        with open(tracking_file, "r") as f:
            tracked_tasks = json.load(f)

        # Keep only tasks that are still in task_ids
        updated_tasks = {k: v for k, v in tracked_tasks.items() if k in task_ids}

        if updated_tasks:
            with open(tracking_file, "w") as f:
                json.dump(updated_tasks, f)
        else:
            tracking_file.unlink()
    except Exception:
        pass


# ============================================================================
# Forbidden-phrase and verification-only-turn detection (behavioural override)
# ============================================================================
#
# These scans catch premature-stop patterns by inspecting the most recent
# assistant turn on the transcript:
#
# 1. FORBIDDEN_STOP_PHRASES — summary-shaped prose that indicates a stop
#    triggered by turn-taking bias rather than a real done-state.
# 2. Verification-only turns — the model made only Bash/Read/Grep calls with
#    no Edit/Write, meaning it verified state but made no progress. Iterate
#    closes gaps via code changes, not verification.
# 3. "Deferred" rationalizations — phrases like "deferred until X lands" or
#    "out of scope for this iteration" mask stopping as scope control.
#
# Matches produce BLOCK with concrete next-action guidance pointing at the
# remaining Partial/Draft/deferred items the other gap scans surfaced.

FORBIDDEN_STOP_PHRASES = [
    # Summary-shaped prose
    r"\biteration\s+(?:done|complete|finished)\b",
    r"\bmoved\s+the\s+needle\b",
    r"\blogical\s+(?:stopping\s+point|checkpoint)\b",
    r"\bremaining\s+debt\b",
    r"\bwhat\s+changed:\s*$",
    r"\bwhat\s+was\s+verified:\s*$",
    r"\bfinal\s+summary:\s*$",
    # Numbered iteration ordinals
    r"\biteration\s+\d+\s+(?:summary|complete|done|finished)\b",
    r"\b(?:after|past)\s+\d+\s+iterations?\b",
    # "Go re-invoke" — the classic "I stopped when I shouldn't have" tell
    r"\bre-?invoke\s+/?iterate\b",
    r"\bready\s+for\s+(?:the\s+)?next\s+invocation\b",
    # Explicit stop rationale
    r"\bI'?ll\s+pause\s+here\b",
    r"\bstopping\s+here\s+(?:to|for|so)\b",
    r"\bhand(?:ing)?\s+(?:control\s+)?back\s+to\s+(?:the\s+)?user\b",
]

FORBIDDEN_DEFERRAL_PHRASES = [
    # Deferred-as-acceptable stopping rationales
    r"\bdeferred\s+(?:until|since|because)\b",
    r"\bout\s+of\s+scope\s+for\s+this\s+iteration\b",
    r"\bcan'?t\s+be\s+delivered\s+without\b",
    r"\bwaits?\s+on\s+the\s+(?:upstream|payload|graph|contract)\b",
    r"\bblocked\s+on\s+(?:the\s+)?(?:absent|missing|upstream|unwritten)\b",
    r"\bwill\s+land\s+(?:once|when|with|after)\s+",
    r"\bfollow-?up\s+(?:tracked|deferred|pending)\b",
    r"\bnot\s+yet\s+wired\b",
    r"\bawaits?\s+(?:the\s+)?(?:RPC|contract|payload|implementation)\b",
]


def read_last_assistant_turn(hook_input: Dict[str, Any]) -> str:
    """Return the most recent assistant message's text content.

    Stop hooks get the transcript path in hook_input. The transcript is
    JSONL — one message per line. We walk it backwards to find the last
    assistant message and concatenate its text content blocks.

    Returns empty string if the transcript is unreadable or the last turn
    has no text (e.g. a pure tool-call turn).
    """
    transcript_path = hook_input.get("transcript_path")
    if not transcript_path:
        return ""
    path = Path(transcript_path)
    if not path.exists():
        return ""
    try:
        # Cap at last 2 MB so the scan is always fast even on long sessions.
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            offset = max(0, size - 2 * 1024 * 1024)
            f.seek(offset)
            chunk = f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""

    # JSONL; walk backwards, find last assistant message
    lines = [ln for ln in chunk.splitlines() if ln.strip().startswith("{")]
    for line in reversed(lines):
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Transcript format varies across Claude Code versions; accept both
        # top-level {"type":"assistant","message":{...}} and flatter shapes.
        if msg.get("type") == "assistant" or msg.get("role") == "assistant":
            inner = msg.get("message", msg)
            content = inner.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                return "\n".join(parts)
    return ""


def scan_forbidden_stop_phrases(text: str) -> List[Tuple[str, str]]:
    """Return (phrase, context) tuples for every forbidden-stop match."""
    matches: List[Tuple[str, str]] = []
    if not text:
        return matches
    for pattern in FORBIDDEN_STOP_PHRASES + FORBIDDEN_DEFERRAL_PHRASES:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            # One-line context around the match
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            ctx = text[start:end].replace("\n", " ").strip()
            matches.append((m.group(0), ctx))
    return matches


def count_recent_assistant_tool_calls(hook_input: Dict[str, Any]) -> Dict[str, int]:
    """Count tool calls in the most recent assistant turn by tool name.

    Returns a dict like {"Bash": 4, "Read": 2, "Edit": 0, "Write": 1}.
    Used to detect verification-only turns (all Bash/Read, no Edit/Write).
    """
    counts: Dict[str, int] = {}
    transcript_path = hook_input.get("transcript_path")
    if not transcript_path:
        return counts
    path = Path(transcript_path)
    if not path.exists():
        return counts
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            offset = max(0, size - 4 * 1024 * 1024)
            f.seek(offset)
            chunk = f.read().decode("utf-8", errors="replace")
    except OSError:
        return counts

    lines = [ln for ln in chunk.splitlines() if ln.strip().startswith("{")]
    # Find the last assistant turn (one or more consecutive assistant lines
    # after the most recent user line).
    last_user_idx = -1
    for i, line in enumerate(lines):
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("type") == "user" or msg.get("role") == "user":
            last_user_idx = i

    for line in lines[last_user_idx + 1 :] if last_user_idx >= 0 else lines:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("type") != "assistant" and msg.get("role") != "assistant":
            continue
        inner = msg.get("message", msg)
        content = inner.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "unknown")
                    counts[name] = counts.get(name, 0) + 1
    return counts


def is_verification_only_turn(tool_counts: Dict[str, int]) -> bool:
    """True if the last assistant turn had tool calls but none were code edits.

    Verification-only means: one or more Bash/Read/Grep/Glob calls, zero
    Edit/Write/NotebookEdit calls. That's the "I verified the state and now
    I'm stopping" failure mode.
    """
    if not tool_counts:
        return False
    edit_tools = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
    has_edits = any(tool_counts.get(t, 0) > 0 for t in edit_tools)
    if has_edits:
        return False
    verify_tools = {"Bash", "Read", "Grep", "Glob"}
    has_verify = any(tool_counts.get(t, 0) > 0 for t in verify_tools)
    return has_verify


def compute_must_block(gaps: List[str], forbidden_matches: list, verification_only: bool) -> Tuple[bool, bool]:
    """Decide whether the Stop hook must block, and why.

    Returns (must_block, verification_only_with_gaps). A verification-only
    turn (tests/lint/build with no Edit/Write/MultiEdit) is only a
    stopping-bias tell while gaps remain to work on instead; with zero
    gaps it's the legitimate final validation checkpoint the skill's
    "Verification Budget" guidance recommends, not a reason to force a
    pointless edit just to get past this hook.
    """
    verification_only_with_gaps = verification_only and bool(gaps)
    must_block = bool(gaps) or bool(forbidden_matches) or verification_only_with_gaps
    return must_block, verification_only_with_gaps


# ============================================================================
# Language Detection and Gap Checking
# ============================================================================
# SCOPE: Complete project health - documentation AND implementation
#
# This hook checks EVERYTHING:
# - Documentation artifacts exist and are current (spec, ADRs, threat model)
# - Implementation is complete (no untracked TODOs, no placeholders, no stubs)
# - Tests pass and coverage meets minimum threshold (80%)
# - No security vulnerabilities or hardcoded secrets
# - Code quality passes all linters and formatters
# - Frontend/backend/API/database components are wired up and complete
#
# Rationale: The iterate skill brings projects to production-ready completeness.
# Unlike documentation-focused skills (all-aboard, spec-review, adr-review,
# threat-model-review), iterate ensures the implementation matches the docs.
# ============================================================================

def detect_languages(config: Optional["IterateConfig"] = None) -> Set[str]:
    """Auto-detect project languages, returning all that are found.

    When .iterate.json specifies include_paths, searches those directories
    (minus exclude_paths) for language markers first. Falls back to the
    project root. Returns a set of all detected languages so multi-language
    projects (e.g., Rust backend in a JS monorepo) are handled correctly.
    """
    languages: Set[str] = set()

    # Build the list of directories to search for language markers.
    # Priority: include_paths (filtered by exclude_paths) first, then root.
    search_dirs: List[Path] = []
    if config and config.include_paths:
        for p in config.include_paths:
            path = Path(p)
            # Skip if this path is excluded
            if config and any(path.is_relative_to(Path(ex)) or str(path).startswith(ex)
                              for ex in config.exclude_paths):
                continue
            if path.exists() and path.is_dir():
                search_dirs.append(path)

    # Always include root as fallback, but search include_paths first
    search_dirs.append(Path("."))

    for d in search_dirs:
        if (d / "Cargo.toml").exists():
            languages.add("rust")
        if (d / "go.mod").exists():
            languages.add("go")
        if (d / "pyproject.toml").exists() or (d / "setup.py").exists():
            languages.add("python")
        if (d / "package.json").exists():
            # Only count JS if this dir is in include_paths or is root with
            # no include_paths configured (avoids false positive from host repo)
            if not (config and config.include_paths) or d != Path("."):
                languages.add("javascript")
        if (d / "flake.nix").exists() or (d / "default.nix").exists():
            languages.add("nix")
        if (d / "Makefile").exists():
            try:
                with open(d / "Makefile", "r") as f:
                    content = f.read()
                    # Use regex to match .c/.h as file extensions (not substrings like .cargo)
                    if re.search(r'\b\w+\.(c|h)\b', content):
                        languages.add("c")
            except Exception:
                pass

    return languages if languages else {"unknown"}


# ============================================================================
# Comprehensive Completeness Checks
# ============================================================================

def find_project_root() -> Path:
    """Find the project root by walking up to the git root, falling back to CWD.

    When Claude Code's CWD is a subdirectory (e.g. pkgs/tools/sbom-enrich),
    documentation artifacts live at the repository root, not the CWD.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            git_root = Path(result.stdout.strip())
            if git_root.is_dir():
                return git_root
    except Exception:
        pass
    return Path.cwd()


def check_documentation_artifacts() -> List[str]:
    """Check for required documentation artifacts (spec, ADR, threat model).

    Looks in the git root rather than CWD so that projects whose Claude Code
    session is scoped to a subdirectory (e.g. pkgs/tools/sbom-enrich) still
    find docs/ at the repository root.
    """
    gaps = []

    project_root = find_project_root()
    docs_dir = project_root / "docs"
    if not docs_dir.exists():
        gaps.append("P0: No docs/ directory — run /all-aboard to bootstrap documentation")
        return gaps

    # Check for specs
    specs_dir = docs_dir / "specs"
    if not specs_dir.exists() or not list(specs_dir.glob("*.md")):
        gaps.append("P0: No implementation specifications in docs/specs/ — run /spec-create")

    # Check for ADRs
    adr_dir = docs_dir / "adr"
    if not adr_dir.exists() or not list(adr_dir.glob("*.md")):
        gaps.append("P0: No Architecture Decision Records in docs/adr/ — run /adr-create")

    # Check for threat models
    tm_dir = docs_dir / "threat-models"
    if not tm_dir.exists() or not list(tm_dir.glob("*.md")):
        gaps.append("P0: No threat models in docs/threat-models/ — run /threat-model-create")

    return gaps


def check_implementation_completeness(nix_cmd: Optional[str], config: IterateConfig) -> List[str]:
    """Check for incomplete implementations, TODOs, dead code, and placeholders."""
    gaps = []

    # Expanded tracking pattern - accepts GAP-XXX, TODO-XXX, ADR-XXX, FR-XXX, etc.
    tracking_pattern = re.compile(
        r"("
        r"#\d+|"  # GitHub issue numbers
        r"issue|ticket|bug|tracking|"  # Generic tracking
        r"GAP-\d+|"  # Gap analysis references
        r"TODO-\d+|"  # Work item numbers
        r"ADR-\d+|"  # Architecture decisions
        r"FR-\d+|NFR-\d+|IR-\d+|"  # Spec requirement IDs
        r"TM-[A-Z]+-\d+|"  # Threat model IDs
        r"WORK-\d+"  # Work tracking items
        r")",
        re.IGNORECASE
    )

    # Check for TODO/FIXME without tracking issues
    patterns = [
        ("TODO", "TODO comments without tracking issue references"),
        ("FIXME", "FIXME comments without tracking issue references"),
        ("XXX", "XXX comments indicating incomplete work"),
        ("HACK", "HACK comments indicating technical debt"),
        ("PLACEHOLDER", "PLACEHOLDER implementations"),
        ("stub", "Stub implementations"),
        ("unimplemented!", "Unimplemented panic macros (Rust)"),
        ("todo!", "Todo panic macros (Rust)"),
        ("NotImplementedError", "NotImplementedError placeholders (Python)"),
        ("raise NotImplementedError", "NotImplementedError raises (Python)"),
    ]

    for pattern, description in patterns:
        # Search across common source directories, excluding tests
        for src_dir in ["src", "lib", "pkg", "internal", "app", "api", "frontend", "backend"]:
            if not Path(src_dir).exists():
                continue

            # Skip directory if config excludes it
            if not config.should_check_path(src_dir):
                continue

            # Build grep command with config-based exclusions
            # Case-sensitive match, so case variations must be added above
            grep_cmd = ["grep", "-r", "-n", pattern, "--exclude-dir=tests", "--exclude-dir=test"]
            grep_cmd.extend(config.get_grep_exclude_args())
            grep_cmd.append(src_dir)

            success, output = run_command(grep_cmd, nix_cmd)
            if success and output.strip():
                # Filter out tracking issue references
                lines = output.strip().split("\n")
                untracked = [
                    line for line in lines
                    if not tracking_pattern.search(line)
                ]
                if untracked:
                    first_file = untracked[0].split(':')[0] if untracked else ""
                    gaps.append(
                        f"P1: {description} in {src_dir}/: {len(untracked)} instances\n"
                        f"    Fix: Add tracking reference like TODO(#123), TODO(GAP-002), or TODO(ADR-0001)\n"
                        f"    Note: This functionality needs to be implemented even if it has a tracking issue!\n"
                        f"    Having a tracking number is to ensure documentation, the TODO is not complete until\n"
                        f"    it has actually been implemented and the linked tracking issue updated with the\n"
                        f"    implementation status and details\n"
                        f"    Note: You must use one of the supported issue identifier types below!\n"
                        f"    Note: Issues should be linked to ADRs, spec entries or threat model entries.\n"
                        f"    Supported: #N, issue X, GAP-N, TODO-N, ADR-N, FR-N, TM-X-N\n"
                        f"    First untracked: {first_file}"
                    )

    return gaps


def check_test_coverage(language: Set[str], nix_cmd: Optional[str], config: Optional["IterateConfig"] = None) -> List[str]:
    """
    Check test coverage meets 80% minimum threshold.

    Relies on exit codes for pass/fail. Only parses output to extract percentage.
    """
    gaps = []
    # Default threshold per Step 6's "Test coverage ≥ 80%" gate.
    # `.iterate.json` may override via `"coverage_threshold": <float>`
    # for projects whose realistic coverage ceiling is lower because
    # of wire-adapter / FFI / process-entrypoint code that can't be
    # unit-tested without integration infrastructure.
    coverage_threshold = 80.0
    if config and config.coverage_threshold is not None:
        coverage_threshold = config.coverage_threshold

    if "rust" in language:
        rust_root = find_language_root("Cargo.toml")

        # Use nix develop if flake.nix exists in rust project root
        rust_nix_cmd = nix_cmd
        if rust_root and (Path(rust_root) / "flake.nix").exists():
            rust_nix_cmd = "nix develop .#"

        # Per-crate scope override (see check_rust_gaps for rationale)
        cov_scope: List[str] = []
        if config and config.cargo_scope == "per-crate" and config.cargo_crates:
            for crate_name in config.cargo_crates:
                cov_scope.extend(["-p", crate_name])

        # Check tool availability first (short timeout - just version check)
        has_tarpaulin, _ = run_command(
            ["cargo-tarpaulin", "--version"],
            rust_nix_cmd,
            timeout=10,
            cwd=rust_root,
            config=config,
        )
        has_llvm_cov, _ = run_command(
            ["cargo", "llvm-cov", "--version"],
            rust_nix_cmd,
            timeout=10,
            cwd=rust_root,
            config=config,
        )

        if not has_tarpaulin and not has_llvm_cov:
            # Can't measure coverage without tools - check if tests exist as proxy
            test_check, test_output = run_command(
                ["cargo", "test", "--no-run", "--quiet", *cov_scope],
                rust_nix_cmd,
                timeout=120,
                cwd=rust_root,
                config=config,
            )
            if test_check:
                # Tests exist but can't measure - downgrade severity
                gaps.append(
                    "P3: Test coverage measurement unavailable "
                    "(install cargo-tarpaulin or cargo-llvm-cov)"
                )
            else:
                # No tests at all - that's a real problem
                gaps.append("P1: No tests found")
            return gaps

        # Tools available - measure coverage
        coverage = None
        success = False
        output = ""

        # Coverage timeout can be configured via .iterate.json ("cargo_tarpaulin" or "cargo_test")
        coverage_timeout = 600
        if config and config.timeouts:
            coverage_timeout = config.timeouts.get("cargo_tarpaulin",
                             config.timeouts.get("cargo_test", 600))

        # Try cargo-tarpaulin first (if available)
        if has_tarpaulin:
            success, output = run_command(
                ["cargo", "tarpaulin", "--skip-clean", *cov_scope, "--out", "Stdout"],
                rust_nix_cmd,
                timeout=coverage_timeout,
                cwd=rust_root,
                config=config,
            )
            if success:
                coverage = extract_coverage_percentage(output)

        # Try cargo-llvm-cov as fallback
        if coverage is None and has_llvm_cov:
            success, output = run_command(
                ["cargo", "llvm-cov", *cov_scope, "--summary-only"],
                rust_nix_cmd,
                timeout=coverage_timeout,
                cwd=rust_root,
                config=config,
            )
            if success:
                coverage = extract_coverage_percentage(output)

        # Evaluate results
        if coverage is not None:
            if coverage < coverage_threshold:
                gaps.append(
                    f"P1: Test coverage {coverage:.1f}% < {coverage_threshold}% minimum"
                )
        elif "llvm-tools-preview" in output.lower():
            gaps.append(
                "P3: cargo-llvm-cov requires llvm-tools-preview "
                "(rustup component add llvm-tools-preview)"
            )
        else:
            gaps.append("P2: Coverage measurement failed - verify tools work manually")

    if "go" in language:
        success, output = run_command(["go", "test", "-cover", "./..."], nix_cmd)
        if success:
            # Parse coverage from output (multiple packages)
            matches = re.findall(r"coverage:\s+(\d+\.?\d*)%", output)
            if matches:
                coverage = sum(float(m) for m in matches) / len(matches)
                if coverage < coverage_threshold:
                    gaps.append(
                        f"P1: Test coverage {coverage:.1f}% < {coverage_threshold}% minimum"
                    )
        else:
            gaps.append("P1: Go tests failing — fix tests before checking coverage")

    if "python" in language:
        success, output = run_command(
            ["pytest", "--cov", "--cov-report=term"],
            nix_cmd
        )
        if success:
            match = re.search(r"TOTAL.*?(\d+)%", output)
            if match:
                coverage = float(match.group(1))
                if coverage < coverage_threshold:
                    gaps.append(
                        f"P1: Test coverage {coverage:.1f}% < {coverage_threshold}% minimum"
                    )
        else:
            gaps.append("P1: Python tests failing or pytest-cov not installed")

    if "javascript" in language:
        success, output = run_command(["npm", "run", "test:coverage"], nix_cmd)
        if not success:
            success, output = run_command(["npm", "test", "--", "--coverage"], nix_cmd)

        if success:
            match = re.search(r"All files.*?(\d+\.?\d*)", output)
            if match:
                coverage = float(match.group(1))
                if coverage < coverage_threshold:
                    gaps.append(
                        f"P1: Test coverage {coverage:.1f}% < {coverage_threshold}% minimum"
                    )

    return gaps


def check_frontend_backend_completeness(nix_cmd: Optional[str], config: IterateConfig) -> List[str]:
    """Check that all project components (frontend, backend, API, DB) are implemented."""
    gaps = []

    # Detect project structure - only check directories that pass config filters
    frontend_dirs = ["frontend", "ui", "web", "client"]
    has_frontend = any([
        Path(d).exists() and config.should_check_path(d) for d in frontend_dirs
    ]) or (Path("public").exists() and Path("src/components").exists() and
           config.should_check_path("public") and config.should_check_path("src/components"))

    backend_dirs = ["backend", "server", "api", "src/api", "cmd"]
    has_backend = any([
        Path(d).exists() and config.should_check_path(d) for d in backend_dirs
    ])

    db_dirs = ["migrations", "db", "database"]
    has_database = any([
        Path(d).exists() and config.should_check_path(d) for d in db_dirs
    ]) or (Path("schema.sql").exists() and config.should_check_path("schema.sql")) or \
        any(config.should_check_path(str(f)) for f in list(Path(".").glob("*.db")) + list(Path(".").glob("*.sqlite")))

    # Check if frontend exists but is incomplete
    if has_frontend:
        frontend_dirs = [d for d in ["frontend", "ui", "web", "client", "src/components"]
                        if Path(d).exists() and config.should_check_path(d)]
        for dir_name in frontend_dirs:
            # Build grep command with config exclusions
            grep_cmd = ["grep", "-r", "-i", "placeholder\\|TODO\\|coming soon\\|under construction"]
            grep_cmd.extend(config.get_grep_exclude_args())
            grep_cmd.append(dir_name)

            success, output = run_command(grep_cmd, nix_cmd)
            if success and output.strip():
                gaps.append(f"P1: Frontend has placeholder/incomplete components in {dir_name}/")

            # Check if components have tests
            test_patterns = ["*.test.js", "*.test.jsx", "*.test.ts", "*.test.tsx", "*.spec.js"]
            has_tests = any(list(Path(dir_name).rglob(pattern)) for pattern in test_patterns)
            if not has_tests:
                gaps.append(f"P1: Frontend components in {dir_name}/ have no tests")

    # Check if backend exists but is incomplete
    if has_backend:
        backend_dirs = [d for d in ["backend", "server", "api", "src/api", "cmd"]
                       if Path(d).exists() and config.should_check_path(d)]
        for dir_name in backend_dirs:
            # Build grep command with config exclusions
            grep_cmd = ["grep", "-r", "-i", "NotImplemented\\|TODO\\|unimplemented\\|stub"]
            grep_cmd.extend(config.get_grep_exclude_args())
            grep_cmd.append(dir_name)

            success, output = run_command(grep_cmd, nix_cmd)
            if success and output.strip():
                gaps.append(f"P1: Backend has incomplete API handlers/routes in {dir_name}/")

    # Check if database exists but migrations are incomplete
    if has_database:
        migration_dirs = [d for d in ["migrations", "db/migrations", "database/migrations"]
                         if Path(d).exists() and config.should_check_path(d)]
        for dir_name in migration_dirs:
            # Check if migrations have down/rollback counterparts
            up_files = list(Path(dir_name).glob("*up.sql"))
            down_files = list(Path(dir_name).glob("*down.sql"))
            if len(up_files) > len(down_files):
                gaps.append(f"P1: Database migrations in {dir_name}/ missing rollback (down) migrations")

    # Cross-component completeness
    if has_frontend and has_backend:
        # Check if API client is wired up
        frontend_check_dirs = ["frontend", "ui", "web", "client"]
        if any(Path(d).exists() and config.should_check_path(d) for d in frontend_check_dirs):
            api_integration = False
            for dir_name in frontend_check_dirs:
                if not Path(dir_name).exists() or not config.should_check_path(dir_name):
                    continue

                grep_cmd = ["grep", "-r", "-E", "fetch|axios|http|api"]
                grep_cmd.extend(config.get_grep_exclude_args())
                grep_cmd.append(dir_name)

                success, output = run_command(grep_cmd, nix_cmd)
                if success and output.strip():
                    api_integration = True
                    break

            if not api_integration:
                gaps.append("P1: Frontend exists but no API integration detected (no fetch/axios/http calls)")

    return gaps


def check_security_comprehensive(language: Set[str], nix_cmd: Optional[str], config: IterateConfig) -> List[str]:
    """Run comprehensive security scans beyond basic dependency audits."""
    gaps = []

    # Common exclusions for all security scans (build artifacts, dependencies, tests)
    exclude_dirs = ["target", "node_modules", "vendor", ".git", "dist", "build", "tests", "test", "benches", "examples"]
    exclude_args = []
    for exclude in exclude_dirs:
        exclude_args.extend(["--exclude-dir", exclude])

    # Add config-based exclusions
    exclude_args.extend(config.get_grep_exclude_args())

    # Language-specific static analysis for security
    if "rust" in language:
        # Check for unsafe blocks - use regex to match actual unsafe blocks, not comments/attributes
        cmd = ["grep", "-r", "-E", r"unsafe\s*\{", "--include=*.rs"] + exclude_args + ["src/"]
        success, output = run_command(cmd, nix_cmd)
        if success and output.strip():
            # Filter out comments and compiler directives
            lines = []
            for line in output.strip().split("\n"):
                # Skip lines that are comments (// or /*) or attributes (#[allow(unsafe_code)])
                content = line.split(':', 2)[-1].strip() if ':' in line else line
                if not (content.startswith('//') or content.startswith('/*') or content.startswith('#[')):
                    lines.append(line)
            if lines:
                gaps.append(f"P0: {len(lines)} unsafe blocks found — review with /rust-unsafe-ffi-review")

        # Check for common security anti-patterns. -F (fixed-string) avoids
        # the parens being parsed as BRE group syntax, which made every one
        # of these grep calls fail with "Unmatched ( or \(" and silently
        # skip the check (run_command treats a non-zero exit as failure).
        patterns = [
            ("unwrap(", "unwrap() calls that can panic"),
            ("expect(", "expect() calls that can panic"),
            ("panic!(", "panic calls terminate the program and indicate a lack of graceful error handling"),
            (".clone(", "excessive cloning (potential DoS)"),
        ]
        for pattern, description in patterns:
            cmd = ["grep", "-r", "-F", pattern, "--include=*.rs"] + exclude_args + ["src/"]
            success, output = run_command(cmd, nix_cmd)
            if success and output.strip():
                lines = output.strip().split("\n")
                if len(lines) > 20:  # Threshold for "excessive"
                    gaps.append(f"P2: Excessive {description}: {len(lines)} instances")

    if "c" in language:
        # Run comprehensive C security analysis
        success, _ = run_command(["cppcheck", "--enable=warning,style,performance,portability", "--suppress=*:*test*", "."], nix_cmd)
        if not success:
            gaps.append("P0: cppcheck security analysis failed or found issues")

        # Check for banned functions
        banned_functions = ["strcpy", "strcat", "sprintf", "gets", "scanf"]
        for func in banned_functions:
            # -F (fixed-string) suffix to catch functions, not just these
            # bare words, without the trailing "(" being parsed as BRE
            # group syntax (which made this fail with "Unmatched ( or \(").
            # -w no longer applies with -F, so match the call form directly.
            cmd = ["grep", "-r", "-F", "{}(".format(func), "--include=*.c"] + exclude_args + ["."]
            success, output = run_command(cmd, nix_cmd)
            if success and output.strip():
                gaps.append(f"P0: Banned function {func}() found — use safe alternatives")

    if "python" in language:
        # Run bandit security scan (already excludes tests by default)
        success, output = run_command(["bandit", "-r", ".", "-ll"], nix_cmd)
        if not success:
            gaps.append("P0: Bandit security scan found high/medium severity issues")

    return gaps


def run_command(cmd: List[str], nix_shell_cmd: Optional[str] = None, check: bool = False, timeout: Optional[int] = None, config: Optional[IterateConfig] = None, cwd: Optional[str] = None) -> Tuple[bool, str]:
    """
    Run a command and return (success, output), wrapped in Nix shell if needed.

    SUCCESS IS DETERMINED BY EXIT CODE ONLY. Output is for context/extraction only.

    This is critical for Nix environments where stderr may contain warnings/banners
    that don't indicate command failure. Trust the return code first, parse output
    only when extracting specific data (coverage %, error details).

    `timeout=None` (the default) means the caller has no specific requirement;
    in that case `config.timeouts["default"]` is used if set, else 120s.
    Callers that care about a per-command timeout should resolve it
    themselves from `config.timeouts` (keyed by compound names like
    "cargo_test" — `cmd[0]` alone, e.g. "cargo", never matches those) and
    pass the result as `timeout=`. An explicitly passed `timeout` is never
    overridden here, including when it happens to equal 120.

    Debug mode: Set ITERATE_DEBUG=1 environment variable to log raw output.
    """
    if timeout is None:
        # No specific timeout requested: fall back to the configured
        # project-wide default, else 120s.
        timeout = (config.timeouts.get("default", 120) if config and config.timeouts else 120)

    debug_mode = os.getenv("ITERATE_DEBUG") == "1"

    try:
        final_cmd = wrap_command_for_nix(cmd, nix_shell_cmd)

        if debug_mode:
            sys.stderr.write(f"\n[DEBUG] Command: {' '.join(final_cmd)}\n")
            sys.stderr.write(f"[DEBUG] Timeout: {timeout}s\n")

        proc_env = None
        if config and config.env:
            proc_env = os.environ.copy()
            proc_env.update(config.env)

        result = subprocess.run(
            final_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=proc_env,
        )

        # Combine and filter output FIRST before making decisions
        raw_output = result.stdout + result.stderr

        if debug_mode:
            sys.stderr.write(f"[DEBUG] Exit code: {result.returncode}\n")
            sys.stderr.write(f"[DEBUG] Raw stdout:\n{result.stdout}\n")
            sys.stderr.write(f"[DEBUG] Raw stderr:\n{result.stderr}\n")

        # Get custom filters from config if available
        custom_filters = config.custom_output_filters if config else []
        filtered_output = filter_nix_banner(raw_output, custom_filters) if nix_shell_cmd else raw_output

        if debug_mode:
            sys.stderr.write(f"[DEBUG] Filtered output:\n{filtered_output}\n")

        # CRITICAL: Trust the exit code, not the output content
        # Return code 0 = success, non-zero = failure
        # Output is for extracting data (coverage %) or error context only
        success = result.returncode == 0

        return success, filtered_output
    except subprocess.TimeoutExpired:
        if debug_mode:
            sys.stderr.write(f"[DEBUG] Command timed out after {timeout}s\n")
        return False, f"Command timed out after {timeout}s"
    except Exception as e:
        if debug_mode:
            sys.stderr.write(f"[DEBUG] Command failed with exception: {e}\n")
        return False, str(e)


def filter_nix_banner(output: str, custom_filters: Optional[List[str]] = None) -> str:
    """
    Strip Nix environment noise from command output.

    Filters out:
    - Nix store operations
    - ShellHook output (NIX: prefix)
    - Git warnings about dirty working tree
    - Custom user-defined patterns (from .iterate.json)
    - Other Nix-specific messages that don't indicate command failure

    Args:
        output: Raw command output
        custom_filters: Optional list of regex patterns to filter

    Returns:
        Filtered output with noise removed
    """
    lines = output.split('\n')
    filtered = []

    # Compile custom filter regexes once
    custom_patterns = []
    if custom_filters:
        for pattern in custom_filters:
            try:
                custom_patterns.append(re.compile(pattern))
            except re.error:
                # Skip invalid regex patterns
                pass

    for line in lines:
        stripped = line.strip()

        # Nix store operations
        if line.startswith("copying path '/nix/store/") and "from" in line:
            continue
        if line.startswith("warning: ") and "/nix/store/" in line:
            continue

        # ShellHook output (prefixed or not - catch both formats)
        if line.startswith("NIX:") or stripped.startswith("NIX:"):
            continue

        # Git warnings about dirty working tree
        # These appear in Nix environments and don't indicate command failure
        if line.startswith("warning: Git tree ") and "uncommitted changes" in line:
            continue
        if "warning: Git tree " in line and " has uncommitted changes" in line:
            continue

        # Custom user-defined filters
        if custom_patterns:
            skip_line = False
            for pattern in custom_patterns:
                if pattern.search(line):
                    skip_line = True
                    break
            if skip_line:
                continue

        # Keep everything else, including legitimate tool output
        filtered.append(line)

    return '\n'.join(filtered)


def extract_coverage_percentage(output: str) -> Optional[float]:
    """
    Extract coverage percentage from tool output.

    Returns None if no percentage found. Used for extracting data from output
    where the exit code indicates success/failure, but we need the actual value.

    Preference order: anchored matches first (tarpaulin's `Coverage Results:`
    line, llvm-cov's `TOTAL` row), then fall back to the last bare percentage
    in the output. Falling back to the LAST bare percentage rather than the
    first matters because tarpaulin's banner can contain unrelated `%`
    figures (e.g. compile progress) before the final coverage value.
    """
    # Tarpaulin: `Coverage Results:\n32.62% coverage, 1653/5068 lines covered`
    tarpaulin = re.search(r"Coverage Results:[^\n]*\n\s*(\d+\.?\d*)%", output)
    if tarpaulin:
        return float(tarpaulin.group(1))
    # Tarpaulin alternative single-line form: `XX.YY% coverage, A/B lines covered`
    tarpaulin_inline = re.search(r"(\d+\.?\d*)%\s+coverage,\s+\d+/\d+\s+lines", output)
    if tarpaulin_inline:
        return float(tarpaulin_inline.group(1))
    # llvm-cov summary: `TOTAL  <regions> <missed_regions> <region%>  <fns> <missed_fns> <fn%>  <lines> <missed_lines> <line%>  ...`
    # We want the LINE coverage percentage (last % on the TOTAL row before any branch columns).
    # Use findall to get all percentages on the TOTAL line, then take the one after the
    # 6th column (index 2 among the 3 main coverage groups: regions, functions, lines).
    total_line_match = re.search(r"^TOTAL[^\n]+", output, re.MULTILINE)
    if total_line_match:
        total_line = total_line_match.group(0)
        pcts = re.findall(r"(\d+\.?\d*)%", total_line)
        if pcts:
            # llvm-cov emits: region%, function%, line%, [branch%]
            # Line coverage is the 3rd percentage (index 2). Fall back to last if fewer.
            idx = min(2, len(pcts) - 1)
            return float(pcts[idx])
    # Bare-percentage fallback — pick the LAST one so unrelated leading
    # percentages (compile-progress banners, etc.) don't shadow the
    # final result.
    all_pcts = re.findall(r"(\d+\.?\d*)%", output)
    return float(all_pcts[-1]) if all_pcts else None


def format_error_preview(output: str, max_lines: int = 4) -> str:
    """
    Extract first N lines of error output for gap message previews.

    Args:
        output: Command output to preview
        max_lines: Maximum number of lines to include (default 4)

    Returns:
        Formatted preview string with each line indented
    """
    if not output or not output.strip():
        return ""

    lines = output.strip().split('\n')
    preview_lines = lines[:max_lines]

    # Add "..." if output was truncated
    if len(lines) > max_lines:
        preview_lines.append("...")

    # Indent each line for better readability in gap messages
    indented = '\n    '.join(preview_lines)
    return f"\n    {indented}"


def find_language_root(marker: str) -> Optional[str]:
    """Find the project root for a language by searching include_paths for a marker file.

    When .iterate.json specifies include_paths, checks those directories for
    the marker (e.g., 'Cargo.toml' for Rust). Falls back to cwd if found there.
    Returns the absolute path to the directory containing the marker, or None.
    """
    config_file = Path(os.getcwd()) / ".iterate.json"
    include_paths: List[str] = []
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                cfg = json.load(f)
            include_paths = cfg.get("include_paths", [])
        except Exception:
            pass

    # Check include_paths first
    for p in include_paths:
        candidate = Path(p)
        if (candidate / marker).exists():
            return str(candidate.resolve())

    # Fall back to cwd
    if (Path(".") / marker).exists():
        return str(Path(".").resolve())

    return None


def check_rust_gaps(nix_cmd: Optional[str], config: Optional["IterateConfig"] = None) -> List[str]:
    """
    Check for gaps in Rust projects.

    Trusts exit codes for pass/fail. Parses output only for extracting data.
    Includes error previews for P0/P1 gaps.
    """
    gaps = []

    # Find Rust project root (may be in a subdirectory per .iterate.json)
    rust_root = find_language_root("Cargo.toml")
    if not rust_root:
        gaps.append("P1: Cargo.toml not found in include_paths or project root")
        return gaps

    # If the Rust project has its own flake.nix, use nix develop from there
    # so cargo gets the C compiler and other build deps.
    # Use ".#" since cwd is already set to rust_root.
    rust_nix_cmd = nix_cmd
    if (Path(rust_root) / "flake.nix").exists():
        rust_nix_cmd = "nix develop .#"

    # Use configurable timeouts if available, otherwise fall back to sensible defaults
    t_audit = 300
    t_test = 600
    t_clippy = 300
    t_fmt = 60
    if config and config.timeouts:
        t_audit = config.timeouts.get("cargo_audit", t_audit)
        t_test = config.timeouts.get("cargo_test", t_test)
        t_clippy = config.timeouts.get("cargo_clippy", t_clippy)
        t_fmt = config.timeouts.get("cargo_fmt", t_fmt)

    # Resolve cargo scope: when .iterate.json sets cargo.scope=per-crate, swap
    # --workspace for explicit -p <crate> flags to avoid OOM on large workspaces.
    per_crate_args: List[str] = []
    if config and config.cargo_scope == "per-crate" and config.cargo_crates:
        for crate_name in config.cargo_crates:
            per_crate_args.extend(["-p", crate_name])
    test_scope = per_crate_args  # cargo test default is members; only narrow if asked
    clippy_scope = per_crate_args if per_crate_args else ["--workspace"]

    # Check for security vulnerabilities (exit code non-zero = vulnerabilities found)
    success, output = run_command(
        ["cargo", "audit"], rust_nix_cmd, timeout=t_audit, cwd=rust_root, config=config
    )

    if "timed out" in output:
        # Don't block on tooling issues
        gaps.append("P2: cargo audit timed out (check network/proxy)")
    elif not success:
        # Exit code non-zero means vulnerabilities found
        preview = format_error_preview(output)
        gaps.append(
            f"P0: Security vulnerabilities found (cargo audit){preview}"
        )

    # Separately check for unmaintained dependencies (warnings only)
    success_json, json_output = run_command(
        ["cargo", "audit", "--json"],
        rust_nix_cmd,
        timeout=t_audit,
        cwd=rust_root,
        config=config,
    )
    if success_json and json_output.strip():
        try:
            audit_data = json.loads(json_output)
            warnings = audit_data.get("warnings", {})
            unmaintained = warnings.get("unmaintained", [])
            if unmaintained:
                gaps.append(f"P2: {len(unmaintained)} unmaintained dependencies (cargo audit)")
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Ignore JSON parsing errors for warnings

    # Check tests - trust exit code only
    success, output = run_command(
        ["cargo", "test", "--quiet", *test_scope, "--all-features"],
        rust_nix_cmd,
        timeout=t_test,
        cwd=rust_root,
        config=config,
    )
    if not success:
        preview = format_error_preview(output)
        gaps.append(f"P1: Failing tests detected{preview}")

    # Check clippy - trust exit code only, expanded scope to catch all warnings
    success, output = run_command(
        ["cargo", "clippy", *clippy_scope, "--all-targets", "--", "-D", "warnings"],
        rust_nix_cmd,
        timeout=t_clippy,
        cwd=rust_root,
        config=config,
    )
    if not success:
        preview = format_error_preview(output)
        gaps.append(f"P1: Clippy warnings detected{preview}")

    # Check formatting - trust exit code only
    success, _ = run_command(
        ["cargo", "fmt", "--check"], rust_nix_cmd, timeout=t_fmt, cwd=rust_root, config=config
    )
    if not success:
        gaps.append("P2: Formatting issues detected (cargo fmt)")

    return gaps


def check_go_gaps(nix_cmd: Optional[str]) -> List[str]:
    """Check for gaps in Go projects."""
    gaps = []

    success, _ = run_command(["govulncheck", "./..."], nix_cmd)
    if not success:
        gaps.append("P0: Vulnerabilities found (govulncheck)")

    success, _ = run_command(["go", "test", "./..."], nix_cmd)
    if not success:
        gaps.append("P1: Failing tests detected")

    success, _ = run_command(["go", "test", "-race", "./..."], nix_cmd)
    if not success:
        gaps.append("P1: Race conditions detected")

    success, _ = run_command(["go", "vet", "./..."], nix_cmd)
    if not success:
        gaps.append("P1: go vet issues detected")

    success, output = run_command(["gofmt", "-l", "."], nix_cmd)
    if output.strip():
        gaps.append("P2: Formatting issues detected (gofmt)")

    success, _ = run_command(["golangci-lint", "run", "--quiet"], nix_cmd)
    if not success:
        gaps.append("P2: Linter violations detected (golangci-lint)")

    return gaps


def check_python_gaps(nix_cmd: Optional[str]) -> List[str]:
    """Check for gaps in Python projects."""
    gaps = []

    success, _ = run_command(["bandit", "-r", ".", "-ll", "--quiet"], nix_cmd)
    if not success:
        gaps.append("P0: Security issues found (bandit)")

    success, _ = run_command(["safety", "check", "--quiet"], nix_cmd)
    if not success:
        gaps.append("P0: Vulnerable dependencies found (safety)")

    success, _ = run_command(["pytest", "--quiet"], nix_cmd)
    if not success:
        gaps.append("P1: Failing tests detected")

    success, _ = run_command(["ruff", "check", ".", "--quiet"], nix_cmd)
    if not success:
        gaps.append("P2: Ruff linter violations detected")

    success, _ = run_command(["ruff", "format", "--check", ".", "--quiet"], nix_cmd)
    if not success:
        gaps.append("P2: Formatting issues detected (ruff)")

    success, _ = run_command(["mypy", ".", "--quiet"], nix_cmd)
    if not success:
        gaps.append("P2: Type checking errors detected (mypy)")

    return gaps


def check_c_gaps(nix_cmd: Optional[str]) -> List[str]:
    """Check for gaps in C projects."""
    gaps = []

    if Path("Makefile").exists():
        success, _ = run_command(["make", "CFLAGS=-Wall -Wextra -Werror", "clean", "all"], nix_cmd)
        if not success:
            gaps.append("P1: Build warnings/errors detected")

    success, _ = run_command(["cppcheck", "--quiet", "--error-exitcode=1", "."], nix_cmd)
    if not success:
        gaps.append("P1: cppcheck issues detected")

    if Path("test").exists():
        success, _ = run_command(["valgrind", "--leak-check=full", "--error-exitcode=1", "--quiet", "./test"], nix_cmd)
        if not success:
            gaps.append("P1: Memory leaks detected (valgrind)")

    return gaps


def check_javascript_gaps(nix_cmd: Optional[str]) -> List[str]:
    """Check for gaps in JavaScript/TypeScript projects."""
    gaps = []

    success, _ = run_command(["npm", "audit", "--audit-level=moderate"], nix_cmd)
    if not success:
        gaps.append("P0: npm audit vulnerabilities found")

    if Path("package.json").exists():
        try:
            with open("package.json", "r") as f:
                content = f.read()
                if '"test"' in content:
                    success, _ = run_command(["npm", "test"], nix_cmd)
                    if not success:
                        gaps.append("P1: Failing tests detected")
        except Exception:
            pass

    if Path("tsconfig.json").exists():
        success, _ = run_command(["npx", "tsc", "--noEmit"], nix_cmd)
        if not success:
            gaps.append("P1: TypeScript compilation errors detected")

    if Path("package.json").exists():
        try:
            with open("package.json", "r") as f:
                if '"lint"' in f.read():
                    success, _ = run_command(["npm", "run", "lint"], nix_cmd)
                    if not success:
                        gaps.append("P2: Linter violations detected")
        except Exception:
            pass

    return gaps


def check_nix_gaps(nix_cmd: Optional[str], config: Optional["IterateConfig"] = None) -> List[str]:
    """Check for gaps in Nix projects."""
    gaps = []

    # Find Nix project root (may be in a subdirectory per .iterate.json)
    nix_root = find_language_root("flake.nix")
    if not nix_root:
        nix_root = find_language_root("default.nix")
    if not nix_root:
        return gaps  # No nix files found

    # Check tool availability before running — missing tools are environment issues, not project gaps
    nix_available, _ = run_command(["nix", "--version"], None, timeout=10)
    nixfmt_available, _ = run_command(["nixfmt", "--version"], None, timeout=10)
    statix_available, _ = run_command(["statix", "--version"], None, timeout=10)

    if (Path(nix_root) / "flake.nix").exists() and nix_available:
        # Use 'nix flake show' to validate the flake without building derivations.
        # 'nix flake check' triggers full builds which can take 30+ minutes for Rust workspaces.
        nix_show_timeout = 120
        if config and config.timeouts:
            nix_show_timeout = config.timeouts.get("nix_flake_check", 120)
        # Run nix flake show directly (not through nix develop) — it validates the flake
        # without building derivations, and nix is available as a direct command.
        success, output = run_command(["nix", "flake", "show"], None, cwd=nix_root, timeout=nix_show_timeout)
        if not success and output.strip() and "timed out" not in output:
            gaps.append("P1: Flake show failed (flake.nix may have syntax/evaluation errors)")

    if nixfmt_available:
        success, _ = run_command(["nixfmt", "--check", "."], nix_cmd, cwd=nix_root)
        if not success:
            gaps.append("P2: Nix formatting issues detected (nixfmt)")

    if statix_available:
        success, _ = run_command(["statix", "check"], nix_cmd, cwd=nix_root)
        if not success:
            gaps.append("P2: statix issues detected")

    # Check for unprefixed shellHook echo statements
    gaps.extend(check_shellhook_output())

    return gaps


def check_shellhook_output() -> List[str]:
    """Find unprefixed echo statements in Nix shellHooks that would pollute command output."""
    gaps = []

    nix_files = []
    if Path("flake.nix").exists():
        nix_files.append("flake.nix")
    if Path("shell.nix").exists():
        nix_files.append("shell.nix")

    for nix_file in nix_files:
        try:
            with open(nix_file, 'r') as f:
                content = f.read()

            # Look for shellHook with echo statements
            # Pattern: shellHook followed by echo without NIX: prefix
            if 'shellHook' in content:
                lines = content.split('\n')
                in_shellhook = False
                has_unprefixed_echo = False

                for i, line in enumerate(lines):
                    stripped = line.strip()

                    # Detect shellHook block start
                    if 'shellHook' in stripped and '=' in stripped:
                        in_shellhook = True
                        continue

                    # Detect block end
                    if in_shellhook and stripped.startswith('}'):
                        in_shellhook = False
                        continue

                    # Check for echo in shellHook
                    if in_shellhook and 'echo' in stripped:
                        # Check if it's prefixed with NIX:
                        if '"NIX:' not in line and "'NIX:" not in line:
                            has_unprefixed_echo = True
                            break

                if has_unprefixed_echo:
                    gaps.append(
                        f"P2: {nix_file} contains unprefixed shellHook echo statements\n"
                        f"    Fix: Prefix all shellHook echo output with 'NIX:' or remove verbose output\n"
                        f"    Note: This MUST be done for projects using flake.nix and shell.nix and then\n"
                        f"    /iterate rerun, otherwise /iterate hook results will be unreliable.\n"
                        f"    Example: echo 'NIX: Welcome to development environment'\n"
                        f"    Reason: Unprefixed output pollutes command output and causes false positives"
                    )

        except (IOError, UnicodeDecodeError):
            # Skip if file can't be read
            pass

    return gaps


# ============================================================================
# Documentation Cross-Reference Checks
# ============================================================================
# These functions parse the project's ADRs, specs, threat model, stories, and
# security requirements to find gaps between what's documented and what's
# actually implemented and tested in code.

def check_threat_model_gaps(config: IterateConfig) -> List[str]:
    """
    Parse threat model entries and flag any whose mitigations aren't implemented.

    Looks for ### TM-XXX-NNN headers, extracts **Status:** lines, and reports
    entries that are Not Started, Partial, or Designed-but-not-implemented.
    """
    gaps = []
    project_root = find_project_root()
    tm_dir = project_root / "docs" / "threat-models"
    if not tm_dir.exists():
        return gaps  # Absence is caught by check_documentation_artifacts

    for tm_file in sorted(tm_dir.glob("*.md")):
        if not config.should_check_path(str(tm_file)):
            continue

        try:
            content = tm_file.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            continue

        lines = content.split("\n")
        current_threat_id = None
        current_threat_title = None

        for line in lines:
            # Match threat entry headers: ### TM-XXX-NNN: Title
            tm_match = re.match(r"^###\s+(TM-[A-Z]+-\d+):\s*(.*)", line)
            if tm_match:
                current_threat_id = tm_match.group(1)
                current_threat_title = tm_match.group(2).strip()
                continue

            # Match status lines within a threat entry
            if current_threat_id and line.strip().startswith("**Status:**"):
                status_text = line.strip()

                if "Not Started" in status_text:
                    gaps.append(
                        f"P0: Threat {current_threat_id} ({current_threat_title}) — "
                        f"mitigation not started. Implement the mitigations listed in the threat model."
                    )
                elif "PARTIAL" in status_text.upper():
                    # Extract what's partial for context
                    detail = status_text.replace("**Status:**", "").strip()
                    gaps.append(
                        f"P1: Threat {current_threat_id} ({current_threat_title}) — "
                        f"mitigation partially implemented: {detail}. Complete the remaining mitigations."
                    )
                elif "DESIGNED" in status_text.upper() and "IMPLEMENTED" not in status_text.upper():
                    gaps.append(
                        f"P1: Threat {current_threat_id} ({current_threat_title}) — "
                        f"designed but not yet implemented. Write code and tests for this mitigation."
                    )
                # IMPLEMENTED entries are fine — no gap

                # Reset after processing status
                current_threat_id = None
                current_threat_title = None

    return gaps


def check_story_implementation_gaps(config: IterateConfig) -> List[str]:
    """
    Parse story files and flag any that are in Draft status without
    corresponding implementation evidence (test files, code references).

    Stories in Draft or Revision N status represent planned but unfinished work.
    """
    gaps = []
    project_root = find_project_root()
    stories_dir = project_root / "docs" / "stories"
    if not stories_dir.exists():
        return gaps

    # Collect all story files
    story_files = sorted(stories_dir.glob("STORY-*.md"))
    draft_stories = []
    implemented_count = 0
    total_count = len(story_files)

    for story_file in story_files:
        if not config.should_check_path(str(story_file)):
            continue

        try:
            content = story_file.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            continue

        story_name = story_file.stem  # e.g., STORY-063-leader-election-privilege-guard

        # Extract story ID and status from either frontmatter or inline format
        story_id = None
        status = None

        # Try YAML frontmatter format
        fm_id = re.search(r"^story_id:\s*(\S+)", content, re.MULTILINE)
        fm_status = re.search(r"^status:\s*(.+)", content, re.MULTILINE)
        if fm_id:
            story_id = fm_id.group(1)
        if fm_status:
            status = fm_status.group(1).strip()

        # Try inline format: **Story ID:** STORY-NNN / **Status:** X
        if not story_id:
            inline_id = re.search(r"\*\*Story ID:\*\*\s*(\S+)", content)
            if inline_id:
                story_id = inline_id.group(1)
        if not status:
            inline_status = re.search(r"\*\*Status:\*\*\s*(.+)", content)
            if inline_status:
                status = inline_status.group(1).strip()

        if not story_id:
            story_id = story_name

        # Classify status
        status_lower = (status or "").lower()
        if any(kw in status_lower for kw in ["implemented", "complete", "done", "accepted", "shipped"]):
            implemented_count += 1
            continue

        # Draft or Revision = not yet implemented
        draft_stories.append((story_id, status or "Unknown"))

    # Report summary + individual gaps
    if draft_stories:
        # Group by priority: newer stories (higher numbers) are typically lower priority
        # But we report all of them so the iterate skill can prioritize
        gaps.append(
            f"P1: {len(draft_stories)}/{total_count} stories not yet implemented "
            f"({implemented_count} implemented). Stories represent planned features "
            f"and security hardening that need code + tests."
        )

        # List up to 20 individual stories (avoid overwhelming output)
        for story_id, status in draft_stories[:20]:
            gaps.append(
                f"P1: {story_id} (status: {status}) — "
                f"implement acceptance criteria and add tests"
            )

        if len(draft_stories) > 20:
            gaps.append(
                f"P1: ... and {len(draft_stories) - 20} more unimplemented stories "
                f"(see docs/stories/ for full list)"
            )

    return gaps


def check_security_requirement_gaps(config: IterateConfig) -> List[str]:
    """
    Parse SECURITY-REQUIREMENTS.md and flag any SR entries that aren't fully
    implemented. Cross-references the threat model status for each SR.
    """
    gaps = []
    project_root = find_project_root()

    # Try multiple possible locations
    sr_paths = [
        project_root / "docs" / "SECURITY-REQUIREMENTS.md",
        project_root / "docs" / "security-requirements.md",
        project_root / "SECURITY-REQUIREMENTS.md",
    ]

    sr_file = None
    for path in sr_paths:
        if path.exists():
            sr_file = path
            break

    if not sr_file:
        return gaps  # No security requirements file — that's fine for some projects

    try:
        content = sr_file.read_text(encoding="utf-8")
    except (IOError, UnicodeDecodeError):
        return gaps

    # Parse SR entries: ### SR-NNN: Title
    lines = content.split("\n")
    current_sr = None
    current_title = None

    for i, line in enumerate(lines):
        sr_match = re.match(r"^###\s+(SR-\d+):\s*(.*)", line)
        if sr_match:
            current_sr = sr_match.group(1)
            current_title = sr_match.group(2).strip()
            continue

        # Look for implementation status within each SR section
        # Check the next ~30 lines after the SR header for status indicators
        if current_sr and i > 0:
            # Look for status/implementation markers
            if "**Implementation Status:**" in line or "**Status:**" in line:
                status_text = line.strip()

                if "Not Started" in status_text or "not started" in status_text:
                    gaps.append(
                        f"P0: Security requirement {current_sr} ({current_title}) — "
                        f"not started. Implement this security control."
                    )
                elif "Partial" in status_text or "partial" in status_text:
                    gaps.append(
                        f"P0: Security requirement {current_sr} ({current_title}) — "
                        f"partially implemented. Complete remaining acceptance criteria."
                    )

                current_sr = None
                current_title = None

            # Also detect section boundaries
            if line.startswith("### ") and not line.startswith(f"### {current_sr}"):
                # Moved to next section without finding status — flag it
                # (only if we haven't already processed this SR)
                if current_sr:
                    current_sr = None
                    current_title = None

    return gaps


def check_adr_implementation_gaps(config: IterateConfig) -> List[str]:
    """
    Parse ADR files and check whether the decisions they document have
    corresponding implementation in the codebase.

    Looks for:
    - Implementation Location sections that reference files → checks files exist
    - ADRs with status 'accepted' that have no code references in the codebase
    """
    gaps = []
    project_root = find_project_root()
    adr_dir = project_root / "docs" / "adr"
    if not adr_dir.exists():
        return gaps

    for adr_file in sorted(adr_dir.glob("*.md")):
        if not config.should_check_path(str(adr_file)):
            continue

        try:
            content = adr_file.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            continue

        # Extract ADR number from filename: 0036-presence-leader-election.md
        adr_match = re.match(r"(\d+)-(.+)\.md", adr_file.name)
        if not adr_match:
            continue

        adr_num = adr_match.group(1)
        adr_id = f"ADR-{adr_num}"

        # Check status — only flag accepted ADRs (not proposed/deprecated/superseded)
        status_match = re.search(r"^status:\s*(.+)", content, re.MULTILINE)
        if status_match:
            status = status_match.group(1).strip().lower()
            if status in ("deprecated", "superseded", "proposed"):
                continue

        # Look for "Implementation Location" or "Implementation" section
        impl_section = re.search(
            r"##\s*Implementation(?:\s+Location)?[^\n]*\n(.*?)(?=\n##|\Z)",
            content,
            re.DOTALL | re.IGNORECASE,
        )

        if impl_section:
            impl_text = impl_section.group(1)

            # Extract file paths mentioned (e.g., `crates/donbiki-notify/src/desktop.rs`,
            # `internal/foo/bar.go`, `scripts/check.py`). Matches any
            # backtick-quoted relative path ending in a source extension
            # for one of this skill's supported languages — not just
            # Rust's `crates/` convention, which silently skipped this
            # check entirely for Go/Python/JS/Nix/C projects.
            file_refs = re.findall(
                r"`([A-Za-z0-9_][A-Za-z0-9_\-./]*\."
                r"(?:rs|go|py|rb|c|h|cc|cpp|hpp|js|jsx|ts|tsx|nix|sh))`",
                impl_text,
            )
            for file_ref in file_refs:
                full_path = project_root / file_ref
                if not full_path.exists():
                    gaps.append(
                        f"P1: {adr_id} references implementation file "
                        f"`{file_ref}` which doesn't exist. "
                        f"Implement the code described in this ADR."
                    )

    return gaps


def check_spec_task_gaps(config: IterateConfig) -> List[str]:
    """
    Parse spec files and check whether the implementation tasks they describe
    have corresponding code files and test coverage.

    Specs use a "### Task N: Description" format with **File:** markers.
    """
    gaps = []
    project_root = find_project_root()
    specs_dir = project_root / "docs" / "specs"
    if not specs_dir.exists():
        return gaps

    missing_files = []
    missing_tests = []

    for spec_file in sorted(specs_dir.glob("*.md")):
        if spec_file.name == "README.md":
            continue
        if not config.should_check_path(str(spec_file)):
            continue

        try:
            content = spec_file.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            continue

        spec_name = spec_file.stem  # e.g., 04-task-management

        # Extract file references from **File:** markers
        file_refs = re.findall(r"\*\*File:\*\*\s*`([^`]+)`", content)
        for file_ref in file_refs:
            full_path = project_root / file_ref
            if not full_path.exists():
                missing_files.append((spec_name, file_ref))

        # Extract test references from **Test:** or ```rust sections
        # that reference specific test module paths
        test_file_refs = re.findall(r"\*\*Test(?:\s+File)?:\*\*\s*`([^`]+)`", content)
        for test_ref in test_file_refs:
            full_path = project_root / test_ref
            if not full_path.exists():
                missing_tests.append((spec_name, test_ref))

    if missing_files:
        gaps.append(
            f"P1: {len(missing_files)} implementation files referenced in specs "
            f"don't exist yet. These represent planned but unwritten code."
        )
        for spec_name, file_ref in missing_files[:10]:
            gaps.append(f"P1: Spec {spec_name} → missing `{file_ref}`")
        if len(missing_files) > 10:
            gaps.append(f"P1: ... and {len(missing_files) - 10} more missing spec files")

    if missing_tests:
        gaps.append(
            f"P1: {len(missing_tests)} test files referenced in specs "
            f"don't exist yet."
        )
        for spec_name, test_ref in missing_tests[:10]:
            gaps.append(f"P2: Spec {spec_name} → missing test `{test_ref}`")
        if len(missing_tests) > 10:
            gaps.append(f"P2: ... and {len(missing_tests) - 10} more missing test files")

    return gaps


def check_honesty_drift_gaps(config: IterateConfig) -> List[str]:
    """
    Catch documentation honesty drift: stories marked Implemented whose
    bodies contain deferral language, and specs with traceability rows
    flagged `Partial`.

    This is the STORY-146 failure mode — a story's status field says
    Implemented, but the body says "detachable dependency-graph tab
    deferred until the graph RPC lands". The status is a lie relative
    to the acceptance criteria. Iterate must catch this and treat the
    deferred item as the next task.

    Similarly, spec rows with `Partial` are incomplete work, not
    acceptable status quo — the "partial" annotation is an admission
    that the requirement isn't fully delivered.
    """
    gaps: List[str] = []
    project_root = find_project_root()

    # Patterns that indicate deferral even when status is "Implemented"
    deferral_patterns = [
        r"\bdeferred\s+(?:until|since|because|pending)\b",
        r"\bdetachable.{0,40}tab\s+remains?\s+deferred\b",
        r"\bis\s+deferred\s+until\b",
        r"\bplaceholder\s+(?:view|module|implementation)\b",
        r"\bawait(?:s|ing)?\s+the\s+(?:RPC|contract|payload|implementation)\b",
        r"\bnot\s+yet\s+wired\b",
        r"\bwaits?\s+on\s+the\s+(?:upstream|payload|graph|contract)\b",
        r"\bwill\s+land\s+(?:once|when|with|after)\b",
        r"\bfollow-?up\s+(?:tracked|deferred|pending)\b",
        r"\bcan'?t\s+be\s+delivered\s+without\b",
    ]

    # --- Stories marked Implemented but containing deferral language ----
    stories_dir = project_root / "docs" / "stories"
    drift_stories: List[Tuple[str, str, str]] = []  # (id, matched_phrase, context)
    if stories_dir.exists():
        for story_file in sorted(stories_dir.glob("STORY-*.md")):
            if not config.should_check_path(str(story_file)):
                continue
            try:
                content = story_file.read_text(encoding="utf-8")
            except (IOError, UnicodeDecodeError):
                continue

            status_match = re.search(
                r"^\s*(?:\*\*Status:\*\*|status:)\s*(.+?)$",
                content,
                re.MULTILINE | re.IGNORECASE,
            )
            if not status_match:
                continue
            status = status_match.group(1).strip().lower()
            if not any(
                kw in status for kw in ["implemented", "complete", "done", "accepted", "shipped"]
            ):
                continue  # Draft/Revision already caught by the regular story scan

            for pattern in deferral_patterns:
                m = re.search(pattern, content, re.IGNORECASE)
                if not m:
                    continue
                start = max(0, m.start() - 30)
                end = min(len(content), m.end() + 80)
                ctx = content[start:end].replace("\n", " ").strip()
                drift_stories.append((story_file.stem, m.group(0), ctx))
                break  # one match per story is enough

    if drift_stories:
        gaps.append(
            f"P1: {len(drift_stories)} stor{'y' if len(drift_stories) == 1 else 'ies'} "
            f"marked Implemented but carry deferral language in the body. A story's "
            f"status must match its acceptance criteria — if a scenario is deferred, "
            f"the status is at most `Partial`, not `Implemented`. Close the deferral "
            f"by implementing the missing piece, or re-status the story to reflect "
            f"reality."
        )
        for sid, phrase, ctx in drift_stories[:10]:
            gaps.append(
                f"P1: {sid} — contains \"{phrase}\" (context: …{ctx[:120]}…). "
                f"Implement the deferred scenario now."
            )
        if len(drift_stories) > 10:
            gaps.append(f"P1: ... and {len(drift_stories) - 10} more stories with drift")

    # --- Specs with `Partial` traceability rows ----
    specs_dir = project_root / "docs" / "specs"
    partial_rows: List[Tuple[str, int, str]] = []  # (spec, line_no, line)
    if specs_dir.exists():
        for spec_file in sorted(specs_dir.glob("SPEC-*.md")):
            if not config.should_check_path(str(spec_file)):
                continue
            try:
                content = spec_file.read_text(encoding="utf-8")
            except (IOError, UnicodeDecodeError):
                continue
            for i, line in enumerate(content.splitlines(), start=1):
                # Traceability rows look like `| FR-X | desc | ... | Partial |`
                if not line.strip().startswith("|"):
                    continue
                if re.search(r"\|\s*(?:Partial|Draft|Deferred|Pending)\b", line, re.IGNORECASE):
                    partial_rows.append((spec_file.stem, i, line.strip()[:200]))

    if partial_rows:
        gaps.append(
            f"P1: {len(partial_rows)} Partial/Draft/Deferred row{'s' if len(partial_rows) != 1 else ''} "
            f"in spec traceability matrices. Each row is a requirement the project "
            f"admits isn't fully delivered. `Partial` isn't an acceptable end state — "
            f"close the gap or explicitly re-scope the requirement."
        )
        for spec_name, line_no, line in partial_rows[:10]:
            gaps.append(f"P1: {spec_name}:{line_no} — {line}")
        if len(partial_rows) > 10:
            gaps.append(f"P1: ... and {len(partial_rows) - 10} more partial rows")

    # --- Spec bodies still in Draft status ----
    if specs_dir.exists():
        draft_specs: List[str] = []
        for spec_file in sorted(specs_dir.glob("SPEC-*.md")):
            try:
                content = spec_file.read_text(encoding="utf-8")
            except (IOError, UnicodeDecodeError):
                continue
            # Look for **Status:** Draft in the spec header
            m = re.search(
                r"^\*\*Status:\*\*\s*Draft\b",
                content,
                re.MULTILINE | re.IGNORECASE,
            )
            if m:
                draft_specs.append(spec_file.stem)

        if draft_specs:
            gaps.append(
                f"P2: {len(draft_specs)} spec{'s' if len(draft_specs) != 1 else ''} "
                f"still in Draft status. Draft specs get ignored; move to Revision N "
                f"with a revision-history entry or to an Accepted/Approved status "
                f"once the requirements are stable."
            )
            for spec_name in draft_specs:
                gaps.append(f"P2: {spec_name} — still Draft, update the Status header")

    return gaps


def check_cross_reference_matrix(config: IterateConfig) -> List[str]:
    """
    Validate cross-references between stories, ADRs, and threat model entries.

    Checks:
    - Stories that reference ADRs → ADR exists
    - Stories that reference threat IDs → threat entry exists
    - Threat mitigations that reference stories → story exists
    """
    gaps = []
    project_root = find_project_root()

    stories_dir = project_root / "docs" / "stories"
    adr_dir = project_root / "docs" / "adr"
    tm_dir = project_root / "docs" / "threat-models"

    # Build index of existing artifacts
    existing_adrs = set()
    if adr_dir.exists():
        for f in adr_dir.glob("*.md"):
            # Support both NNNN-description.md and ADR-NNNN-description.md
            m = re.match(r"(?:ADR-)?(\d+)-", f.name)
            if m:
                existing_adrs.add(f"ADR-{m.group(1)}")

    existing_stories = set()
    if stories_dir.exists():
        for f in stories_dir.glob("STORY-*.md"):
            m = re.match(r"STORY-(\d+)", f.name)
            if m:
                existing_stories.add(f"STORY-{m.group(1)}")

    existing_threats = set()
    if tm_dir.exists():
        for f in tm_dir.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                for tm_match in re.finditer(r"###\s+(TM-[A-Z]+-\d+)", content):
                    existing_threats.add(tm_match.group(1))
            except (IOError, UnicodeDecodeError):
                continue

    # Check story cross-references
    broken_refs = []
    if stories_dir.exists():
        for story_file in stories_dir.glob("STORY-*.md"):
            try:
                content = story_file.read_text(encoding="utf-8")
            except (IOError, UnicodeDecodeError):
                continue

            story_name = story_file.stem

            # Check ADR references
            for adr_ref in re.finditer(r"ADR-(\d+)", content):
                adr_id = f"ADR-{adr_ref.group(1)}"
                if adr_id not in existing_adrs:
                    broken_refs.append(f"{story_name} → {adr_id} (ADR doesn't exist)")

            # Check threat model references
            for tm_ref in re.finditer(r"(TM-[A-Z]+-\d+)", content):
                tm_id = tm_ref.group(1)
                if tm_id not in existing_threats:
                    broken_refs.append(f"{story_name} → {tm_id} (threat entry doesn't exist)")

            # Check story dependency references
            for dep_ref in re.finditer(r"STORY-(\d+)", content):
                dep_id = f"STORY-{dep_ref.group(1)}"
                # Don't flag self-references
                story_id_match = re.match(r"STORY-(\d+)", story_name)
                if story_id_match and f"STORY-{story_id_match.group(1)}" == dep_id:
                    continue
                if dep_id not in existing_stories:
                    broken_refs.append(f"{story_name} → {dep_id} (story doesn't exist)")

    if broken_refs:
        gaps.append(
            f"P2: {len(broken_refs)} broken cross-references between documentation artifacts"
        )
        for ref in broken_refs[:10]:
            gaps.append(f"P2: Broken reference: {ref}")
        if len(broken_refs) > 10:
            gaps.append(f"P2: ... and {len(broken_refs) - 10} more broken references")

    return gaps


# ============================================================================
# Main Hook Logic
# ============================================================================

def main():
    """Main hook execution."""
    SKILL_NAME = "iterate"

    # Load configuration first
    config = IterateConfig()

    # Read hook input
    hook_input = read_hook_input()

    # Change to the project directory Claude Code was running in.
    # Without this, all Path() checks and tool invocations run against
    # whatever directory launched the hook process (often ~/.claude or /workspace),
    # not the actual project being iterated on.
    project_cwd = hook_input.get("cwd")
    if project_cwd and Path(project_cwd).is_dir():
        os.chdir(project_cwd)

    # Check if we're in background/sub-agent context and should skip expensive checks
    if config.skip_in_background and is_background_context(hook_input):
        # Return success quickly to avoid resource contention
        output = {
            "decision": "approve",
            "reason": "Skipping completion check in background context to avoid resource contention"
        }
        log_hook(SKILL_NAME, hook_input, output, [])
        send_output(output)

    # Check if we should skip
    if should_skip(hook_input):
        output = {}
        log_hook(SKILL_NAME, hook_input, output, [])
        send_output(output)

    # Check for background tasks FIRST - don't check gaps until tasks complete
    background_tasks = hook_input.get("background_tasks", [])
    if background_tasks:
        tasks_to_kill, still_running, should_wait = check_background_tasks(SKILL_NAME, background_tasks)

        # Build instructions for Claude
        instructions = []

        if tasks_to_kill:
            instructions.append(f"Kill background tasks that exceeded 30-minute timeout: {', '.join(tasks_to_kill)}")

        if still_running:
            minutes_remaining = []
            tracked = track_background_tasks(SKILL_NAME, background_tasks)
            now = time.time()
            for task_id in still_running:
                if task_id in tracked:
                    elapsed = (now - tracked[task_id]) / 60
                    remaining = 30 - elapsed
                    minutes_remaining.append(f"{task_id} ({remaining:.1f} min remaining)")

            task_list = ", ".join(minutes_remaining) if minutes_remaining else ", ".join(still_running)
            instructions.append(f"Background tasks still running: {task_list}")
            instructions.append("Wait 60 seconds, then re-run /{} to check task status again".format(SKILL_NAME))
            instructions.append(
                "Once background tasks are finished, rerun /{} in the main "
                "conversation, then continue iterating on implementation "
                "gaps until all gaps are closed".format(SKILL_NAME)
            )

        if instructions:
            reason = "\n\n".join(instructions)
            output = {"decision": "block", "reason": reason}
            log_hook(SKILL_NAME, hook_input, output, [])
            send_output(output)

    # No background tasks (or all completed) - clean up tracking and check for gaps
    cleanup_task_tracking(SKILL_NAME, background_tasks)

    # `config` was already loaded above (and used for skip_in_background);
    # reuse it instead of re-parsing .iterate.json from scratch.

    # Detect Nix environment
    uses_nix, nix_shell_cmd = detect_nix_environment()

    # Detect languages — returns a set of all detected languages.
    # "unknown" is fine, we still run all language-agnostic checks.
    # Respects include_paths/exclude_paths from .iterate.json so we don't
    # false-detect languages from the host repo in monorepo setups.
    languages = detect_languages(config)

    # Collect ALL gaps comprehensively - no weaseling out!
    gaps = []

    # P0: Documentation artifacts (spec, ADR, threat model)
    gaps.extend(check_documentation_artifacts())

    # P0-P1: Implementation completeness (no TODOs, no placeholders, no dead code)
    gaps.extend(check_implementation_completeness(nix_shell_cmd, config))

    # P0-P1: Security vulnerabilities and hardcoded secrets
    gaps.extend(check_security_comprehensive(languages, nix_shell_cmd, config))

    # P1: Test coverage (80% minimum)
    gaps.extend(check_test_coverage(languages, nix_shell_cmd, config))

    # P1: Frontend/backend/API/database completeness
    gaps.extend(check_frontend_backend_completeness(nix_shell_cmd, config))

    # P0-P1: Threat model mitigation gaps (Not Started / Partial / Designed)
    gaps.extend(check_threat_model_gaps(config))

    # P0: Security requirement implementation gaps (SR-NNN entries)
    gaps.extend(check_security_requirement_gaps(config))

    # P1: Story implementation gaps (Draft/unimplemented stories)
    gaps.extend(check_story_implementation_gaps(config))

    # P1: ADR implementation gaps (accepted ADRs with missing code)
    gaps.extend(check_adr_implementation_gaps(config))

    # P1-P2: Spec task gaps (referenced files that don't exist)
    gaps.extend(check_spec_task_gaps(config))

    # P1: Honesty drift — Implemented stories with deferral language,
    # Partial traceability rows, Draft spec headers
    gaps.extend(check_honesty_drift_gaps(config))

    # P2: Cross-reference integrity (broken links between docs)
    gaps.extend(check_cross_reference_matrix(config))

    # P0-P2: Language-specific quality checks (runs for each detected language)
    if "rust" in languages:
        gaps.extend(check_rust_gaps(nix_shell_cmd, config))
    if "go" in languages:
        gaps.extend(check_go_gaps(nix_shell_cmd))
    if "python" in languages:
        gaps.extend(check_python_gaps(nix_shell_cmd))
    if "c" in languages:
        gaps.extend(check_c_gaps(nix_shell_cmd))
    if "javascript" in languages:
        gaps.extend(check_javascript_gaps(nix_shell_cmd))
    if "nix" in languages:
        gaps.extend(check_nix_gaps(nix_shell_cmd, config))

    # Behavioural scans — read the last assistant turn and check for
    # stopping-bias tells. These run regardless of gap count because even
    # a clean project can be hit by a premature summary-then-stop.
    last_turn_text = read_last_assistant_turn(hook_input)
    forbidden_matches = scan_forbidden_stop_phrases(last_turn_text)
    tool_counts = count_recent_assistant_tool_calls(hook_input)
    verification_only = is_verification_only_turn(tool_counts)

    # Make decision based on gaps AND behavioural flags.
    must_block, verification_only_with_gaps = compute_must_block(
        gaps, forbidden_matches, verification_only
    )

    if must_block:
        sections = []

        # Behavioural lead — if the last turn tripped a forbidden phrase
        # or was verification-only, name it before the gap list.
        if forbidden_matches:
            lines = [
                "BEHAVIOURAL BLOCK — premature stop pattern detected.",
                "",
                f"The last assistant turn matched {len(forbidden_matches)} "
                f"forbidden stop phrase(s). These phrases are explicit stopping-"
                f"bias tells that the /iterate skill's 'Hard overrides' section "
                f"bans:",
                "",
            ]
            for phrase, ctx in forbidden_matches[:8]:
                lines.append(f"  - matched \"{phrase}\" in: …{ctx[:140]}…")
            if len(forbidden_matches) > 8:
                lines.append(f"  - ... and {len(forbidden_matches) - 8} more")
            lines += [
                "",
                "Required next action: delete the summary/deferral sentence from",
                "your draft and issue your next code-change tool call in this",
                "same turn. Do not write a replacement summary. Do not ask the",
                "user to re-invoke. Pick a gap from the list below and start",
                "editing.",
            ]
            sections.append("\n".join(lines))

        if verification_only_with_gaps:
            name_counts = ", ".join(f"{n}×{c}" for n, c in sorted(tool_counts.items()))
            sections.append(
                "BEHAVIOURAL BLOCK — verification-only turn detected.\n\n"
                f"The last assistant turn made tool calls [{name_counts}] but "
                "zero Edit/Write/MultiEdit calls. /iterate closes gaps via "
                "code changes; verification without change is not an "
                "iteration, it's a read-only pass.\n\n"
                "Required next action: pick a gap from the list below and "
                "make a concrete code change. The verification budget rule "
                "in the skill forbids re-verifying baseline state without "
                "an accompanying change."
            )

        # Standard stop-failure preamble
        sections.append(
            f"YOU SHOULD NOT HAVE STOPPED. The /{SKILL_NAME} skill explicitly\n"
            f"overrides Claude Code's default end-of-turn behavior. Reaching this\n"
            f"hook means you wrote a user-facing summary and handed control back\n"
            f"to the user — that is the failure mode the skill warns about in its\n"
            f"'Single-Turn Autonomy' and 'Hard overrides' sections. Do NOT treat\n"
            f"this block as a new turn starting.\n\n"
            f"Required behavior NOW (in this same turn, without pausing for\n"
            f"acknowledgement):\n"
            f"  1. Stop writing summary paragraphs. No ordinals ('iteration N'),\n"
            f"     no 'moved the needle', no 'remaining debt', no 're-invoke'.\n"
            f"  2. Treat every 'deferred' / 'Partial' / 'placeholder' / 'awaits\n"
            f"     upstream' annotation as the DEFINITION of the next task, not\n"
            f"     as acceptable status. If a story says 'deferred until X lands',\n"
            f"     go build X.\n"
            f"  3. Start your next code change via Edit or Write. Do NOT start\n"
            f"     with another Bash/Read/Grep 'let me verify' call — the\n"
            f"     verification budget rule forbids baseline re-verification.\n"
            f"  4. Keep iterating until either (a) all stopping criteria in\n"
            f"     Step 6 pass and this hook returns zero gaps, or (b) you hit\n"
            f"     a genuinely irrecoverable blocker that only the user can\n"
            f"     resolve (missing credential, policy decision, tool that\n"
            f"     fundamentally cannot be installed in this environment).\n"
            f"     'The upstream RPC doesn't exist' is NOT a valid blocker —\n"
            f"     implement it.\n\n"
            f"If you believe any of the gaps listed below are wrong, you MUST\n"
            f"cite specific data (file paths, line numbers, test output)\n"
            f"demonstrating why — then continue iterating on the remaining\n"
            f"valid gaps. You MUST NOT use disagreement with the hook as an\n"
            f"excuse to stop.\n\n"
            f"It is far more likely the project is not yet complete per its\n"
            f"ADRs, specs, and threat model than that this hook is wrong. If\n"
            f"in any doubt, re-read those artifacts and pick the highest-\n"
            f"priority unaddressed gap — then start the next iteration.\n"
        )

        if gaps:
            sections.append(
                "IDENTIFIED GAPS — reassess against the current state of the "
                "ADRs, specs, and threat model at the start of each iteration, "
                "since earlier iterations may have resolved some.\n\n"
                + "\n".join(f"- {gap}" for gap in gaps)
            )
        else:
            sections.append(
                "NO DOC-LEVEL GAPS IDENTIFIED — the behavioural block above is "
                "the entire reason for this stop rejection. Run the gap-hunt "
                "probes from the skill's 'If you find no obvious next gap, "
                "scan harder' checklist before considering another stop."
            )

        reason = "\n\n".join(sections)
        output = {"decision": "block", "reason": reason}
        log_hook(SKILL_NAME, hook_input, output, gaps)
        tmux_send_iterate_fallback()
        send_output(output)
    else:
        # True clean state: no doc-level gaps, no forbidden phrases, no
        # verification-only turn. This is the only exit path that means
        # "really done".
        reason = (
            "All doc-level gaps closed and the last assistant turn didn't "
            "match any forbidden-stop patterns. Before accepting this stop, "
            "confirm you've run the 'scan harder' probes from the skill: grep "
            "for TODO/FIXME/HACK/XXX/unimplemented!/todo!()/#[ignore]/"
            "#[allow(dead_code)]/awaiting/pending across source and docs; "
            "check every story's Gherkin scenarios for test coverage; run "
            "`cargo outdated` / `npm outdated` equivalents. If any of those "
            "surface new gaps, keep iterating. Do NOT use AskUserQuestion "
            "to check in — the user pre-authorized the full loop when they "
            "invoked the skill."
        )
        output = {"decision": "approve", "reason": reason}
        log_hook(SKILL_NAME, hook_input, output, [])
        send_output(output)


if __name__ == "__main__":
    main()
