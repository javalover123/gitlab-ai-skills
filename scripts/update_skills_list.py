#!/usr/bin/env python3
"""Regenerates the Skills table in README.md from skills/*/SKILL.md frontmatter.

Skills are grouped by their ``category`` frontmatter field. Skills without a
category appear under a final "Other" section. Within each category, skills
are sorted alphabetically by name.

Usage:
    python3 scripts/update_skills_list.py          # Update README.md in place
    python3 scripts/update_skills_list.py --ci      # Verify README.md is up to date (exit 1 if not)
    python3 scripts/update_skills_list.py --debug   # Enable debug logging
"""

import os
import re
import sys
from collections import defaultdict

from lib.frontmatter import parse_frontmatter as _parse_frontmatter

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
README_FILE = os.path.join(REPO_ROOT, "README.md")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

# Tags for the auto-generated section in README.md
SKILLS_START_TAG = "<!-- SKILLS_START -->"
SKILLS_END_TAG = "<!-- SKILLS_END -->"

# Fallback category for skills without a category field
UNCATEGORIZED = "Other"

# Preferred display order for known categories (unknown ones sort alphabetically after)
CATEGORY_ORDER = [
    "Development Workflow",
    "Database",
    "Testing",
    "Shell & Environment",
    "Agent Tooling",
]

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def parse_frontmatter(skill_file):
    """Extract name, description, and category from YAML frontmatter in a SKILL.md file.

    Returns (name, description, category) tuple. Falls back to empty strings if not found.
    """
    fields = _parse_frontmatter(skill_file)
    name = fields.get("name", "")
    description = fields.get("description", "")
    category = fields.get("category", "")
    log_debug(
        f"Parsed {skill_file}: name='{name}', description='{description}', category='{category}'"
    )
    return name, description, category


def sort_key(category):
    """Return a sort key that puts known categories first, then alphabetical."""
    try:
        return (0, CATEGORY_ORDER.index(category))
    except ValueError:
        return (1, category)


def generate_sections():
    """Generate grouped markdown sections from skills/*/SKILL.md files."""
    log_debug(f"Scanning skills directory: {SKILLS_DIR}")

    if not os.path.isdir(SKILLS_DIR):
        log_debug("Skills directory does not exist")
        return ""

    # Collect skills grouped by category
    by_category = defaultdict(list)

    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_file = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        if not os.path.isfile(skill_file):
            log_debug(f"Skipping {skill_name}: no SKILL.md found")
            continue

        name, description, category = parse_frontmatter(skill_file)

        if not name:
            name = skill_name
        if not description:
            description = "-"
        if not category:
            category = UNCATEGORIZED

        rel_path = f"skills/{skill_name}/SKILL.md"
        by_category[category].append((name, description, rel_path))
        log_debug(f"Added skill '{name}' to category '{category}'")

    if not by_category:
        log_debug("No skills found")
        return ""

    # Sort categories by preferred order
    sorted_categories = sorted(by_category.keys(), key=sort_key)

    parts = []

    for category in sorted_categories:
        skills = by_category[category]
        entries = [
            f"#### {name}\n\n{description} → [`SKILL.md`]({rel_path})"
            for name, description, rel_path in skills
        ]
        parts.append(f"### {category}\n\n" + "\n\n".join(entries))
        log_debug(
            f"Generated section for category '{category}' with {len(skills)} skill(s)"
        )

    result = "\n\n".join(parts)
    log_debug(f"Generated sections:\n{result}")
    return result


def read_existing_table():
    """Read the README and extract the existing content between SKILLS_START and SKILLS_END tags."""
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
        log_debug(f"Existing content found:\n{existing}")
        return existing

    log_debug("No existing content found")
    return None


def update_readme(new_content):
    """Update the README file, replacing the section between tags with the new content."""
    log_debug(f"Updating README file: {README_FILE}")
    with open(README_FILE, "r") as f:
        content = f.read()

    updated = re.sub(
        f"{re.escape(SKILLS_START_TAG)}.*?{re.escape(SKILLS_END_TAG)}",
        f"{SKILLS_START_TAG}\n{new_content}\n{SKILLS_END_TAG}",
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

    new_content = generate_sections()

    if is_ci_mode:
        existing_content = read_existing_table()
        if (
            existing_content is not None
            and existing_content.strip() == new_content.strip()
        ):
            log_debug("Content matches in CI mode. Exiting with code 0.")
            print("README.md skills table is up to date.")
            sys.exit(0)
        else:
            log_debug("Content does not match in CI mode. Exiting with code 1.")
            print(
                "ERROR: README.md skills table is out of date. "
                "Run `python3 scripts/update_skills_list.py` to update.",
                file=sys.stderr,
            )
            if DEBUG:
                print(f"\nExpected:\n{new_content}", file=sys.stderr)
                print(f"\nGot:\n{existing_content}", file=sys.stderr)
            sys.exit(1)
    else:
        update_readme(new_content)


if __name__ == "__main__":
    main()
