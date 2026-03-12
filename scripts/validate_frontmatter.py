#!/usr/bin/env python3
"""Validates that all skills/*/SKILL.md files have required YAML frontmatter fields.

Usage:
    python3 scripts/validate_frontmatter.py          # Report validation results
    python3 scripts/validate_frontmatter.py --ci      # Exit 1 if any skill fails validation
    python3 scripts/validate_frontmatter.py --debug   # Enable debug logging
"""

import os
import sys

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

# Required frontmatter fields
REQUIRED_FIELDS = ["name", "description", "license", "compatibility"]

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def parse_frontmatter(skill_file):
    """Extract all top-level key-value pairs from YAML frontmatter.

    Returns a dict of field_name -> value (as string). Only handles simple
    top-level keys (not nested YAML). Returns empty dict if no frontmatter found.
    """
    log_debug(f"Parsing frontmatter from {skill_file}")
    fields = {}

    with open(skill_file, "r") as f:
        lines = f.readlines()

    if not lines or lines[0].strip() != "---":
        log_debug("No frontmatter found (first line is not ---)")
        return fields

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break  # End of frontmatter

        # Only match top-level keys (lines that don't start with whitespace)
        if not line[0].isspace() and ":" in stripped:
            key = stripped.split(":", 1)[0].strip()
            value = stripped.split(":", 1)[1].strip().strip("\"'")
            fields[key] = value
            log_debug(f"Found field: '{key}' = '{value}'")

    return fields


def validate_skills():
    """Validate all skills and return (results, has_errors).

    Returns a list of (skill_name, skill_file, missing_fields) tuples
    and a boolean indicating if any errors were found.
    """
    log_debug(f"Scanning skills directory: {SKILLS_DIR}")

    if not os.path.isdir(SKILLS_DIR):
        log_debug("Skills directory does not exist")
        return [], False

    results = []
    has_errors = False

    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_file = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        if not os.path.isfile(skill_file):
            log_debug(f"Skipping {skill_name}: no SKILL.md found")
            continue

        fields = parse_frontmatter(skill_file)
        missing = [f for f in REQUIRED_FIELDS if f not in fields or not fields[f]]

        if missing:
            has_errors = True

        results.append((skill_name, skill_file, missing))
        log_debug(f"Validated {skill_name}: missing={missing}")

    return results, has_errors


def main():
    is_ci_mode = "--ci" in sys.argv

    results, has_errors = validate_skills()

    if not results:
        print("No skills found.")
        sys.exit(0)

    for skill_name, skill_file, missing in results:
        rel_path = os.path.relpath(skill_file, REPO_ROOT)
        if missing:
            print(f"FAIL: {rel_path} — missing required fields: {', '.join(missing)}")
        else:
            print(f"  OK: {rel_path}")

    total = len(results)
    failed = sum(1 for _, _, m in results if m)
    passed = total - failed
    print(f"\n{total} skills checked: {passed} passed, {failed} failed.")

    if is_ci_mode and has_errors:
        print(
            "\nERROR: Some skills have missing frontmatter fields. "
            "See output above for details.",
            file=sys.stderr,
        )
        sys.exit(1)
    elif has_errors:
        print("\nWARNING: Some skills have missing frontmatter fields.")
    else:
        print("\nAll skills have valid frontmatter.")


if __name__ == "__main__":
    main()
