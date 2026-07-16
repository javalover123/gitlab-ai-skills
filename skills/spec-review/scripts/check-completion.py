#!/usr/bin/env python3
"""
Completion checker for the spec-review skill's stop hook.

Determines if spec review should continue by validating quality gates.
When gaps remain, blocks continuation with gap list for Claude to address.

Uses JSON input/output per Claude Code hooks specification:
https://code.claude.com/docs/en/hooks#json-output

Configuration:
  Create .spec-review.json in project root to customize timeouts:
  {
    "background_task_timeout_minutes": 30,
    "skip_in_background": true
  }
"""

import json
import os
import sys
import re
import time
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


# ============================================================================
# Configuration Loading
# ============================================================================

class SpecReviewConfig:
    """Handles configuration for the spec-review skill based on .spec-review.json config."""

    def __init__(self):
        self.background_task_timeout_minutes: int = 30
        self.skip_in_background: bool = True
        self._load_config()

    def _load_config(self):
        """Load configuration from .spec-review.json when present in project root."""
        config_file = Path(os.getcwd()) / ".spec-review.json"
        if not config_file.exists():
            return

        try:
            with open(config_file, "r") as f:
                config = json.load(f)

            if "background_task_timeout_minutes" in config:
                self.background_task_timeout_minutes = int(config["background_task_timeout_minutes"])

            if "skip_in_background" in config:
                self.skip_in_background = bool(config["skip_in_background"])
        except:
            pass  # Use defaults if config is invalid


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


def log_hook(skill_name: str, hook_input: Dict[str, Any], output: Dict[str, Any], gaps: List[str]) -> None:
    """Log hook invocations to temp directory for debugging and auditing."""
    log_dir = Path(tempfile.gettempdir()) / "claude-code-hooks" / skill_name
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().isoformat()
    log_file = log_dir / f"hook-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

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
    except:
        pass  # Don't fail the hook if logging fails


def should_skip(hook_input: Dict[str, Any]) -> bool:
    """Check if we should skip iteration (subagent, background, or stop hook active)."""
    # Check if stop hook already triggered
    if hook_input.get("stop_hook_active", False):
        return True

    # Check if this is a subagent
    if hook_input.get("parent_task_id") or hook_input.get("agent_type") or hook_input.get("is_subagent", False):
        return True

    # Check if this is a background task
    if hook_input.get("run_in_background") or hook_input.get("is_background", False):
        return True

    return False


def get_task_tracking_file(skill_name: str) -> Path:
    """Get path to task tracking file."""
    log_dir = Path(tempfile.gettempdir()) / "claude-code-hooks" / skill_name
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "background-tasks.json"


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
        except:
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
        except:
            pass

    return tracked_tasks


def check_background_tasks(skill_name: str, task_ids: List[str], timeout_minutes: int = 30) -> tuple[List[str], List[str], bool]:
    """
    Check background task status and runtime.

    Args:
        skill_name: Name of the skill for tracking
        task_ids: List of active task IDs
        timeout_minutes: Maximum runtime before killing tasks (default 30)

    Returns:
        (tasks_to_kill, still_running_tasks, should_wait)
        - tasks_to_kill: tasks running > timeout
        - still_running_tasks: tasks still running < timeout
        - should_wait: True if we should wait 60s and check again
    """
    if not task_ids:
        return [], [], False

    # Track tasks
    tracked_tasks = track_background_tasks(skill_name, task_ids)

    now = time.time()
    timeout_seconds = timeout_minutes * 60

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
            except:
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
    except:
        pass


# ============================================================================


# Spec Review Gap Checking
# ============================================================================
# SCOPE: Specification quality and completeness ONLY
#
# This hook checks that implementation specifications exist, have required
# sections, cross-reference ADRs and threat models correctly, and have no
# unresolved quality issues.
#
# This hook does NOT check:
# - Whether spec requirements are implemented in code
# - Whether code has TODOs
# - Whether features are complete
#
# Rationale: Specs document current AND planned implementation. A complete spec
# means all requirements are documented, not that all requirements are implemented.
# Code can have TODOs for unimplemented features as long as they're tracked as
# requirements in the spec.
#
# For implementation completeness, use /iterate instead.
# ============================================================================

DOCS_DIR = Path("docs")
SPECS_DIR = DOCS_DIR / "specs"


def find_report() -> Optional[Path]:
    """Locate the spec review report."""
    candidates = [
        DOCS_DIR / "spec-review-report.md",
        DOCS_DIR / "specs" / "review-report.md",
        DOCS_DIR / "reviews" / "spec-review.md",
        DOCS_DIR / "spec-review.md",
    ]

    for path in candidates:
        if path.exists():
            return path
    return None


def check_specs_exist() -> List[str]:
    """Check: spec directory exists and has content."""
    gaps = []

    if not SPECS_DIR.exists():
        gaps.append(f"No specs directory at {SPECS_DIR}")
        return gaps

    if not list(SPECS_DIR.glob("*.md")):
        gaps.append("Specs directory exists but contains no .md files")

    return gaps


def check_report_exists() -> List[str]:
    """Check: review report exists."""
    report = find_report()
    if not report:
        return ["No spec review report found — review hasn't produced output yet"]
    return []


