#!/usr/bin/env python3
"""Discover and run per-skill unit tests.

Skills are self-contained directories, so their tests live next to their code
(``skills/<name>/scripts/test_*.py``) rather than in a central suite. Python's
``unittest discover`` only recurses into importable packages, which would force
an ``__init__.py`` into every skill; instead this runner globs for ``test_*.py``
under ``skills/`` and executes each file as its own process. Tests use only the
standard library, so no third-party dependency is required.

Usage:
    python3 scripts/run_skill_tests.py            # run all skill tests
    python3 scripts/run_skill_tests.py --ci        # same; nonzero exit on failure
    python3 scripts/run_skill_tests.py --debug     # debug logging
"""

import glob
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

DEBUG = "--debug" in sys.argv


def log_debug(message):
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def discover_tests():
    pattern = os.path.join(SKILLS_DIR, "**", "test_*.py")
    return sorted(glob.glob(pattern, recursive=True))


def main():
    if not os.path.isdir(SKILLS_DIR):
        print("No skills directory found.")
        sys.exit(0)

    tests = discover_tests()
    if not tests:
        print("No skill tests found (skills/**/test_*.py).")
        sys.exit(0)

    failures = []
    for path in tests:
        rel = os.path.relpath(path, REPO_ROOT)
        log_debug(f"running {rel}")
        print(f">>> {rel}")
        result = subprocess.run([sys.executable, path])
        if result.returncode != 0:
            failures.append(rel)
        print()

    if failures:
        print("FAILED skill tests:")
        for rel in failures:
            print(f"  - {rel}")
        sys.exit(1)

    print(f"All skill tests passed ({len(tests)} file(s)).")


if __name__ == "__main__":
    main()
