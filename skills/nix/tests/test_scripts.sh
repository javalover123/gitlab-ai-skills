#!/usr/bin/env bash
# Tests for the nix skill's helper scripts: find-rules.py, antipatterns.py, gates.sh.
#
# The suites are Python unittest (standard library only) because they drive the
# Python scripts directly and stub tools on an isolated PATH. They need no network,
# credentials, Nix, or git: tests that depend on git skip themselves when it's absent.
#
# Usage: bash tests/test_scripts.sh   (exits non-zero if any case fails)

set -Eeuo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "SKIP: python3 not found; the script tests need it" >&2
  exit 0
fi

echo "Running nix skill script tests with $(python3 --version 2>&1)"
python3 -m unittest discover -s "$TESTS_DIR" -p 'test_*.py' -v
