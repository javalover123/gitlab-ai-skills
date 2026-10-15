#!/usr/bin/env python3
"""Checks that skill versions are bumped when skill files change.

Changed files are scoped to the MR's own changes (merge-base, or HEAD^1 in
merged-results pipelines). Versions are compared against the current target
branch tip so a version already taken there must be bumped past. Exits 2 if
the baseline cannot be read. Fails if any skill has file changes
without a corresponding version bump in SKILL.md frontmatter. A skill removed
by the MR has no version left and is reported as removed, not failed.

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


class BaselineError(Exception):
    """A git ref needed for the comparison could not be read."""


def run_git(*args):
    """Run git in the repo root and return stdout; raise BaselineError on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise BaselineError(f"git {' '.join(args)} failed: {e.stderr.strip()}") from e
    return result.stdout


def ref_exists(ref):
    try:
        run_git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        return True
    except BaselineError:
        return False


def get_baselines():
    """Return (diff_args, version_ref).

    diff_args are the `git diff --name-only` revision arguments that scope the
    changed files to the MR's own changes. version_ref is the ref whose skill
    versions the new version must exceed: the current target-branch tip where
    available, so a version already taken on the target must be bumped past.

    - Merged-results pipelines: HEAD is a merge commit, so HEAD^1 (the target
      tip) is the baseline for both. A merge-base would attribute target drift
      to the MR.
    - Detached MR pipelines: files come from the MR merge-base
      (CI_MERGE_REQUEST_DIFF_BASE_SHA); versions from origin/<default> when
      fetched, else the merge-base.
    - Local runs: three-dot diff against origin/<default>.
    """
    default_branch = os.environ.get("CI_DEFAULT_BRANCH", "main")
    target_tip = f"origin/{default_branch}"

    if os.environ.get("CI_MERGE_REQUEST_EVENT_TYPE") == "merged_result":
        base = os.environ.get("CI_MERGE_REQUEST_TARGET_BRANCH_SHA") or "HEAD^1"
        log_debug(f"Merged-results pipeline, baseline: {base}")
        return [base, "HEAD"], base

    diff_base = os.environ.get("CI_MERGE_REQUEST_DIFF_BASE_SHA")
    if diff_base:
        if ref_exists(target_tip):
            version_ref = target_tip
        else:
            version_ref = diff_base
            print(
                f"WARNING: {target_tip} not available; version collision "
                "detection against the target branch is off.",
                file=sys.stderr,
            )
        log_debug(f"Detached MR pipeline, diff base: {diff_base}, versions: {version_ref}")
        return [diff_base, "HEAD"], version_ref

    log_debug(f"Local run, baseline: {target_tip}")
    return [f"{target_tip}...HEAD"], target_tip


def get_changed_files(diff_args):
    """Get files changed per diff_args. Raises BaselineError if git fails."""
    output = run_git("diff", "--name-only", *diff_args)
    files = [f for f in output.strip().split("\n") if f]
    log_debug(f"Changed files: {files}")
    return files


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
        if len(parts) < 3:
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
        content = run_git("show", f"{ref}:{skill_md_path}")
    except BaselineError:
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


def merge_base_version(skill_name, diff_args):
    """Version at the MR's own diff baseline (differs from the target tip on collisions)."""
    return get_version_at_ref(skill_name, diff_args[0].split("...")[0])


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

    try:
        diff_args, base_ref = get_baselines()
        changed_files = get_changed_files(diff_args)
    except BaselineError as e:
        print(f"ERROR: cannot compute baseline: {e}", file=sys.stderr)
        sys.exit(2)

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

        # A skill that existed on the target and has no SKILL.md now was removed
        # (or renamed into another skill). There's no version left to bump.
        if old_version is not None and not os.path.isfile(
            os.path.join(REPO_ROOT, "skills", skill_name, "SKILL.md")
        ):
            print(f"  OK: {skill_name} — removed (no version to bump)")
            continue

        if is_version_bumped(old_version, new_version):
            print(
                f"  OK: {skill_name} — version bumped "
                f"({old_version or 'new'} → {new_version})"
            )
        else:
            has_errors = True
            changed_list = "\n".join(f"        - {f}" for f in files)
            if old_version == new_version and merge_base_version(
                skill_name, diff_args
            ) not in (None, new_version):
                print(
                    f"FAIL: {skill_name} — version {new_version} is already on "
                    f"the target branch; bump past it:\n{changed_list}"
                )
            elif old_version == new_version:
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
