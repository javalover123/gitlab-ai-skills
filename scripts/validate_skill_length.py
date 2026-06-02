#!/usr/bin/env python3
"""Reports SKILL.md files that exceed the length convention.

The repo convention (established in !9, reinforced in !40) is to keep each
SKILL.md lean: aim for under 100 lines, and treat 150 as a hard ceiling — push
detail into sibling reference files (`references/*.md`) instead. A long SKILL.md
burns agent context on every load.

This check is intentionally WARN-ONLY: five existing skills currently exceed 150
lines, so a hard gate would block unrelated MRs until those are trimmed. It
prints offenders so they are visible in CI logs and during pre-push, without
failing the build. Promote to a hard gate (exit 1 over MAX) once the existing
long skills are split.

Usage:
    python3 scripts/validate_skill_length.py          # report
    python3 scripts/validate_skill_length.py --ci      # report (still exit 0)
    python3 scripts/validate_skill_length.py --debug   # debug logging
"""

import os
import sys

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

TARGET_LINES = 100  # aim under this
MAX_LINES = 150  # hard ceiling per convention

DEBUG = "--debug" in sys.argv


def log_debug(message):
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def count_lines(path):
    with open(path, "r") as f:
        return sum(1 for _ in f)


def main():
    if not os.path.isdir(SKILLS_DIR):
        print("No skills directory found.")
        sys.exit(0)

    over_max = []
    over_target = []

    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_file = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        if not os.path.isfile(skill_file):
            continue
        n = count_lines(skill_file)
        rel = os.path.relpath(skill_file, REPO_ROOT)
        log_debug(f"{rel}: {n} lines")
        if n > MAX_LINES:
            over_max.append((rel, n))
        elif n > TARGET_LINES:
            over_target.append((rel, n))

    if over_max:
        print(f"Over hard ceiling ({MAX_LINES} lines) — split into references/:")
        for rel, n in over_max:
            print(f"  WARN: {rel} — {n} lines")
    if over_target:
        print(f"Over target ({TARGET_LINES} lines) — consider trimming:")
        for rel, n in over_target:
            print(f"  note: {rel} — {n} lines")
    if not over_max and not over_target:
        print(f"All SKILL.md files are within {TARGET_LINES} lines.")

    # Warn-only: never fail the build. See module docstring.
    sys.exit(0)


if __name__ == "__main__":
    main()
