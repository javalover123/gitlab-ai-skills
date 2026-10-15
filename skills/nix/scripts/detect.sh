#!/usr/bin/env bash
# detect.sh: inventory a directory for the nix skill. Reports languages and
# lockfiles, existing build-system and Nix signals (nixpkgs checkout, NixOS
# configuration, flake, non-flake project), which Nix tools are on PATH, and a
# first-guess track.
#
# Usage: bash scripts/detect.sh [/path/to/dir]
# Output: a plain-text report on stdout. It's a starting point: read the
# project's README, docs, and CI to confirm intent. Safe on any directory,
# including one with no Nix files; it only reads.

set -Eeuo pipefail
ROOT="${1:-.}"
cd "$ROOT" 2>/dev/null || {
  echo "detect.sh: cannot enter directory: $ROOT" >&2
  exit 1
}

have() { [ -e "$1" ] && echo "  - $1"; return 0; }
any()  { for f in "$@"; do [ -e "$f" ] && return 0; done; return 1; }
# True when the named file exists and mentions the pattern.
mentions() { [ -f "$1" ] && grep -q -E -- "$2" "$1" 2>/dev/null; }

echo "== nix skill detection report for: $(pwd) =="
echo

echo "Languages & lockfiles found:"
LANGS=()
REFS=()
if any Gemfile Gemfile.lock; then
  echo "  RUBY"; have Gemfile; have Gemfile.lock; have gemset.nix; have .ruby-version
  LANGS+=("ruby"); REFS+=("references/lang-ruby.md")
fi
if any go.mod go.sum; then
  echo "  GO"; have go.mod; have go.sum; have gomod2nix.toml; have vendor/modules.txt
  LANGS+=("go"); REFS+=("references/lang-go.md")
fi
if any Cargo.toml Cargo.lock; then
  echo "  RUST"; have Cargo.toml; have Cargo.lock; have rust-toolchain.toml; have rust-toolchain
  LANGS+=("rust"); REFS+=("references/lang-rust.md")
fi
if any pyproject.toml poetry.lock uv.lock requirements.txt; then
  echo "  PYTHON"; have pyproject.toml; have poetry.lock; have uv.lock; have requirements.txt
  LANGS+=("python"); REFS+=("references/lang-python.md")
fi
if any package.json package-lock.json pnpm-lock.yaml yarn.lock; then
  echo "  NODE"; have package.json; have package-lock.json; have pnpm-lock.yaml; have yarn.lock
  LANGS+=("node"); REFS+=("references/lang-nodejs.md")
fi
if any CMakeLists.txt meson.build configure.ac Makefile.am; then
  echo "  C/C++"; have CMakeLists.txt; have meson.build; have configure.ac; have Makefile.am
  LANGS+=("c-cpp"); REFS+=("references/lang-c-cpp.md")
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
[ -d build-chains ] && echo "  - build-chains/  (ordered build lists, hand-rolled build system)"
for s in builder.sh tbm.sh packager.sh build.sh; do have "$s"; done
[ -d tbms ] && echo "  - tbms/  (TBMS-style component tree, hand-rolled build system)"
echo

# --- Nix context -----------------------------------------------------------
IS_NIXPKGS=0
IS_NIXOS=0
IS_FLAKE=0
IS_NONFLAKE=0

# A nixpkgs checkout has the by-name tree and lib/ (plus nixos/ and ci/).
if [ -d pkgs/by-name ] && [ -d lib ]; then
  IS_NIXPKGS=1
fi
if [ -f flake.nix ]; then
  IS_FLAKE=1
fi
# nixpkgs itself mentions nixosConfigurations (in its flake), but it's the
# source of the module system, not a machine configuration.
if [ "$IS_NIXPKGS" -eq 0 ] && { mentions flake.nix 'nixosConfigurations' || any configuration.nix system.nix; }; then
  IS_NIXOS=1
fi
if any default.nix shell.nix npins/default.nix nix/sources.nix; then
  IS_NONFLAKE=1
fi

echo "Nix context:"
if [ "$IS_NIXPKGS" -eq 1 ]; then
  echo "  nixpkgs checkout: yes (pkgs/by-name and lib/ present)"
  have nixos; have ci; have maintainers/maintainer-list.nix
else
  echo "  nixpkgs checkout: no"
fi
if [ "$IS_NIXOS" -eq 1 ]; then
  echo "  NixOS configuration: yes"
  mentions flake.nix 'nixosConfigurations' && echo "    - flake.nix defines nixosConfigurations"
  have configuration.nix; have system.nix; have hardware-configuration.nix; have hosts
else
  echo "  NixOS configuration: no"
