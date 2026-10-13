#!/usr/bin/env bash
# CI discovers skills/**/tests/test_*.sh; this skill's suite is Python
# (stdlib unittest), like its helper scripts.
#
# Usage: bash skills/gitlab-pipeline-watch/tests/test_scripts.sh
set -Eeuo pipefail

exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/test_scripts.py"
