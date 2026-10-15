#!/usr/bin/env bash
# Thin wrapper so scripts/run_skill_tests.sh's `tests/test_*.sh` discovery
# picks up the Python regression tests in test_check_completion.py.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/test_check_completion.py"
