#!/usr/bin/env python3
"""Checks that distributed SKILL.md files are compatible with the ClaudeCode format.

Scans all skills distributed to .claude-plugin/**/skills/* directories and
validates their SKILL.md frontmatter against the ClaudeCode plugin Skills format.
Fails on hard incompatibilities (missing description), warns on fields that
ClaudeCode does not recognize (silently ignored).

Usage:
    python3 scripts/validate-claudecode-distribution.py          # Report compatibility status
    python3 scripts/validate-claudecode-distribution.py --ci      # Exit 1 on hard failures
    python3 scripts/validate-claudecode-distribution.py --debug   # Enable debug logging
"""

import glob
import os
import sys

from lib.frontmatter import parse_frontmatter

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
CLAUDE_PLUGIN_DIR = os.path.join(REPO_ROOT, ".claude-plugin")

# Fields recognized by the ClaudeCode SKILL.md format
# See: https://code.claude.com/docs/en/plugins
CLAUDECODE_KNOWN_FIELDS = {"description", "disable-model-invocation", "name", "version"}

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
    """Check a single skill for ClaudeCode compatibility.

    Returns (errors, warnings) where each is a list of strings.
    Errors are hard failures; warnings are informational.
    """
    errors = []
    warnings = []

    fields = parse_frontmatter_fields(skill_file)

    if not fields:
        errors.append("No YAML frontmatter found")
        return errors, warnings

    # Hard failure: description is required by ClaudeCode
    if "description" not in fields:
        errors.append("Missing 'description' field (required by ClaudeCode)")

    # Informational: fields not recognized by ClaudeCode (silently ignored)
    unknown_fields = fields - CLAUDECODE_KNOWN_FIELDS
    if unknown_fields:
        warnings.append(
            f"Unknown fields (ignored by ClaudeCode): {', '.join(sorted(unknown_fields))}"
        )

    return errors, warnings


def find_skill_files():
    """Find all SKILL.md files distributed to .claude-plugin/**/skills/* directories."""
    pattern = os.path.join(CLAUDE_PLUGIN_DIR, "**", "skills", "*", "SKILL.md")
    return sorted(glob.glob(pattern, recursive=True))


def main():
    is_ci_mode = "--ci" in sys.argv

    log_debug(f"Scanning .claude-plugin directory: {CLAUDE_PLUGIN_DIR}")

    if not os.path.isdir(CLAUDE_PLUGIN_DIR):
        print("No .claude-plugin directory found.")
        sys.exit(0)

    skill_files = find_skill_files()

    if not skill_files:
        print("No distributed skills found in .claude-plugin/**/skills/*/SKILL.md")
        sys.exit(0)

    total = 0
    total_errors = 0
    total_warnings = 0

    for skill_file in skill_files:
        skill_name = os.path.basename(os.path.dirname(skill_file))
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
            print("  \u2713 fully compatible with ClaudeCode format")

        print()

    summary_parts = [f"{total} skill(s) checked"]
    summary_parts.append(f"{total_errors} error(s)")
    if total_warnings:
        summary_parts.append(f"{total_warnings} warning(s)")
    print(f"Summary: {', '.join(summary_parts)}")

    if is_ci_mode and total_errors > 0:
        print(
            "\nERROR: Some distributed skills have ClaudeCode compatibility issues. "
            "See output above for details.",
            file=sys.stderr,
        )
        sys.exit(1)
    elif total_errors > 0:
        print("\nWARNING: Some distributed skills have ClaudeCode compatibility issues.")
    else:
        print("\nAll distributed skills are compatible with ClaudeCode format.")


if __name__ == "__main__":
    main()