fi
if [ "$IS_FLAKE" -eq 1 ]; then
  echo "  flake: yes"
  have flake.lock
  # Output names are a heuristic grep of flake.nix, not an evaluation.
  OUTS=""
  for o in packages devShells checks overlays nixosModules nixosConfigurations formatter apps templates; do
    mentions flake.nix "(^|[^A-Za-z_])$o([^A-Za-z_]|\$)" && OUTS="$OUTS $o"
  done
  [ -n "$OUTS" ] && echo "    - outputs mentioned in flake.nix:$OUTS"
  mentions flake.nix 'flake-parts' && echo "    - uses flake-parts"
  mentions flake.nix 'treefmt-nix' && echo "    - uses treefmt-nix"
else
  echo "  flake: no"
fi
if [ "$IS_NONFLAKE" -eq 1 ]; then
  echo "  non-flake Nix project: yes"
  have default.nix; have shell.nix
  [ -d npins ] && echo "  - npins/  (pinned sources: npins)"
  [ -f nix/sources.nix ] && echo "  - nix/sources.nix  (pinned sources: niv)"
  [ -f nix/sources.json ] && echo "  - nix/sources.json"
else
  echo "  non-flake Nix project: no"
fi
if [ -f .envrc ]; then
  DIRENV="$(grep -E '^[[:space:]]*use[[:space:]]+(flake|nix)' .envrc 2>/dev/null | head -n 1 || true)"
  [ -n "$DIRENV" ] && echo "  .envrc: $DIRENV"
fi
echo

echo "Nix tools on PATH:"
for t in nix nixfmt statix deadnix nixpkgs-review nix-update nixpkgs-vet treefmt npins; do
  if command -v "$t" >/dev/null 2>&1; then
    echo "  - $t: $(command -v "$t")"
  else
    echo "  - $t: missing"
  fi
done
echo

echo "Entry points / services (heuristic):"
have main.go; have src/main.rs; have cmd; have bin
# Glob loops, not `ls`, so odd file names survive; `[ -d ]` skips an unmatched glob.
for d in crates/*; do [ -d "$d" ] && echo "  - crate: $d"; done | head -20 || true
for d in packages/*; do [ -d "$d" ] && echo "  - package: $d"; done | head -20 || true
echo

# Track guess
echo "First-guess track:"
HANDROLLED=0
if [ -d build-chains ] || [ -d tbms ] || [ -d config/software ]; then
  HANDROLLED=1
elif any builder.sh tbm.sh packager.sh && [ ${#LANGS[@]} -le 1 ]; then
  HANDROLLED=1
fi
if [ "$IS_NIXPKGS" -eq 1 ]; then
  echo "  >> NIXPKGS CONTRIBUTION."
  echo "     Use references/upstreaming-and-prs.md, references/derivation-authoring.md,"
  echo "     and the templates in assets/templates/nixpkgs/. nixpkgs is a non-flake"
  echo "     workflow: nix-build -A <attr>, nix-shell."
elif [ "$IS_NIXOS" -eq 1 ]; then
  echo "  >> NIXOS SYSTEM CONFIGURATION."
  echo "     Use references/nixos-systems.md; for a new flake see assets/templates/nixos/flake.nix."
elif [ "$IS_FLAKE" -eq 1 ] || [ "$IS_NONFLAKE" -eq 1 ]; then
  echo "  >> EXISTING NIX PROJECT."
  echo "     An existing convention wins: extend the flake or shell.nix you found, keep its"
  echo "     pinning tool, and don't convert it unless asked. See references/choosing-a-track.md."
elif [ "$HANDROLLED" -eq 1 ]; then
  echo "  >> BUILD-SYSTEM REPLACEMENT (Stage 3)."
  echo "     The repo's product appears to be software it builds. See"
  echo "     references/worked-example-gitlab-toolchain.md."
else
  echo "  >> APPLICATION PROJECT (Stages 1-2)."
  echo "     Languages: ${LANGS[*]:-unknown}."
  for r in "${REFS[@]:-}"; do
    [ -n "$r" ] && echo "     Read $r"
  done
  echo "     Scaffold from assets/templates/ (see references/nixify-workflow.md)."
fi
if [ "$HANDROLLED" -eq 1 ] && { [ "$IS_FLAKE" -eq 1 ] || [ "$IS_NONFLAKE" -eq 1 ]; }; then
  echo "  (Hand-rolled build markers also found; see references/worked-example-gitlab-toolchain.md.)"
fi
echo
echo "NEXT: read README/CONTRIBUTING/docs/CI to confirm purpose, then write the"
echo "plan (track, per-language builder + rationale, file layout, human decisions)"
echo "before generating any files. References: references/choosing-a-track.md,"
echo "references/nixify-workflow.md."