def check_report_sections() -> List[str]:
    """Check: report has all expected sections."""
    gaps = []
    report = find_report()
    if not report:
        return gaps

    content = report.read_text()
    required_sections = ["Summary", "Gap", "Recommend"]

    for section in required_sections:
        if not re.search(section, content, re.IGNORECASE):
            gaps.append(f"Report missing expected section containing '{section}'")

    return gaps


def check_unresolved_findings() -> List[str]:
    """Check: no unresolved Critical or Important findings."""
    gaps = []
    report = find_report()
    if not report:
        return gaps

    content = report.read_text()

    if re.search(r"critical|block.?release", content, re.IGNORECASE):
        critical_sections = re.findall(
            r"^#.*(?:[Cc]ritical|[Bb]lock.*[Rr]elease).*?(?=^#|\Z)",
            content,
            re.MULTILINE | re.DOTALL
        )
        for section in critical_sections:
            unchecked = section.count("- [ ]")
            if unchecked > 0:
                gaps.append(f"{unchecked} unresolved Critical finding(s) in report")
                break

    if re.search(r"important|fix.?soon", content, re.IGNORECASE):
        important_sections = re.findall(
            r"^#.*(?:[Ii]mportant|[Ff]ix.*[Ss]oon).*?(?=^#|\Z)",
            content,
            re.MULTILINE | re.DOTALL
        )
        for section in important_sections:
            unchecked = section.count("- [ ]")
            if unchecked > 0:
                gaps.append(f"{unchecked} unresolved Important finding(s) in report")
                break

    return gaps


def check_cross_references() -> List[str]:
    """Check: cross-references to ADRs and threat model are intact."""
    gaps = []
    report = find_report()
    if not report or not SPECS_DIR.exists():
        return gaps

    adr_dir = DOCS_DIR / "adr"
    tm_dir = DOCS_DIR / "threat-models"

    if adr_dir.exists():
        for spec_file in SPECS_DIR.glob("*.md"):
            content = spec_file.read_text()
            adr_refs = re.findall(r"ADR-([0-9]+)", content)

            for ref_num in set(adr_refs):
                found = any(
                    adr_file.name for adr_file in adr_dir.glob("*.md")
                    if re.search(rf"(?:^|-)0*{ref_num}(?:-|\.)", adr_file.name)
                )
                if not found:
                    gaps.append(f"Spec references ADR-{ref_num} but no matching ADR file found")

    if tm_dir.exists():
        for spec_file in SPECS_DIR.glob("*.md"):
            content = spec_file.read_text()
            tm_refs = re.findall(r"(TM-[A-Z]+-[0-9]+)", content)

            for ref in set(tm_refs):
                found = any(ref in tm.read_text() for tm in tm_dir.glob("*.md"))
                if not found:
                    gaps.append(f"Spec references {ref} but not found in threat models")

    return gaps


# ============================================================================


# ============================================================================
# Main Hook Logic
# ============================================================================

def main():
    """Main hook execution."""
    SKILL_NAME = "spec-review"

    # Load configuration first
    config = SpecReviewConfig()

    # Read hook input
    hook_input = read_hook_input()

    # Change to the project directory Claude Code was running in.
    # Without this, all Path() checks run against the hook process launch directory,
    # not the actual project being worked on.
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
        tasks_to_kill, still_running, should_wait = check_background_tasks(
            SKILL_NAME, background_tasks, config.background_task_timeout_minutes
        )

        # Build instructions for Claude
        instructions = []

        if tasks_to_kill:
            instructions.append(f"Kill background tasks that exceeded {config.background_task_timeout_minutes}-minute timeout: {', '.join(tasks_to_kill)}")

        if still_running:
            minutes_remaining = []
            tracked = track_background_tasks(SKILL_NAME, background_tasks)
            now = time.time()
            for task_id in still_running:
                if task_id in tracked:
                    elapsed = (now - tracked[task_id]) / 60
                    remaining = config.background_task_timeout_minutes - elapsed
                    minutes_remaining.append(f"{task_id} ({remaining:.1f} min remaining)")

            task_list = ", ".join(minutes_remaining) if minutes_remaining else ", ".join(still_running)
            instructions.append(f"Background tasks still running: {task_list}")
            instructions.append("Wait 60 seconds, then re-run /{} to check task status again".format(SKILL_NAME))

        if instructions:
            reason = "\n\n".join(instructions)
            output = {"decision": "block", "reason": reason}
            log_hook(SKILL_NAME, hook_input, output, [])
            send_output(output)

    # No background tasks (or all completed) - clean up tracking and check for gaps
    cleanup_task_tracking(SKILL_NAME, background_tasks)

    # Collect all gaps
    gaps = []
    gaps.extend(check_specs_exist())
    gaps.extend(check_report_exists())
    gaps.extend(check_report_sections())
    gaps.extend(check_unresolved_findings())
    gaps.extend(check_cross_references())

    # Make decision based on gaps
    if gaps:
        instructions = f"Continue running /{SKILL_NAME} to address remaining gaps:\n\n"
        instructions += "\n".join(f"- {gap}" for gap in gaps)
        output = {"decision": "block", "reason": instructions}
        log_hook(SKILL_NAME, hook_input, output, gaps)
        send_output(output)
    else:
        output = {}
        log_hook(SKILL_NAME, hook_input, output, [])
        send_output(output)


if __name__ == "__main__":
    main()