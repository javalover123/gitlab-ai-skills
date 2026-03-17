#!/usr/bin/env python3
"""Checks that skill versions are bumped when skill files change.

Compares the current branch against the base branch (origin/main or
CI_MERGE_REQUEST_DIFF_BASE_SHA) and fails if any skill has file changes
without a corresponding version bump in SKILL.md frontmatter.

Generated files (.claude-plugin/) are excluded from the diff check since
they are derived from SKILL.md.

Usage:
    python3 scripts/check_version_bump.py          # Report results
    python3 scripts/check_version_bump.py --ci      # Exit 1 if version bump missing
    python3 scripts/check_version_bump.py --debug   # Enable debug logging
"""

import os
import re
import subprocess
import sys

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")

# Patterns to exclude from "changed files" — these are generated/derived
EXCLUDED_PATTERNS = [".claude-plugin/"]

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def get_base_ref():
    """Determine the base ref to diff against.

    In CI merge request pipelines, uses CI_MERGE_REQUEST_DIFF_BASE_SHA.
    Otherwise falls back to origin/main (for lefthook pre-push).
    """
    ci_base = os.environ.get("CI_MERGE_REQUEST_DIFF_BASE_SHA")
    if ci_base:
        log_debug(f"Using CI base ref: {ci_base}")
        return ci_base

    # Fallback: origin/main for local development (lefthook pre-push)
    default_branch = os.environ.get("CI_DEFAULT_BRANCH", "main")
    base_ref = f"origin/{default_branch}"
    log_debug(f"Using local base ref: {base_ref}")
    return base_ref


def get_changed_files(base_ref):
    """Get list of files changed between base_ref and HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_ref, "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        log_debug(f"Changed files: {files}")
        return files
    except subprocess.CalledProcessError as e:
        log_debug(f"git diff failed: {e.stderr}")
        return []


def get_changed_skills(changed_files):
    """Group changed files by skill, excluding generated files.

    Returns a dict of skill_name -> list of changed file paths.
    """
    skills = {}

    for filepath in changed_files:
        # Only look at files under skills/
        if not filepath.startswith("skills/"):
            continue

        parts = filepath.split("/")
        if len(parts) < 2:
            continue

        skill_name = parts[1]

        # Skip generated/derived files
        if any(pattern in filepath for pattern in EXCLUDED_PATTERNS):
            log_debug(f"Skipping generated file: {filepath}")
            continue

        skills.setdefault(skill_name, []).append(filepath)

    log_debug(f"Changed skills: {list(skills.keys())}")
    return skills


def get_version_at_ref(skill_name, ref):
    """Extract the version field from SKILL.md frontmatter at a given git ref.

    Returns the version string, or None if not found.
    """
    skill_md_path = f"skills/{skill_name}/SKILL.md"
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{skill_md_path}"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        )
        content = result.stdout
    except subprocess.CalledProcessError:
        log_debug(f"Could not read {skill_md_path} at {ref} (new skill?)")
        return None

    # Parse frontmatter
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if not line[0:1].isspace() and stripped.startswith("version:"):
            version = stripped.split(":", 1)[1].strip().strip("\"'")
            log_debug(f"Found version '{version}' for {skill_name} at {ref}")
            return version

    return None


def parse_current_version(skill_name):
    """Read the current version from the working tree SKILL.md."""
    skill_file = os.path.join(REPO_ROOT, "skills", skill_name, "SKILL.md")
    if not os.path.isfile(skill_file):
        return None

    with open(skill_file, "r") as f:
        lines = f.readlines()

    if not lines or lines[0].strip() != "---":
        return None

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if not line[0:1].isspace() and stripped.startswith("version:"):
            version = stripped.split(":", 1)[1].strip().strip("\"'")
            return version

    return None


def is_version_bumped(old_version, new_version):
    """Check if new_version is strictly greater than old_version (semver)."""
    if old_version is None:
        # New skill — any version is fine
        return True
    if new_version is None:
        return False

    semver_re = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
    old_match = semver_re.match(old_version)
    new_match = semver_re.match(new_version)

    if not old_match or not new_match:
        # Can't compare non-semver; just check they're different
        return old_version != new_version

    old_tuple = tuple(int(x) for x in old_match.groups())
    new_tuple = tuple(int(x) for x in new_match.groups())
    return new_tuple > old_tuple


def main():
    is_ci_mode = "--ci" in sys.argv

    base_ref = get_base_ref()
    changed_files = get_changed_files(base_ref)

    if not changed_files:
        print("No changed files detected.")
        sys.exit(0)

    changed_skills = get_changed_skills(changed_files)

    if not changed_skills:
        print("No skill files changed.")
        sys.exit(0)

    has_errors = False

    for skill_name, files in sorted(changed_skills.items()):
        old_version = get_version_at_ref(skill_name, base_ref)
        new_version = parse_current_version(skill_name)

        log_debug(
            f"{skill_name}: old={old_version}, new={new_version}, "
            f"changed={len(files)} file(s)"
        )

        if is_version_bumped(old_version, new_version):
            print(
                f"  OK: {skill_name} — version bumped "
                f"({old_version or 'new'} → {new_version})"
            )
        else:
            has_errors = True
            changed_list = "\n".join(f"        - {f}" for f in files)
            if old_version == new_version:
                print(
                    f"FAIL: {skill_name} — version unchanged at {old_version} "
                    f"but {len(files)} file(s) changed:\n{changed_list}"
                )
            else:
                print(
                    f"FAIL: {skill_name} — version went from {old_version} to "
                    f"{new_version} (must increase):\n{changed_list}"
                )

    if is_ci_mode and has_errors:
        print(
            "\nERROR: Some skills have file changes without a version bump. "
            "Update the 'version' field in SKILL.md frontmatter.",
            file=sys.stderr,
        )
        sys.exit(1)
    elif has_errors:
        print("\nWARNING: Some skills have file changes without a version bump.")
    else:
        print("\nAll changed skills have version bumps.")


if __name__ == "__main__":
    main()
