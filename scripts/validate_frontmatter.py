#!/usr/bin/env python3
"""Validates that all skills/*/SKILL.md files have required YAML frontmatter fields.

Usage:
    python3 scripts/validate_frontmatter.py          # Report validation results
    python3 scripts/validate_frontmatter.py --ci      # Exit 1 if any skill fails validation
    python3 scripts/validate_frontmatter.py --debug   # Enable debug logging
"""

import os
import re
import sys

try:
    import yaml  # PyYAML — strict YAML validation

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from lib.frontmatter import parse_frontmatter

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

# Required frontmatter fields
REQUIRED_FIELDS = ["name", "description", "version", "license"]

# Semver pattern (major.minor.patch, no pre-release/build metadata for simplicity)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Skill names are kebab-case: lowercase alphanumerics joined by single hyphens.
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def extract_raw_frontmatter(skill_file):
    """Return the raw YAML text between the ``---`` delimiters, or *None*."""
    with open(skill_file, "r") as f:
        content = f.read()
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[1]


def strict_yaml_check(skill_file):
    """Parse the frontmatter with ``yaml.safe_load`` and return an error string on failure.

    This mirrors what downstream consumers (pi.dev, Duo CLI) do when loading
    skills — if ``yaml.safe_load`` rejects the frontmatter, the skill is
    effectively broken for agents even though the lenient ``parse_frontmatter``
    accepts it.

    Returns *None* when the frontmatter is valid YAML (or when no frontmatter is
    found — other checks already cover that case).
    """
    raw = extract_raw_frontmatter(skill_file)
    if raw is None:
        return None
    try:
        yaml.safe_load(raw)
        return None
    except yaml.YAMLError as exc:
        # Condense the error to the first line for readability.
        msg = str(exc).split("\n")[0]
        return f"frontmatter is not valid YAML: {msg}"


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
    yaml_warned = False

    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_file = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        if not os.path.isfile(skill_file):
            log_debug(f"Skipping {skill_name}: no SKILL.md found")
            continue

        fields = parse_frontmatter(skill_file)
        missing = [f for f in REQUIRED_FIELDS if f not in fields or not fields[f]]
        format_errors = []

        # Strict YAML validation — catches frontmatter that the lenient
        # parse_frontmatter accepts but real YAML parsers (used by pi.dev,
        # Duo CLI) reject. See gitlab-org/gitlab!241268 for the motivating
        # bug: an unquoted description containing "Triggers: …" broke
        # downstream consumers.
        if HAS_YAML:
            yaml_err = strict_yaml_check(skill_file)
            if yaml_err:
                format_errors.append(yaml_err)
        elif not yaml_warned:
            log_debug(
                "PyYAML not installed — skipping strict YAML validation. "
                "Install with: pip install PyYAML"
            )
            yaml_warned = True

        # Validate version format if present
        if "version" in fields and fields["version"]:
            if not SEMVER_RE.match(fields["version"]):
                format_errors.append(
                    f"version '{fields['version']}' is not valid semver (expected X.Y.Z)"
                )

        # Validate name: kebab-case and matching the directory name.
        # Rationale: reviewers repeatedly asked for this convention (see
        # !9 commit-messages, !23 gitlab-clickhouse/gitlab-psql). Encoding it
        # as a check stops it recurring. All 15 existing skills already pass.
        name = fields.get("name", "")
        if name:
            if not KEBAB_RE.match(name):
                format_errors.append(
                    f"name '{name}' is not kebab-case (lowercase, hyphen-separated)"
                )
            if name != skill_name:
                format_errors.append(
                    f"name '{name}' does not match directory name '{skill_name}'"
                )

        if missing or format_errors:
            has_errors = True

        results.append((skill_name, skill_file, missing, format_errors))
        log_debug(
            f"Validated {skill_name}: missing={missing}, format_errors={format_errors}"
        )

    return results, has_errors


def main():
    is_ci_mode = "--ci" in sys.argv

    results, has_errors = validate_skills()

    if not results:
        print("No skills found.")
        sys.exit(0)

    for skill_name, skill_file, missing, format_errors in results:
        rel_path = os.path.relpath(skill_file, REPO_ROOT)
        if missing:
            print(f"FAIL: {rel_path} — missing required fields: {', '.join(missing)}")
        if format_errors:
            for err in format_errors:
                print(f"FAIL: {rel_path} — {err}")
        if not missing and not format_errors:
            print(f"  OK: {rel_path}")

    total = len(results)
    failed = sum(1 for _, _, m, f in results if m or f)
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
