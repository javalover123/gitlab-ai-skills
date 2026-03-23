"""Sync the version in SKILL.md frontmatter into the ClaudeCode plugin.json.

For each skill that has a corresponding .claude-plugin/plugins/<skill>/plugin.json,
reads the version from SKILL.md and writes it into plugin.json.

Usage:
    python scripts/sync_skill.py               # Sync all distributed skills and report
    python scripts/sync_skill.py --ci          # Check only; exit 1 if any version is out of sync
    python scripts/sync_skill.py --debug       # Enable debug logging
"""

import json
import os
import sys

SCRIPTS_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPTS_DIR, "..")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
PLUGINS_DIR = os.path.join(REPO_ROOT, ".claude-plugin", "plugins")

sys.path.insert(0, SCRIPTS_DIR)
from lib.frontmatter import parse_frontmatter  # noqa: E402

DEBUG = "--debug" in sys.argv


def log_debug(msg):
    if DEBUG:
        print(f"DEBUG: {msg}", file=sys.stderr)


def get_plugin_json_path(plugin_name):
    return os.path.join(PLUGINS_DIR, plugin_name, "plugin.json")


def distributed_plugins():
    """Yield (plugin_name, skill_name) pairs for all plugins that have a plugin.json."""
    if not os.path.isdir(PLUGINS_DIR):
        return
    for plugin_name in sorted(os.listdir(PLUGINS_DIR)):
        plugin_json = get_plugin_json_path(plugin_name)
        if not os.path.isfile(plugin_json):
            continue
        # The skill is symlinked under plugins/<plugin>/skills/<skill_name>
        skills_dir = os.path.join(PLUGINS_DIR, plugin_name, "skills")
        if os.path.isdir(skills_dir):
            for skill_name in os.listdir(skills_dir):
                yield plugin_name, skill_name
        else:
            yield plugin_name, plugin_name


def main():
    is_ci = "--ci" in sys.argv
    has_errors = False
    found = False

    for plugin_name, skill_name in distributed_plugins():
        found = True
        skill_md = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        if not os.path.isfile(skill_md):
            print(f"SKIP: {plugin_name} — SKILL.md not found at {os.path.relpath(skill_md, REPO_ROOT)}")
            continue

        fields = parse_frontmatter(skill_md)
        skill_version = fields.get("version")
        log_debug(f"{plugin_name}: SKILL.md version={skill_version}")

        if not skill_version:
            print(f"SKIP: {plugin_name} — no version field in SKILL.md")
            continue

        plugin_json_path = get_plugin_json_path(plugin_name)
        with open(plugin_json_path) as f:
            plugin_data = json.load(f)

        plugin_version = plugin_data.get("version")
        log_debug(f"{plugin_name}: plugin.json version={plugin_version}")

        if plugin_version == skill_version:
            print(f"  OK: {plugin_name} — version {skill_version} already in sync")
            continue

        if is_ci:
            has_errors = True
            print(
                f"FAIL: {plugin_name} — plugin.json {plugin_version!r} != SKILL.md {skill_version!r}"
            )
        else:
            plugin_data["version"] = skill_version
            with open(plugin_json_path, "w") as f:
                f.write(json.dumps(plugin_data, indent=2) + "\n")
            print(
                f"SYNC: {plugin_name} — plugin.json updated "
                f"{plugin_version!r} → {skill_version!r}"
            )

    if not found:
        print("No distributed skills found.")
        sys.exit(0)

    if is_ci and has_errors:
        print(
            "\nERROR: Some plugin.json versions are out of sync with SKILL.md. "
            "Run bin/sync-skill to fix.",
            file=sys.stderr,
        )
        sys.exit(1)
    elif not has_errors:
        print("\nAll distribution versions are in sync.")


if __name__ == "__main__":
    main()
