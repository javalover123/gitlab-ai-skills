#!/usr/bin/env python3
"""Sync skills whose source of truth lives in another repository.

Reads ``synced-skills.yml`` and, for each listed skill, mirrors the skill
directory from its SSoT repo into ``skills/<name>/``: writes added/changed
files and removes files that no longer exist upstream. After mirroring it runs
``lefthook run auto-fix`` (regenerating README/ToC/catalog/distribution
manifests) so the working tree is committable as-is.

This script performs NO git or MR operations — it only mutates the working
tree. The CI ``sync-skills`` job wraps it with the branch/commit/push/MR
ceremony. That keeps the fetch/diff/delete logic testable in isolation.

Fetching uses ``glab api`` (the repo's existing GitLab access convention), so
``glab`` must be authenticated in the environment.

Usage:
    scripts/sync_external_skills.py                # sync all manifest skills
    scripts/sync_external_skills.py --skill glab   # sync one skill
    scripts/sync_external_skills.py --check        # report drift; exit 1 if any
    scripts/sync_external_skills.py --no-auto-fix  # skip lefthook auto-fix
    scripts/sync_external_skills.py --debug
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
MANIFEST = os.path.join(REPO_ROOT, "synced-skills.yml")

DEBUG = False


def log_debug(msg):
    if DEBUG:
        print(f"DEBUG: {msg}", file=sys.stderr)


def log(msg):
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Manifest parsing (stdlib only — the CI image has no PyYAML, matching the
# rest of scripts/ which hand-parse YAML).
# ---------------------------------------------------------------------------

def parse_manifest(path):
    """Parse synced-skills.yml into {skill_name: {field: value}}.

    Expects the shape:
        skills:
          <name>:
            source_project: ...
            source_path: ...
            source_ref: ...
            mode: ...
    """
    skills = {}
    if not os.path.isfile(path):
        return skills

    with open(path) as f:
        lines = f.readlines()

    in_skills = False
    current = None
    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))

        if indent == 0:
            in_skills = stripped == "skills:"
            current = None
            continue
        if not in_skills:
            continue

        if indent == 2 and stripped.endswith(":"):
            current = stripped[:-1].strip()
            skills[current] = {}
            continue
        if indent >= 4 and current is not None and ":" in stripped:
            key, _, value = stripped.partition(":")
            skills[current][key.strip()] = value.strip()

    return skills


# ---------------------------------------------------------------------------
# GitLab fetch via glab api
# ---------------------------------------------------------------------------

def glab_api(path):
    """Call ``glab api <path>`` and return parsed JSON."""
    log_debug(f"glab api {path}")
    result = subprocess.run(
        ["glab", "api", path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"glab api {path} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def list_source_tree(project, ref, source_path):
    """Return {relative_path: blob_path} for every file under source_path.

    Paginates the repository tree API and filters to blobs (files).
    """
    encoded_project = urllib.parse.quote(project, safe="")
    encoded_path = urllib.parse.quote(source_path, safe="")
    files = {}
    page = 1
    while True:
        api = (
            f"projects/{encoded_project}/repository/tree"
            f"?path={encoded_path}&ref={urllib.parse.quote(ref, safe='')}"
            f"&recursive=true&per_page=100&page={page}"
        )
        entries = glab_api(api)
        if not entries:
            break
        for entry in entries:
            if entry.get("type") != "blob":
                continue
            full = entry["path"]
            rel = os.path.relpath(full, source_path)
            files[rel] = full
        if len(entries) < 100:
            break
        page += 1
    return files


def fetch_file(project, ref, blob_path):
    """Return raw bytes of a file at blob_path on ref."""
    encoded_project = urllib.parse.quote(project, safe="")
    encoded_file = urllib.parse.quote(blob_path, safe="")
    api = (
        f"projects/{encoded_project}/repository/files/{encoded_file}"
        f"?ref={urllib.parse.quote(ref, safe='')}"
    )
    payload = glab_api(api)
    if payload.get("encoding") == "base64":
        return base64.b64decode(payload["content"])
    return payload.get("content", "").encode()


# ---------------------------------------------------------------------------
# Mirror
# ---------------------------------------------------------------------------

def local_files(skill_dir):
    """Return the set of file paths (relative to skill_dir) currently present."""
    found = set()
    for root, _dirs, names in os.walk(skill_dir):
        for name in names:
            abs_path = os.path.join(root, name)
            found.add(os.path.relpath(abs_path, skill_dir))
    return found


def mirror_skill(name, cfg, *, check=False):
    """Mirror one skill from its source into skills/<name>/.

    Returns True if the working tree changed (or would change, in check mode).
    """
    for required in ("source_project", "source_path", "source_ref"):
        if required not in cfg:
            raise ValueError(f"skill '{name}' missing '{required}' in manifest")

    project = cfg["source_project"]
    source_path = cfg["source_path"]
    ref = cfg["source_ref"]
    skill_dir = os.path.join(SKILLS_DIR, name)

    log(f"Syncing '{name}' from {project}:{source_path}@{ref}")
    upstream = list_source_tree(project, ref, source_path)
    if not upstream:
        raise RuntimeError(
            f"no files found at {project}:{source_path}@{ref} — refusing to "
            f"wipe local skill '{name}'"
        )

    existing = local_files(skill_dir) if os.path.isdir(skill_dir) else set()
    changed = False

    # Add / update files present upstream.
    for rel, blob_path in sorted(upstream.items()):
        dest = os.path.join(skill_dir, rel)
        new_bytes = fetch_file(project, ref, blob_path)
        old_bytes = None
        if os.path.isfile(dest):
            with open(dest, "rb") as f:
                old_bytes = f.read()
        if old_bytes == new_bytes:
            continue
        changed = True
        verb = "would update" if check else "updating"
        log_debug(f"{verb} {name}/{rel}")
        if not check:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(new_bytes)

    # Remove files that no longer exist upstream.
    for rel in sorted(existing - set(upstream)):
        changed = True
        verb = "would remove" if check else "removing"
        log_debug(f"{verb} {name}/{rel}")
        if not check:
            os.remove(os.path.join(skill_dir, rel))

    # Prune now-empty directories.
    if not check and os.path.isdir(skill_dir):
        for root, dirs, names in os.walk(skill_dir, topdown=False):
            if not names and not dirs and root != skill_dir:
                os.rmdir(root)

    return changed


def run_auto_fix():
    """Regenerate README/ToC/catalog/distribution artifacts via lefthook."""
    log("Running lefthook auto-fix to regenerate distribution artifacts")
    result = subprocess.run(
        ["lefthook", "run", "auto-fix"],
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError("lefthook run auto-fix failed")


def main():
    global DEBUG
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", help="sync only this skill")
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift without writing; exit 1 if any skill is out of sync",
    )
    parser.add_argument(
        "--no-auto-fix",
        action="store_true",
        help="skip the lefthook auto-fix step",
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    DEBUG = args.debug

    manifest = parse_manifest(MANIFEST)
    if not manifest:
        log(f"No skills listed in {MANIFEST}; nothing to sync.")
        return

    if args.skill:
        if args.skill not in manifest:
            log(f"ERROR: '{args.skill}' is not listed in {MANIFEST}")
            sys.exit(1)
        manifest = {args.skill: manifest[args.skill]}

    any_changed = False
    for name, cfg in manifest.items():
        if mirror_skill(name, cfg, check=args.check):
            any_changed = True

    if args.check:
        if any_changed:
            log("Synced skills are OUT OF SYNC with their source of truth.")
            sys.exit(1)
        log("All synced skills are up to date.")
        return

    if any_changed and not args.no_auto_fix:
        run_auto_fix()

    if any_changed:
        log("Sync applied changes to the working tree.")
    else:
        log("No changes — synced skills already up to date.")


if __name__ == "__main__":
    main()
