#!/usr/bin/env python3
"""Checks that distributed SKILL.md files are compatible with the opencode format.

Scans all skills distributed to .opencode/skills/* directories and validates
their SKILL.md frontmatter against the opencode Skills format. Fails on missing
required fields or invalid version format, warns on fields opencode does not
recognize.

Usage:
    python3 scripts/validate-opencode-distribution.py          # Report compatibility status
    python3 scripts/validate-opencode-distribution.py --ci      # Exit 1 on hard failures
    python3 scripts/validate-opencode-distribution.py --debug   # Enable debug logging
"""

import glob
import os
import re
import sys

from lib.frontmatter import parse_frontmatter

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
OPENCODE_DIR = os.path.join(REPO_ROOT, ".opencode")

# Fields recognized by the opencode SKILL.md format
OPENCODE_KNOWN_FIELDS = {"name", "description", "version", "license", "compatibility", "metadata"}

# Required fields for opencode format
OPENCODE_REQUIRED_FIELDS = ["name", "description", "version"]

# Semver pattern (major.minor.patch)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def check_skill(skill_name, skill_file):
    """Check a single skill for opencode compatibility.

    Returns (errors, warnings) where each is a list of strings.
    Errors are hard failures; warnings are informational.
    """
    errors = []
    warnings = []

    fields = parse_frontmatter(skill_file)
    log_debug(f"Found fields: {set(fields.keys())}")

    if not fields:
        errors.append("No YAML frontmatter found")
        return errors, warnings

    # Hard failure: required fields must be present and non-empty
    missing = [f for f in OPENCODE_REQUIRED_FIELDS if f not in fields or not fields[f]]
    if missing:
        errors.append(f"Missing required fields: {', '.join(missing)}")

    # Hard failure: version must be valid semver if present
    if "version" in fields and fields["version"]:
        if not SEMVER_RE.match(fields["version"]):
            errors.append(
                f"version '{fields['version']}' is not valid semver (expected X.Y.Z)"
            )

    # Informational: fields not recognized by opencode (silently ignored)
    unknown_fields = set(fields.keys()) - OPENCODE_KNOWN_FIELDS
    if unknown_fields:
        warnings.append(
            f"Unknown fields (ignored by opencode): {', '.join(sorted(unknown_fields))}"
        )

    return errors, warnings


def find_skill_files():
    """Find all SKILL.md files distributed to .opencode/skills/* directories."""
    pattern = os.path.join(OPENCODE_DIR, "skills", "*", "SKILL.md")
    return sorted(glob.glob(pattern))


def main():
    is_ci_mode = "--ci" in sys.argv

    log_debug(f"Scanning .opencode directory: {OPENCODE_DIR}")

    if not os.path.isdir(OPENCODE_DIR):
        print("No .opencode directory found.")
        sys.exit(0)

    skill_files = find_skill_files()

    if not skill_files:
        print("No distributed skills found in .opencode/skills/*/SKILL.md")
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

        if not errors:
            print("  \u2713 all required fields present")
        for err in errors:
            print(f"  \u2717 {err}")
            total_errors += 1
        for warn in warnings:
            print(f"  \u26a0 {warn}")
            total_warnings += 1
        if not errors and not warnings:
            print("  \u2713 fully compatible with opencode format")

        print()

    summary_parts = [f"{total} skill(s) checked"]
    summary_parts.append(f"{total_errors} error(s)")
    if total_warnings:
        summary_parts.append(f"{total_warnings} warning(s)")
    print(f"Summary: {', '.join(summary_parts)}")

    if is_ci_mode and total_errors > 0:
        print(
            "\nERROR: Some distributed skills have opencode compatibility issues. "
            "See output above for details.",
            file=sys.stderr,
        )
        sys.exit(1)
    elif total_errors > 0:
        print("\nWARNING: Some distributed skills have opencode compatibility issues.")
    else:
        print("\nAll distributed skills are compatible with opencode format.")


if __name__ == "__main__":
    main()
