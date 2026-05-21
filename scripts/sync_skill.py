"""Sync SKILL.md frontmatter versions into distributed plugin manifests.

For each distributed skill in .claude-plugin/plugins/<skill>/plugin.json and
.codex-plugin/plugins/<skill>/.codex-plugin/plugin.json, read the version from
SKILL.md and write it into the manifest.

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
CODEX_PLUGINS_DIR = os.path.join(REPO_ROOT, ".codex-plugin", "plugins")

sys.path.insert(0, SCRIPTS_DIR)
from lib.frontmatter import parse_frontmatter  # noqa: E402

DEBUG = "--debug" in sys.argv


def log_debug(msg):
    if DEBUG:
        print(f"DEBUG: {msg}", file=sys.stderr)


def get_plugin_json_path(env, plugin_name):
    if env == "claudecode":
        return os.path.join(PLUGINS_DIR, plugin_name, "plugin.json")
    if env == "codex":
        return os.path.join(CODEX_PLUGINS_DIR, plugin_name, ".codex-plugin", "plugin.json")
    raise ValueError(f"Unknown env: {env}")


def distributed_plugins_for_env(env):
    """Yield (plugin_name, skill_name) pairs for one environment."""
    plugins_dir = PLUGINS_DIR if env == "claudecode" else CODEX_PLUGINS_DIR
    if not os.path.isdir(plugins_dir):
        return
    for plugin_name in sorted(os.listdir(plugins_dir)):
        plugin_json = get_plugin_json_path(env, plugin_name)
        if not os.path.isfile(plugin_json):
            continue
        # The skill is symlinked under plugins/<plugin>/skills/<skill_name>
        skills_dir = os.path.join(plugins_dir, plugin_name, "skills")
        if os.path.isdir(skills_dir):
            for skill_name in os.listdir(skills_dir):
                yield plugin_name, skill_name
        else:
            yield plugin_name, plugin_name


def main():
    is_ci = "--ci" in sys.argv
    has_errors = False
    found = False

    for env in ("claudecode", "codex"):
        for plugin_name, skill_name in distributed_plugins_for_env(env):
            found = True
            skill_md = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
            if not os.path.isfile(skill_md):
                print(
                    f"SKIP: {env}/{plugin_name} — SKILL.md not found at {os.path.relpath(skill_md, REPO_ROOT)}"
                )
                continue

            fields = parse_frontmatter(skill_md)
            skill_version = fields.get("version")
            log_debug(f"{env}/{plugin_name}: SKILL.md version={skill_version}")

            if not skill_version:
                print(f"SKIP: {env}/{plugin_name} — no version field in SKILL.md")
                continue

            plugin_json_path = get_plugin_json_path(env, plugin_name)
            with open(plugin_json_path) as f:
                plugin_data = json.load(f)

            plugin_version = plugin_data.get("version")
            log_debug(f"{env}/{plugin_name}: plugin.json version={plugin_version}")

            if plugin_version == skill_version:
                print(f"  OK: {env}/{plugin_name} — version {skill_version} already in sync")
                continue

            if is_ci:
                has_errors = True
                print(
                    f"FAIL: {env}/{plugin_name} — plugin.json {plugin_version!r} != SKILL.md {skill_version!r}"
                )
            else:
                plugin_data["version"] = skill_version
                with open(plugin_json_path, "w") as f:
                    f.write(json.dumps(plugin_data, indent=2) + "\n")
                print(
                    f"SYNC: {env}/{plugin_name} — plugin.json updated "
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
