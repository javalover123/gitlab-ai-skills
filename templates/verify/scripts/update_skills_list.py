#!/usr/bin/env python3
"""Regenerates the Skills table in README.md from skills/*/SKILL.md frontmatter.

Usage:
    python3 scripts/update_skills_list.py          # Update README.md in place
    python3 scripts/update_skills_list.py --ci      # Verify README.md is up to date (exit 1 if not)
    python3 scripts/update_skills_list.py --debug   # Enable debug logging
"""

import os
import re
import sys

if "SKILLS_REPO_ROOT" not in os.environ:
    print("ERROR: SKILLS_REPO_ROOT environment variable is not set.", file=sys.stderr)
    sys.exit(1)
REPO_ROOT = os.environ["SKILLS_REPO_ROOT"]
README_FILE = os.path.join(REPO_ROOT, "README.md")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

# Tags for the auto-generated section in README.md
SKILLS_START_TAG = "<!-- SKILLS_START -->"
SKILLS_END_TAG = "<!-- SKILLS_END -->"

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def parse_frontmatter(skill_file):
    """Extract name and description from YAML frontmatter in a SKILL.md file.

    Expects frontmatter delimited by --- on the first line and a closing ---.
    Returns (name, description) tuple. Falls back to empty strings if not found.
    """
    log_debug(f"Parsing frontmatter from {skill_file}")
    name = ""
    description = ""

    with open(skill_file, "r") as f:
        lines = f.readlines()

    if not lines or lines[0].strip() != "---":
        log_debug("No frontmatter found (first line is not ---)")
        return name, description

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break  # End of frontmatter

        if stripped.startswith("name:"):
            name = stripped.split(":", 1)[1].strip().strip("\"'")
            log_debug(f"Found name: '{name}'")
        elif stripped.startswith("description:"):
            description = stripped.split(":", 1)[1].strip().strip("\"'")
            log_debug(f"Found description: '{description}'")

    return name, description


def generate_table():
    """Generate the skills markdown table from skills/*/SKILL.md files."""
    log_debug(f"Scanning skills directory: {SKILLS_DIR}")

    if not os.path.isdir(SKILLS_DIR):
        log_debug("Skills directory does not exist")
        return ""

    rows = []

    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_file = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        if not os.path.isfile(skill_file):
            log_debug(f"Skipping {skill_name}: no SKILL.md found")
            continue

        name, description = parse_frontmatter(skill_file)

        # Fall back to directory name if name not in frontmatter
        if not name:
            name = skill_name

        # Fall back to placeholder if no description
        if not description:
            description = "-"

        rel_path = f"skills/{skill_name}/SKILL.md"
        row = f"| [`{name}`]({rel_path}) | {description} |"
        rows.append(row)
        log_debug(f"Added row for skill: {name}")

    if not rows:
        log_debug("No skills found")
        return ""

    header = "| Skill | Description |\n| ----- | ----------- |"
    table = header + "\n" + "\n".join(rows)
    log_debug(f"Generated table:\n{table}")
    return table


def read_existing_table():
    """Read the README and extract the existing table between SKILLS_START and SKILLS_END tags."""
    log_debug(f"Reading existing table from {README_FILE}")
    with open(README_FILE, "r") as f:
        content = f.read()

    match = re.search(
        f"{re.escape(SKILLS_START_TAG)}(.*?){re.escape(SKILLS_END_TAG)}",
        content,
        re.DOTALL,
    )
    if match:
        existing = match.group(1).strip()
        log_debug(f"Existing table found:\n{existing}")
        return existing

    log_debug("No existing table found")
    return None


def update_readme(new_table):
    """Update the README file, replacing the section between tags with the new table."""
    log_debug(f"Updating README file: {README_FILE}")
    with open(README_FILE, "r") as f:
        content = f.read()

    updated = re.sub(
        f"{re.escape(SKILLS_START_TAG)}.*?{re.escape(SKILLS_END_TAG)}",
        f"{SKILLS_START_TAG}\n{new_table}\n{SKILLS_END_TAG}",
        content,
        flags=re.DOTALL,
    )

    if updated != content:
        with open(README_FILE, "w") as f:
            f.write(updated)
        log_debug("README.md updated.")
        print("README.md updated.")
    else:
        log_debug("README.md is up to date. No changes needed.")
        print("README.md is up to date. No changes needed.")


def main():
    is_ci_mode = "--ci" in sys.argv

    new_table = generate_table()

    if is_ci_mode:
        existing_table = read_existing_table()
        if existing_table is not None and existing_table.strip() == new_table.strip():
            log_debug("Tables match in CI mode. Exiting with code 0.")
            print("README.md skills table is up to date.")
            sys.exit(0)
        else:
            log_debug("Tables do not match in CI mode. Exiting with code 1.")
            print(
                "ERROR: README.md skills table is out of date. "
                "Run `python3 scripts/update_skills_list.py` to update.",
                file=sys.stderr,
            )
            if DEBUG:
                print(f"\nExpected:\n{new_table}", file=sys.stderr)
                print(f"\nGot:\n{existing_table}", file=sys.stderr)
            sys.exit(1)
    else:
        update_readme(new_table)


if __name__ == "__main__":
    main()
