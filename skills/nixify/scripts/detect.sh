#!/usr/bin/env bash
# detect.sh — inventory a repo for nixify: languages, lockfiles, build system,
# entry points, and a first-guess track (application vs build-system-replacement).
#
# Usage: bash scripts/detect.sh /path/to/repo
# Output: human-readable report on stdout. Treat as a starting point — always
# read the project's own README/docs/CI to confirm intent.

set -euo pipefail
ROOT="${1:-.}"
cd "$ROOT"

have() { [ -e "$1" ] && echo "  - $1"; return 0; }
any()  { for f in "$@"; do [ -e "$f" ] && return 0; done; return 1; }

echo "== nixify detection report for: $(pwd) =="
echo

echo "Languages & lockfiles found:"
LANGS=()
if any Gemfile Gemfile.lock; then
  echo "  RUBY"; have Gemfile; have Gemfile.lock; have gemset.nix; have .ruby-version
  LANGS+=("ruby")
fi
if any go.mod go.sum; then
  echo "  GO"; have go.mod; have go.sum; have gomod2nix.toml; have vendor/modules.txt
  LANGS+=("go")
fi
if any Cargo.toml Cargo.lock; then
  echo "  RUST"; have Cargo.toml; have Cargo.lock; have rust-toolchain.toml; have rust-toolchain
  LANGS+=("rust")
fi
if any pyproject.toml poetry.lock uv.lock requirements.txt; then
  echo "  PYTHON"; have pyproject.toml; have poetry.lock; have uv.lock; have requirements.txt
  LANGS+=("python")
fi
if any package.json package-lock.json pnpm-lock.yaml yarn.lock; then
  echo "  NODE"; have package.json; have package-lock.json; have pnpm-lock.yaml; have yarn.lock
  LANGS+=("node")
fi
if any CMakeLists.txt meson.build configure.ac Makefile.am; then
  echo "  C/C++"; have CMakeLists.txt; have meson.build; have configure.ac; have Makefile.am
  LANGS+=("c-cpp")
fi
[ ${#LANGS[@]} -eq 0 ] && echo "  (none of the recognized language manifests found)"
echo

echo "Existing build system signals:"
have Makefile; have makefile; have GNUmakefile
have Dockerfile; have Containerfile
have .mise.toml; have mise.toml; have .tool-versions
have BUILD.bazel; have WORKSPACE; have MODULE.bazel
have flake.nix; have default.nix; have shell.nix
# Omnibus / hand-rolled build-system markers:
[ -d config/software ] && echo "  - config/software/  (Omnibus software definitions)"
if ls ./*.rb >/dev/null 2>&1 && [ -d config ]; then echo "  - top-level *.rb + config/ (possible Omnibus)"; fi
[ -d build-chains ] && echo "  - build-chains/  (ordered build lists — hand-rolled build system)"
for s in builder.sh tbm.sh packager.sh build.sh; do have "$s"; done
[ -d tbms ] && echo "  - tbms/  (TBMS-style component tree — hand-rolled build system)"
echo

echo "Entry points / services (heuristic):"
have main.go; have src/main.rs; have cmd; have bin
find crates -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sed 's|^crates/|  - crate: |' | head -20 || true
find packages -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sed 's|^packages/|  - package: |' | head -20 || true
echo

# Track guess
echo "First-guess track:"
HANDROLLED=0
if [ -d build-chains ] || [ -d tbms ] || [ -d config/software ]; then
  HANDROLLED=1
elif any builder.sh tbm.sh packager.sh && [ ${#LANGS[@]} -le 1 ]; then
  HANDROLLED=1
fi
if [ "$HANDROLLED" -eq 1 ]; then
  echo "  >> BUILD-SYSTEM REPLACEMENT (Stage 3)."
  echo "     The repo's product appears to be software it builds. See"
  echo "     references/worked-example-gitlab-toolchain.md."
else
  echo "  >> APPLICATION PROJECT (Stages 1-2)."
  echo "     Languages: ${LANGS[*]:-unknown}. Use the matching references/<lang>.md."
fi
echo
echo "NEXT: read README/CONTRIBUTING/docs/CI to confirm purpose, then write the"
echo "plan (track, per-language builder + rationale, file layout, human decisions)"
echo "before generating any files."
