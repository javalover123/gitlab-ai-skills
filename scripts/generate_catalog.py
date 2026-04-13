#!/usr/bin/env python3
"""Generates catalog.json from skills/*/SKILL.md frontmatter.

Usage:
    python3 scripts/generate_catalog.py          # Generate/update catalog.json
    python3 scripts/generate_catalog.py --ci      # Verify catalog.json is up to date (exit 1 if not)
    python3 scripts/generate_catalog.py --debug   # Enable debug logging
"""

import json
import os
import sys

from lib.frontmatter import parse_frontmatter

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
CATALOG_FILE = os.path.join(REPO_ROOT, "catalog.json")

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def generate_catalog():
    """Generate the catalog data structure from skill frontmatter."""
    log_debug(f"Scanning skills directory: {SKILLS_DIR}")

    skills = []

    if not os.path.isdir(SKILLS_DIR):
        log_debug("Skills directory does not exist")
        return {"skills": skills}

    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_file = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        if not os.path.isfile(skill_file):
            log_debug(f"Skipping {skill_name}: no SKILL.md found")
            continue

        fields = parse_frontmatter(skill_file)

        skill_entry = {
            "name": fields.get("name", skill_name),
            "description": fields.get("description", ""),
            "category": fields.get("category", ""),
            "license": fields.get("license", ""),
            "compatibility": fields.get("compatibility", ""),
            "path": f"skills/{skill_name}/SKILL.md",
        }
        skills.append(skill_entry)
        log_debug(f"Added skill: {skill_entry['name']}")

    return {"skills": skills}


def main():
    is_ci_mode = "--ci" in sys.argv

    catalog = generate_catalog()
    new_content = json.dumps(catalog, indent=2) + "\n"

    if is_ci_mode:
        if os.path.isfile(CATALOG_FILE):
            with open(CATALOG_FILE, "r") as f:
                existing_content = f.read()
        else:
            existing_content = ""

        if existing_content == new_content:
            log_debug("catalog.json is up to date.")
            print("catalog.json is up to date.")
            sys.exit(0)
        else:
            log_debug("catalog.json is out of date.")
            print(
                "ERROR: catalog.json is out of date. "
                "Run `python3 scripts/generate_catalog.py` to update.",
                file=sys.stderr,
            )
            if DEBUG:
                print(f"\nExpected:\n{new_content}", file=sys.stderr)
                if existing_content:
                    print(f"\nGot:\n{existing_content}", file=sys.stderr)
                else:
                    print("\nGot: (file does not exist)", file=sys.stderr)
            sys.exit(1)
    else:
        with open(CATALOG_FILE, "w") as f:
            f.write(new_content)
        print(f"catalog.json updated with {len(catalog['skills'])} skill(s).")


if __name__ == "__main__":
    main()
