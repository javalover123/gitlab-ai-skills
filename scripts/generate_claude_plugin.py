#!/usr/bin/env python3
"""Generates .claude-plugin/ manifests from skills/*/SKILL.md frontmatter.

Generates two types of files:
  - .claude-plugin/marketplace.json — repo-root marketplace catalog
  - skills/<name>/.claude-plugin/plugin.json — per-skill plugin manifest

Usage:
    python3 scripts/generate_claude_plugin.py          # Generate/update manifests
    python3 scripts/generate_claude_plugin.py --ci      # Verify manifests are up to date (exit 1 if not)
    python3 scripts/generate_claude_plugin.py --debug   # Enable debug logging
"""

import json
import os
import sys

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
MARKETPLACE_FILE = os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json")

# Marketplace metadata
MARKETPLACE_NAME = "gitlab-skills"
MARKETPLACE_OWNER = {"name": "GitLab"}
MARKETPLACE_REPO_URL = "https://gitlab.com/gitlab-org/ai/skills.git"

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def parse_frontmatter(skill_file):
    """Extract top-level key-value pairs from YAML frontmatter.

    Returns a dict of field_name -> value. Only handles simple top-level keys.
    Supports YAML multi-line scalars (``>``, ``>-``, ``|``, ``|-``).
    """
    log_debug(f"Parsing frontmatter from {skill_file}")
    fields = {}

    with open(skill_file, "r") as f:
        lines = f.readlines()

    if not lines or lines[0].strip() != "---":
        return fields

    current_key = None
    multiline_parts = []
    multiline_folded = False

    def _flush_multiline():
        if current_key and multiline_parts:
            joiner = " " if multiline_folded else "\n"
            fields[current_key] = joiner.join(multiline_parts)
            log_debug(f"Found field: '{current_key}' = '{fields[current_key]}'")

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            _flush_multiline()
            break

        if current_key and line[0:1].isspace() and stripped:
            multiline_parts.append(stripped)
            continue

        _flush_multiline()
        current_key = None
        multiline_parts = []

        if not line[0:1].isspace() and ":" in stripped:
            key = stripped.split(":", 1)[0].strip()
            value = stripped.split(":", 1)[1].strip().strip("\"'")
            if value in (">", ">-", "|", "|-"):
                current_key = key
                multiline_parts = []
                multiline_folded = value.startswith(">")
            else:
                fields[key] = value
                log_debug(f"Found field: '{key}' = '{value}'")

    return fields


def generate_plugin_json(skill_name, fields):
    """Generate a per-skill .claude-plugin/plugin.json content."""
    return {
        "name": fields.get("name", skill_name),
        "description": fields.get("description", ""),
        "version": fields.get("version", "0.0.0"),
        "author": {"name": "GitLab"},
        "license": fields.get("license", "MIT"),
    }


def generate_marketplace_entry(skill_name, fields):
    """Generate a marketplace plugin entry for a skill."""
    return {
        "name": fields.get("name", skill_name),
        "source": {
            "source": "git-subdir",
            "url": MARKETPLACE_REPO_URL,
            "path": f"skills/{skill_name}",
        },
        "description": fields.get("description", ""),
        "version": fields.get("version", "0.0.0"),
        "author": {"name": "GitLab"},
        "license": fields.get("license", "MIT"),
    }


def collect_skills():
    """Collect all skills and their frontmatter.

    Returns a sorted list of (skill_name, fields) tuples.
    """
    log_debug(f"Scanning skills directory: {SKILLS_DIR}")
    skills = []

    if not os.path.isdir(SKILLS_DIR):
        log_debug("Skills directory does not exist")
        return skills

    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_file = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        if not os.path.isfile(skill_file):
            log_debug(f"Skipping {skill_name}: no SKILL.md found")
            continue

        fields = parse_frontmatter(skill_file)
        skills.append((skill_name, fields))
        log_debug(f"Collected skill: {skill_name}")

    return skills


def generate_all(skills):
    """Generate all manifest contents.

    Returns a dict of file_path -> content_string.
    """
    files = {}

    # Per-skill plugin.json files
    for skill_name, fields in skills:
        plugin_json = generate_plugin_json(skill_name, fields)
        path = os.path.join(SKILLS_DIR, skill_name, ".claude-plugin", "plugin.json")
        files[path] = json.dumps(plugin_json, indent=2) + "\n"

    # Root marketplace.json
    marketplace = {
        "name": MARKETPLACE_NAME,
        "owner": MARKETPLACE_OWNER,
        "plugins": [
            generate_marketplace_entry(name, fields) for name, fields in skills
        ],
    }
    files[MARKETPLACE_FILE] = json.dumps(marketplace, indent=2) + "\n"

    return files


def main():
    is_ci_mode = "--ci" in sys.argv

    skills = collect_skills()
    generated_files = generate_all(skills)

    if is_ci_mode:
        out_of_date = []

        for file_path, expected_content in generated_files.items():
            rel_path = os.path.relpath(file_path, REPO_ROOT)
            if os.path.isfile(file_path):
                with open(file_path, "r") as f:
                    actual_content = f.read()
                if actual_content != expected_content:
                    out_of_date.append(rel_path)
                    log_debug(f"{rel_path} is out of date")
                    if DEBUG:
                        print(f"\n--- Expected {rel_path} ---", file=sys.stderr)
                        print(expected_content, file=sys.stderr)
                        print(f"--- Got {rel_path} ---", file=sys.stderr)
                        print(actual_content, file=sys.stderr)
                else:
                    log_debug(f"{rel_path} is up to date")
            else:
                out_of_date.append(rel_path)
                log_debug(f"{rel_path} does not exist")

        if out_of_date:
            print(
                "ERROR: .claude-plugin/ manifests are out of date. "
                "Run `python3 scripts/generate_claude_plugin.py` to update.\n"
                f"Out of date: {', '.join(out_of_date)}",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            print(".claude-plugin/ manifests are up to date.")
            sys.exit(0)
    else:
        for file_path, content in generated_files.items():
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)
            rel_path = os.path.relpath(file_path, REPO_ROOT)
            print(f"Updated: {rel_path}")

        print(f"\n{len(generated_files)} file(s) generated for {len(skills)} skill(s).")


if __name__ == "__main__":
    main()
