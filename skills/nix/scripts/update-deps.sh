#!/usr/bin/env bash
# update-deps.sh: the one-command dependency-update path to ship with a Nix
# change. After a developer changes dependencies the normal way (and the
# lockfile updates), run this to refresh the Nix side (a hash bump or a
# regenerated file) so nobody hand-edits Nix dependency data.
#
# Usage: bash scripts/update-deps.sh [ruby|go|rust|node|python|auto] [flake-attr]
#   Default target is "auto", detected from the lockfiles present. Run it from
#   the repo root. When `nix-update` is on PATH and you pass the flake attribute
#   of the package (for example `myapp`), the hash-based ecosystems (Go with
#   vendorHash, Rust with cargoHash, Node with npmDepsHash or a pnpm hash) are
#   updated with `nix-update --flake --version=skip`. The nix-update README
#   lists those hashes as supported and says `--version=skip` refreshes hashes
#   without touching `version`; check the diff, since that mode isn't exercised
#   by this script's tests.

set -Eeuo pipefail

usage() {
  echo "Usage: $0 [ruby|go|rust|node|python|auto] [flake-attr]" >&2
}

case "${1:-}" in
  -h | --help)
    usage
    exit 0
    ;;
esac

TARGET="${1:-auto}"
ATTR="${2:-}"

detect() {
  [ -e Gemfile.lock ] && echo ruby && return
  [ -e go.mod ] && echo go && return
  [ -e Cargo.lock ] && echo rust && return
  if [ -e package-lock.json ] || [ -e pnpm-lock.yaml ] || [ -e yarn.lock ]; then
    echo node && return
  fi
  if [ -e uv.lock ] || [ -e poetry.lock ]; then
    echo python && return
  fi
  echo unknown
}

# List every ecosystem whose lockfile exists, so a mixed repo isn't silently
# handled as only the first one.
present() {
  local found=""
  [ -e Gemfile.lock ] && found="$found ruby"
  [ -e go.mod ] && found="$found go"
  [ -e Cargo.lock ] && found="$found rust"
  if [ -e package-lock.json ] || [ -e pnpm-lock.yaml ] || [ -e yarn.lock ]; then found="$found node"; fi
  if [ -e uv.lock ] || [ -e poetry.lock ]; then found="$found python"; fi
  echo "${found# }"
}

if [ "$TARGET" = auto ]; then
  TARGET="$(detect)"
  FOUND="$(present)"
  case "$FOUND" in
    *" "*) echo ">> Several lockfiles found ($FOUND); handling '$TARGET'. Pass another target to update it too." ;;
  esac
fi

# Refresh hashes in place when nix-update can do it; returns non-zero when it
# can't, so the caller prints the manual steps instead.
try_nix_update() {
  if [ -n "$ATTR" ] && command -v nix-update >/dev/null 2>&1; then
    echo ">> nix-update --flake --version=skip $ATTR"
    nix-update --flake --version=skip "$ATTR"
    echo ">> Commit the changed hash."
    return 0
  fi
  return 1
}

case "$TARGET" in
  ruby)
    echo ">> Ruby: regenerating gemset.nix from Gemfile.lock"
    command -v bundle >/dev/null && bundle lock
    command -v bundix >/dev/null || {
      echo "bundix not found; enter the dev shell (it provides bundix)" >&2
      exit 1
    }
    bundix
    echo ">> Commit the updated gemset.nix."
    ;;
  go)
    if [ -e gomod2nix.toml ]; then
      echo ">> Go: regenerating gomod2nix.toml"
      command -v gomod2nix >/dev/null || {
        echo "gomod2nix not found; enter the dev shell" >&2
        exit 1
      }
      gomod2nix generate
      echo ">> Commit the updated gomod2nix.toml."
    elif ! try_nix_update; then
      echo ">> Go: re-deriving vendorHash for buildGoModule."
      echo "   1) Set vendorHash = lib.fakeHash; in the package.nix"
      echo "   2) nix build .#<name> 2>&1 | grep -A2 'got:'"
      echo "   3) Paste the 'got:' hash back into vendorHash and commit."
      echo "   (Pass the flake attribute as the second argument to use nix-update instead.)"
    fi
    ;;
  rust)
    if try_nix_update; then
      :
    else
      echo ">> Rust (crane): no Nix regeneration needed; crane reads Cargo.lock directly."
      echo "   Just commit the updated Cargo.lock (after your normal 'cargo update')."
      echo "   With rustPlatform.buildRustPackage and cargoHash, re-derive the hash like the"
      echo "   Go flow: set cargoHash = lib.fakeHash;, build, paste the 'got:' hash. Passing the"
      echo "   flake attribute as the second argument lets nix-update do it."
    fi
    ;;
  node)
    if try_nix_update; then
      :
    else
      echo ">> Node: re-deriving the deps hash."
      echo "   buildNpmPackage: set npmDepsHash = lib.fakeHash; build; paste the 'got:' hash."
      echo "   pnpm: set the hash of fetchPnpmDeps to lib.fakeHash; build; paste the 'got:' hash."
      echo "   Then commit the package.nix hash change. (Pass the flake attribute as the"
      echo "   second argument to use nix-update instead.)"
    fi
    ;;
  python)
    echo ">> Python (uv2nix): no Nix regeneration needed; the lockfile is read directly."
    echo "   Commit the updated uv.lock (after 'uv lock')."
    echo "   Poetry projects (commit poetry.lock after 'poetry lock'): poetry2nix is unmaintained,"
    echo "   so keeping it or moving to uv is a decision for the project owner."
    ;;
  *)
    echo "Could not detect a supported lockfile. Pass one of: ruby|go|rust|node|python" >&2
    usage
    exit 1
    ;;
esac
