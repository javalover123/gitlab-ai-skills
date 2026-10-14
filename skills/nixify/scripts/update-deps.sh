#!/usr/bin/env bash
# update-deps.sh — the one-command dependency-update path nixify always ships.
# After a developer changes dependencies the normal way (and the lockfile
# updates), run this to refresh the Nix side (hash bump or codegen) so the
# developer never hand-edits Nix dependency data.
#
# Usage: bash scripts/update-deps.sh [ruby|go|rust|node|python|auto]
# Default "auto" detects from files present. Run from the repo root.

set -euo pipefail
TARGET="${1:-auto}"

detect() {
  [ -e Gemfile.lock ]      && echo ruby   && return
  [ -e go.mod ]            && echo go     && return
  [ -e Cargo.lock ]        && echo rust   && return
  [ -e package-lock.json ] || [ -e pnpm-lock.yaml ] || [ -e yarn.lock ] && echo node && return
  [ -e uv.lock ] || [ -e poetry.lock ] && echo python && return
  echo unknown
}
[ "$TARGET" = auto ] && TARGET="$(detect)"

case "$TARGET" in
  ruby)
    echo ">> Ruby: regenerating gemset.nix from Gemfile.lock"
    command -v bundle >/dev/null && bundle lock
    command -v bundix >/dev/null || { echo "bundix not found; enter the dev shell (it provides bundix)"; exit 1; }
    bundix
    echo ">> Commit the updated gemset.nix."
    ;;
  go)
    if [ -e gomod2nix.toml ]; then
      echo ">> Go: regenerating gomod2nix.toml"
      command -v gomod2nix >/dev/null || { echo "gomod2nix not found; enter the dev shell"; exit 1; }
      gomod2nix generate
      echo ">> Commit the updated gomod2nix.toml."
    else
      echo ">> Go: re-deriving vendorHash for buildGoModule."
      echo "   1) Set vendorHash = lib.fakeHash; in the package.nix"
      echo "   2) nix build .#<name> 2>&1 | grep -A2 'got:'"
      echo "   3) Paste the 'got:' sha256 back into vendorHash and commit."
    fi
    ;;
  rust)
    echo ">> Rust (crane): no Nix regeneration needed — crane reads Cargo.lock directly."
    echo "   Just commit the updated Cargo.lock (after your normal 'cargo update')."
    echo "   (If using buildRustPackage with cargoHash, re-derive it like the Go vendorHash flow.)"
    ;;
  node)
    echo ">> Node: re-deriving the deps hash."
    echo "   buildNpmPackage: set npmDepsHash = lib.fakeHash; build; paste the 'got:' hash."
    echo "   pnpm: set pnpmDeps hash = lib.fakeHash; build; paste the 'got:' hash."
    echo "   Then commit the package.nix hash change."
    ;;
  python)
    echo ">> Python (uv2nix/poetry2nix): no Nix regeneration needed — the lockfile is read directly."
    echo "   Commit the updated uv.lock / poetry.lock (after 'uv lock' / 'poetry lock')."
    ;;
  *)
    echo "Could not detect a supported lockfile. Pass one of: ruby|go|rust|node|python" >&2
    exit 1
    ;;
esac
