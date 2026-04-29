#!/usr/bin/env python3
"""Checks that skills are compatible with the pi package format.

Validates the root package.json pi manifest and checks all skills under
skills/*/SKILL.md against pi's Agent Skills spec requirements (name format,
description presence, character limits).

Usage:
    python3 scripts/validate-pi-distribution.py          # Report compatibility status
    python3 scripts/validate-pi-distribution.py --ci      # Exit 1 on hard failures
    python3 scripts/validate-pi-distribution.py --debug   # Enable debug logging
"""

import glob
import json
import os
import re
import sys

from lib.frontmatter import parse_frontmatter

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
PACKAGE_JSON = os.path.join(REPO_ROOT, "package.json")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

# Pi name validation: lowercase letters, numbers, hyphens only.
# No leading/trailing hyphens, no consecutive hyphens.
PI_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PI_NAME_MAX_LEN = 64
PI_DESCRIPTION_MAX_LEN = 1024

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def check_package_json():
    """Validate the root package.json has a pi manifest.

    Returns a list of error strings. Empty list means valid.
    """
    errors = []

    if not os.path.isfile(PACKAGE_JSON):
        errors.append("No root package.json found")
        return errors

    with open(PACKAGE_JSON) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in package.json: {e}")
            return errors

    if "pi" not in data:
        errors.append("package.json missing 'pi' manifest section")
    elif "skills" not in data.get("pi", {}):
        errors.append("package.json 'pi' section missing 'skills' array")
    else:
        skills = data["pi"]["skills"]
        if not isinstance(skills, list) or not skills:
            errors.append("package.json 'pi.skills' must be a non-empty array")
        elif "./skills" not in skills:
            errors.append("package.json 'pi.skills' does not include './skills'")

    keywords = data.get("keywords", [])
    if "pi-package" not in keywords:
        errors.append("package.json missing 'pi-package' keyword")

    return errors


def check_skill(skill_name, skill_file):
    """Check a single skill for pi compatibility.

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

    # Check name field
    name = fields.get("name", "")
    if not name:
        errors.append("Missing required 'name' field")
    else:
        if len(name) > PI_NAME_MAX_LEN:
            errors.append(f"name '{name}' exceeds {PI_NAME_MAX_LEN} characters ({len(name)})")
        if not PI_NAME_RE.match(name):
            errors.append(
                f"name '{name}' does not match pi format "
                "(lowercase a-z, 0-9, hyphens; no leading/trailing/consecutive hyphens)"
            )
        if name != skill_name:
            errors.append(f"name '{name}' does not match directory name '{skill_name}'")

    # Check description field (pi won't load skills without it)
    description = fields.get("description", "")
    if not description:
        errors.append("Missing required 'description' field (pi won't load skills without it)")
    elif len(description) > PI_DESCRIPTION_MAX_LEN:
        warnings.append(
            f"description exceeds {PI_DESCRIPTION_MAX_LEN} characters "
            f"({len(description)}); pi may warn"
        )

    return errors, warnings


def find_skill_files():
    """Find all SKILL.md files under skills/*/."""
    pattern = os.path.join(SKILLS_DIR, "*", "SKILL.md")
    return sorted(glob.glob(pattern))


def main():
    is_ci_mode = "--ci" in sys.argv

    # Validate package.json manifest
    print("Checking package.json pi manifest...")
    manifest_errors = check_package_json()
    if manifest_errors:
        for err in manifest_errors:
            print(f"  ✗ {err}")
    else:
        print("  ✓ package.json has valid pi manifest")
    print()

    # Validate individual skills
    skill_files = find_skill_files()

    if not skill_files:
        print("No skills found in skills/*/SKILL.md")
        sys.exit(0)

    total = 0
    total_errors = len(manifest_errors)
    total_warnings = 0

    for skill_file in skill_files:
        skill_name = os.path.basename(os.path.dirname(skill_file))
        total += 1
        rel_path = os.path.relpath(skill_file, REPO_ROOT)
        errors, warnings = check_skill(skill_name, skill_file)

        print(f"{rel_path}")

        if not errors and not warnings:
            print("  ✓ fully compatible with pi format")
        for err in errors:
            print(f"  ✗ {err}")
            total_errors += 1
        for warn in warnings:
            print(f"  ⚠ {warn}")
            total_warnings += 1

        print()

    summary_parts = [f"{total} skill(s) checked"]
    summary_parts.append(f"{total_errors} error(s)")
    if total_warnings:
        summary_parts.append(f"{total_warnings} warning(s)")
    print(f"Summary: {', '.join(summary_parts)}")

    if is_ci_mode and total_errors > 0:
        print(
            "\nERROR: Some skills have pi compatibility issues. "
            "See output above for details.",
            file=sys.stderr,
        )
        sys.exit(1)
    elif total_errors > 0:
        print("\nWARNING: Some skills have pi compatibility issues.")
    else:
        print("\nAll skills are compatible with pi format.")


if __name__ == "__main__":
    main()
