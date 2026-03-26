#!/usr/bin/env python3
"""Regenerates the Claude Code plugins table in README.md from .claude-plugin/ metadata.

Reads marketplace.json for the plugin list, each plugin's plugin.json for details,
and the plugin's skills/ directory for included skills, then updates the section
between CLAUDECODE_PLUGINS_START and CLAUDECODE_PLUGINS_END tags.

Usage:
    python3 scripts/update_claudecode_readme.py          # Update README.md in place
    python3 scripts/update_claudecode_readme.py --ci      # Verify README.md is up to date (exit 1 if not)
    python3 scripts/update_claudecode_readme.py --debug   # Enable debug logging
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
README_FILE = os.path.join(REPO_ROOT, "README.md")
CLAUDE_PLUGIN_DIR = os.path.join(REPO_ROOT, ".claude-plugin")
MARKETPLACE_FILE = os.path.join(CLAUDE_PLUGIN_DIR, "marketplace.json")

# Tags for the auto-generated section in README.md
PLUGINS_START_TAG = "<!-- CLAUDECODE_PLUGINS_START -->"
PLUGINS_END_TAG = "<!-- CLAUDECODE_PLUGINS_END -->"

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def load_marketplace():
    """Load marketplace.json and return the list of plugin entries."""
    if not os.path.isfile(MARKETPLACE_FILE):
        log_debug(f"No marketplace.json found at {MARKETPLACE_FILE}")
        return []

    with open(MARKETPLACE_FILE, "r") as f:
        data = json.load(f)

    plugins = data.get("plugins", [])
    log_debug(f"Found {len(plugins)} plugin(s) in marketplace.json")
    return plugins


def load_plugin_json(source_path):
    """Load plugin.json from the given source path (relative to repo root).

    Returns a dict with the plugin metadata, or an empty dict on failure.
    """
    resolved = os.path.normpath(os.path.join(REPO_ROOT, source_path))
    plugin_file = os.path.join(resolved, "plugin.json")

    if not os.path.isfile(plugin_file):
        log_debug(f"No plugin.json found at {plugin_file}")
        return {}

    with open(plugin_file, "r") as f:
        data = json.load(f)

    log_debug(f"Loaded plugin.json: {data}")
    return data


def list_plugin_skills(source_path):
    """Return a list of (skill_name, skill_rel_path) for skills in a plugin's skills/ dir.

    Resolves symlinks to find each skill's SKILL.md and returns the path relative
    to the repo root. Falls back to using the symlink name if SKILL.md is not found.
    """
    resolved = os.path.normpath(os.path.join(REPO_ROOT, source_path))
    skills_dir = os.path.join(resolved, "skills")

    if not os.path.isdir(skills_dir):
        log_debug(f"No skills/ directory found at {skills_dir}")
        return []

    skills = []
    for entry in sorted(os.listdir(skills_dir)):
        entry_path = os.path.join(skills_dir, entry)
        # Resolve symlinks to get the real path
        real_path = os.path.realpath(entry_path)
        skill_md = os.path.join(real_path, "SKILL.md")

        if os.path.isfile(skill_md):
            rel_skill_md = os.path.relpath(skill_md, REPO_ROOT)
            # Read skill name from frontmatter, fall back to directory name
            fields = parse_frontmatter(skill_md)
            skill_name = fields.get("name") or entry
        else:
            rel_skill_md = None
            skill_name = entry

        log_debug(f"Found skill: {skill_name} -> {rel_skill_md}")
        skills.append((skill_name, rel_skill_md))

    return skills


def generate_table():
    """Generate the plugins markdown table from marketplace and plugin.json files."""
    log_debug(f"Loading plugins from {MARKETPLACE_FILE}")

    marketplace_plugins = load_marketplace()

    if not marketplace_plugins:
        log_debug("No plugins found in marketplace.json")
        return ""

    rows = []

    for entry in marketplace_plugins:
        plugin_name = entry.get("name", "")
        source = entry.get("source", "")

        plugin_data = load_plugin_json(source) if source else {}

        name = plugin_data.get("name") or plugin_name
        description = plugin_data.get("description") or "-"
        version = plugin_data.get("version") or "-"

        # Link plugin name to its directory
        if source:
            rel_source = source.removeprefix("./")
            plugin_link = f"[`{name}`]({rel_source})"
        else:
            plugin_link = f"`{name}`"

        # Build skills cell: comma-separated links to each skill's SKILL.md
        skills = list_plugin_skills(source) if source else []
        if skills:
            skill_parts = []
            for skill_name, skill_path in skills:
                if skill_path:
                    skill_parts.append(f"[`{skill_name}`]({skill_path})")
                else:
                    skill_parts.append(f"`{skill_name}`")
            skills_cell = ", ".join(skill_parts)
        else:
            skills_cell = "-"

        row = f"| {plugin_link} | {skills_cell} | {description} | {version} |"
        rows.append(row)
        log_debug(f"Added row for plugin: {name}")

    if not rows:
        log_debug("No rows generated")
        return ""

    header = "| Plugin | Skills | Description | Version |\n| ------ | ------ | ----------- | ------- |"
    table = header + "\n" + "\n".join(rows)
    log_debug(f"Generated table:\n{table}")
    return table


def read_existing_table():
    """Read the README and extract the existing table between the plugin tags."""
    log_debug(f"Reading existing table from {README_FILE}")
    with open(README_FILE, "r") as f:
        content = f.read()

    match = re.search(
        f"{re.escape(PLUGINS_START_TAG)}(.*?){re.escape(PLUGINS_END_TAG)}",
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

    if PLUGINS_START_TAG not in content:
        print(
            f"ERROR: {PLUGINS_START_TAG} not found in README.md. "
            "Add the tags to README.md before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    updated = re.sub(
        f"{re.escape(PLUGINS_START_TAG)}.*?{re.escape(PLUGINS_END_TAG)}",
        f"{PLUGINS_START_TAG}\n{new_table}\n{PLUGINS_END_TAG}",
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
            print("README.md Claude Code plugins table is up to date.")
            sys.exit(0)
        else:
            log_debug("Tables do not match in CI mode. Exiting with code 1.")
            print(
                "ERROR: README.md Claude Code plugins table is out of date. "
                "Run `python3 scripts/update_claudecode_readme.py` to update.",
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
