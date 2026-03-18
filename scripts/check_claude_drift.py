#!/usr/bin/env python3
"""Checks that skills/*/SKILL.md files are compatible with the claude.ai plugin format.

Detects drift between our SKILL.md format (opencode) and the claude.ai plugin
Skills format. Fails on hard incompatibilities (missing description), warns on
fields that are opencode-only (silently ignored by claude.ai).

Usage:
    python3 scripts/check_claude_drift.py          # Report compatibility status
    python3 scripts/check_claude_drift.py --ci      # Exit 1 on hard failures
    python3 scripts/check_claude_drift.py --debug   # Enable debug logging
"""

import os
import sys

from lib.frontmatter import parse_frontmatter

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

# Fields recognized by claude.ai SKILL.md format
# See: https://code.claude.com/docs/en/plugins
CLAUDE_KNOWN_FIELDS = {"description", "disable-model-invocation", "name", "version"}

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def parse_frontmatter_fields(skill_file):
    """Extract all top-level field names from YAML frontmatter.

    Returns a set of field names. Returns empty set if no frontmatter found.
    """
    fields = parse_frontmatter(skill_file)
    log_debug(f"Found fields: {set(fields.keys())}")
    return set(fields.keys())


def check_skill(skill_name, skill_file):
    """Check a single skill for claude.ai compatibility.

    Returns (errors, warnings) where each is a list of strings.
    Errors are hard failures; warnings are informational.
    """
    errors = []
    warnings = []

    fields = parse_frontmatter_fields(skill_file)

    if not fields:
        errors.append("No YAML frontmatter found")
        return errors, warnings

    # Hard failure: description is required by both formats
    if "description" not in fields:
        errors.append(
            "Missing 'description' field (required by both opencode and claude.ai)"
        )

    # Informational: fields we use that claude.ai ignores
    opencode_only = fields - CLAUDE_KNOWN_FIELDS
    if opencode_only:
        warnings.append(
            f"opencode-only fields (ignored by claude.ai): {', '.join(sorted(opencode_only))}"
        )

    # Informational: claude.ai-specific fields present
    claude_specific = {"disable-model-invocation"} & fields
    if claude_specific:
        warnings.append(
            f"claude.ai-specific fields present: {', '.join(sorted(claude_specific))}"
        )

    return errors, warnings


def main():
    is_ci_mode = "--ci" in sys.argv

    log_debug(f"Scanning skills directory: {SKILLS_DIR}")

    if not os.path.isdir(SKILLS_DIR):
        print("No skills directory found.")
        sys.exit(0)

    total = 0
    total_errors = 0
    total_warnings = 0

    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_file = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        if not os.path.isfile(skill_file):
            log_debug(f"Skipping {skill_name}: no SKILL.md found")
            continue

        total += 1
        rel_path = os.path.relpath(skill_file, REPO_ROOT)
        errors, warnings = check_skill(skill_name, skill_file)

        print(f"{rel_path}")

        if "description" in parse_frontmatter_fields(skill_file):
            print("  \u2713 description present")
        for err in errors:
            print(f"  \u2717 {err}")
            total_errors += 1
        for warn in warnings:
            print(f"  \u26a0 {warn}")
            total_warnings += 1
        if not errors and not warnings:
            print("  \u2713 fully compatible with claude.ai format")

        print()

    summary_parts = [f"{total} skill(s) checked"]
    summary_parts.append(f"{total_errors} error(s)")
    if total_warnings:
        summary_parts.append(f"{total_warnings} warning(s)")
    print(f"Summary: {', '.join(summary_parts)}")

    if is_ci_mode and total_errors > 0:
        print(
            "\nERROR: Some skills have claude.ai compatibility issues. "
            "See output above for details.",
            file=sys.stderr,
        )
        sys.exit(1)
    elif total_errors > 0:
        print("\nWARNING: Some skills have claude.ai compatibility issues.")
    else:
        print("\nAll skills are compatible with claude.ai format.")


if __name__ == "__main__":
    main()
