#!/usr/bin/env python3
"""Checks that skills distributed to .agents/skills/ are spec-compatible.

The ".agents/skills/" directory is the cross-tool discovery location described
by the Agent Skills spec (https://agentskills.io). This scans every
.agents/skills/*/SKILL.md and validates its frontmatter against the spec:
required fields (name, description), the name format and length, and the
description length. Fields the spec does not define are reported as
informational (they are silently ignored by consumers).

Usage:
    python3 scripts/validate-agents-distribution.py          # Report compatibility status
    python3 scripts/validate-agents-distribution.py --ci      # Exit 1 on hard failures
    python3 scripts/validate-agents-distribution.py --debug   # Enable debug logging
"""

import glob
import os
import re
import sys

from lib.frontmatter import parse_frontmatter

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
AGENTS_DIR = os.path.join(REPO_ROOT, ".agents")

# Fields defined by the Agent Skills spec. Anything else is ignored by
# consumers, so it is reported informationally rather than as an error.
AGENTS_KNOWN_FIELDS = {
    "name",
    "description",
    "version",
    "license",
    "compatibility",
    "metadata",
    "disable-model-invocation",
}

# Required by the spec.
AGENTS_REQUIRED_FIELDS = ["name", "description"]

# name: lowercase a-z, 0-9, hyphens; no leading/trailing/consecutive hyphens.
AGENTS_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
AGENTS_NAME_MAX_LEN = 64
AGENTS_DESCRIPTION_MAX_LEN = 1024

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def check_skill(skill_name, skill_file):
    """Check a single skill for Agent Skills spec compatibility.

    Returns (errors, warnings) where each is a list of strings.
    Errors are hard failures; warnings are informational.
    """
    errors = []
    warnings = []

    fields = parse_frontmatter(skill_file)
    log_debug(f"[{skill_name}] Found fields: {set(fields.keys())}")

    if not fields:
        errors.append("No YAML frontmatter found")
        return errors, warnings

    # Hard failure: required fields must be present and non-empty
    missing = [f for f in AGENTS_REQUIRED_FIELDS if f not in fields or not fields[f]]
    if missing:
        errors.append(f"Missing required fields: {', '.join(missing)}")

    # Hard failure: name must match the spec format and length
    name = fields.get("name", "")
    if name:
        if len(name) > AGENTS_NAME_MAX_LEN:
            errors.append(f"name '{name}' exceeds {AGENTS_NAME_MAX_LEN} characters ({len(name)})")
        if not AGENTS_NAME_RE.match(name):
            errors.append(
                f"name '{name}' does not match spec format "
                "(lowercase a-z, 0-9, hyphens; no leading/trailing/consecutive hyphens)"
            )

    # Informational: description over the spec limit
    description = fields.get("description", "")
    if description and len(description) > AGENTS_DESCRIPTION_MAX_LEN:
        warnings.append(
            f"description exceeds {AGENTS_DESCRIPTION_MAX_LEN} characters ({len(description)})"
        )

    # Informational: fields not defined by the spec (silently ignored)
    unknown_fields = set(fields.keys()) - AGENTS_KNOWN_FIELDS
    if unknown_fields:
        warnings.append(
            f"Fields not defined by the spec (ignored by consumers): "
            f"{', '.join(sorted(unknown_fields))}"
        )

    return errors, warnings


def find_skill_files():
    """Find all SKILL.md files distributed to .agents/skills/* directories."""
    pattern = os.path.join(AGENTS_DIR, "skills", "*", "SKILL.md")
    return sorted(glob.glob(pattern))


def main():
    is_ci_mode = "--ci" in sys.argv

    log_debug(f"Scanning .agents directory: {AGENTS_DIR}")

    if not os.path.isdir(AGENTS_DIR):
        print("No .agents directory found.")
        sys.exit(0)

    skill_files = find_skill_files()

    if not skill_files:
        print("No distributed skills found in .agents/skills/*/SKILL.md")
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
            print("  ✓ all required fields present")
        for err in errors:
            print(f"  ✗ {err}")
            total_errors += 1
        for warn in warnings:
            print(f"  ⚠ {warn}")
            total_warnings += 1
        if not errors and not warnings:
            print("  ✓ fully compatible with the Agent Skills spec")

        print()

    summary_parts = [f"{total} skill(s) checked"]
    summary_parts.append(f"{total_errors} error(s)")
    if total_warnings:
        summary_parts.append(f"{total_warnings} warning(s)")
    print(f"Summary: {', '.join(summary_parts)}")

    if is_ci_mode and total_errors > 0:
        print(
            "\nERROR: Some distributed skills are not compatible with the "
            "Agent Skills spec. See output above for details.",
            file=sys.stderr,
        )
        sys.exit(1)
    elif total_errors > 0:
        print("\nWARNING: Some distributed skills are not compatible with the Agent Skills spec.")
    else:
        print("\nAll distributed skills are compatible with the Agent Skills spec.")


if __name__ == "__main__":
    main()
