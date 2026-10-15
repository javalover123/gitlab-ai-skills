#!/usr/bin/env bash
# Run the Nix quality-gate ladder that applies to the current context.
#
#   gates.sh [--context auto|project|nixpkgs|nixos] [--paths PATH...] [--no-build]
#
# Contexts: project (your own flake or non-flake repo), nixpkgs (a nixpkgs checkout),
# nixos (a NixOS system configuration). Without --paths it checks the .nix files you
# changed since HEAD (plus untracked ones); with nothing changed it checks every tracked
# .nix file, except in nixpkgs where it checks only your changes.
#
# Missing tools are SKIPped with an install hint, never silently passed. The summary
# ends with "Gates run:" and "Not run:" lines you can paste into your report. Gates this
# script can't automate (nixpkgs-review, passthru.tests, other platforms) are listed under
# "Not run" so you remember them. Full ladder: references/gates-and-tooling.md.
#
# Exit status: 0 no gate failed, 1 a gate failed, 2 usage error.
# -e is on, so every place that can legitimately fail is a condition or carries `|| rc=$?`:
# a failing gate is recorded and the run continues; it must not abort the script.
set -Eeuo pipefail

SKILL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
context=auto
build=1
paths=()

usage() {
  echo "usage: gates.sh [--context auto|project|nixpkgs|nixos] [--paths PATH...] [--no-build]" >&2
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --context) [ $# -ge 2 ] || usage; context=$2; shift 2 ;;
    --no-build) build=0; shift ;;
    --paths)
      shift
      while [ $# -gt 0 ] && [[ "$1" != --* ]]; do paths+=("$1"); shift; done
      [ ${#paths[@]} -gt 0 ] || usage
      ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
done
case "$context" in auto|project|nixpkgs|nixos) ;; *) usage ;; esac

have() { command -v "$1" >/dev/null 2>&1; }
in_git() { git rev-parse --is-inside-work-tree >/dev/null 2>&1; }

detect_context() {
  if [ -d pkgs/by-name ] && [ -f lib/default.nix ]; then echo nixpkgs
  elif { [ -f flake.nix ] && grep -q nixosConfigurations flake.nix; } || [ -f configuration.nix ]; then echo nixos
  else echo project
  fi
}
[ "$context" = auto ] && context=$(detect_context)
echo "context: $context"

# --- which files are in scope ------------------------------------------------
# Plain here-strings, not process substitution: /dev/fd isn't available in every sandbox.
files=()
add_files() {  # reads newline-separated paths on stdin, keeps the ones that exist
  local f
  while IFS= read -r f; do
    if [ -n "$f" ] && [ -f "$f" ]; then files+=("$f"); fi
  done
}
if [ ${#paths[@]} -gt 0 ]; then
  for p in "${paths[@]}"; do
    if [ -d "$p" ]; then add_files <<< "$(find "$p" -name '*.nix' -not -path '*/.git/*' | sort)"
    elif [ -f "$p" ]; then files+=("$p"); fi
  done
elif in_git; then
  if git rev-parse --verify -q HEAD >/dev/null; then
    add_files <<< "$(git diff --name-only HEAD --diff-filter=ACMR -- '*.nix')"
  fi
  add_files <<< "$(git ls-files --others --exclude-standard -- '*.nix')"
  if [ ${#files[@]} -eq 0 ] && [ "$context" != nixpkgs ]; then
    add_files <<< "$(git ls-files -- '*.nix')"
  fi
else
  add_files <<< "$(find . -name '*.nix' -not -path '*/.git/*' | sort)"
fi
if [ ${#files[@]} -gt 0 ]; then
  sorted=$(printf '%s\n' "${files[@]}" | sort -u)
  files=()
  add_files <<< "$sorted"
fi

# --- result bookkeeping --------------------------------------------------------
ran=()
notrun=()
failed=0
out=$(mktemp)
trap 'rm -f "$out"' EXIT

record_pass() { echo "PASS $1: ${2:-ok}"; ran+=("$1 PASS"); }
record_skip() { echo "SKIP $1: $2"; notrun+=("$1 ($2)"); }
record_fail() {
  echo "FAIL $1: $2"
  sed 's/^/    /' "$out" | tail -n 25
  ran+=("$1 FAIL"); failed=1
}

# Every gate is time-limited so one hung tool (a network fetch, a huge build) can't block
# the whole run. Override with GATE_TIMEOUT=seconds; builds usually need a larger value.
# GNU timeout exits 124 when it fires; BusyBox's exits 143 (SIGTERM), so accept both.
# macOS has no `timeout`; Homebrew coreutils installs it as `gtimeout`. With neither, gates
# run without a limit.
GATE_TIMEOUT=${GATE_TIMEOUT:-900}
TIMEOUT_BIN=$(command -v timeout || command -v gtimeout || true)

# gate NAME DESCRIPTION CMD... : run CMD, record PASS or FAIL
gate() {
  local name=$1 desc=$2 rc=0; shift 2
  if [ -n "$TIMEOUT_BIN" ]; then "$TIMEOUT_BIN" "$GATE_TIMEOUT" "$@" >"$out" 2>&1 || rc=$?; else "$@" >"$out" 2>&1 || rc=$?; fi
  if [ "$rc" -eq 0 ]; then record_pass "$name" "$desc"
  elif [ -n "$TIMEOUT_BIN" ] && { [ "$rc" -eq 124 ] || [ "$rc" -eq 143 ]; }; then
    echo "timed out after ${GATE_TIMEOUT}s (raise GATE_TIMEOUT if this gate is legitimately slow)" >"$out"
    record_fail "$name" "$desc"
  else record_fail "$name" "$desc"; fi
}

if [ ${#files[@]} -eq 0 ]; then
  echo "no .nix files in scope; nothing to check"
  [ "$context" = nixpkgs ] && echo "Not run: everything (no changed .nix files; pass --paths)"
  exit 0
fi
echo "files in scope: ${#files[@]}"

# --- gate 0: grep-level anti-patterns ------------------------------------------
if have python3; then
  gate antipatterns "${#files[@]} file(s) vs review-derived rules" python3 "$SKILL_DIR/scripts/antipatterns.py" "${files[@]}"
else
  record_skip antipatterns "python3 not found"
fi

# --- gate 1: parse ---------------------------------------------------------------
if have nix-instantiate; then
  # Single-quoted on purpose: the inner shell, not this one, expands "$@" and "$f".
  # shellcheck disable=SC2016
  gate parse "nix-instantiate --parse" bash -c 'for f in "$@"; do nix-instantiate --parse "$f" >/dev/null || exit 1; done' _ "${files[@]}"
else
  record_skip parse "nix-instantiate not found (install Nix)"
fi

# --- gate 2: format --------------------------------------------------------------
if have nixfmt; then
  gate format "nixfmt --check" nixfmt --check "${files[@]}"
else
  record_skip format "nixfmt not found (try: nix shell nixpkgs#nixfmt)"
fi

# --- gate 3: diagnostics (own projects; nixpkgs CI uses nixf-diagnose via treefmt) -
if [ "$context" != nixpkgs ]; then
  if have statix; then gate statix "statix check" statix check "${files[@]}" ; else record_skip statix "statix not found (nix shell nixpkgs#statix)"; fi
  if have deadnix; then gate deadnix "deadnix --fail" deadnix --fail "${files[@]}" ; else record_skip deadnix "deadnix not found (nix shell nixpkgs#deadnix)"; fi
fi

# --- gate 4/6: eval and build, per context ---------------------------------------
pkg_names() {
  local f
  for f in "${files[@]}"; do
    if [[ "$f" =~ pkgs/by-name/[^/]+/([^/]+)/ ]]; then echo "${BASH_REMATCH[1]}"; fi
  done | sort -u
}

case "$context" in
  project)
    if [ -f flake.nix ]; then
      if have nix; then
        gate eval "nix flake check --no-build --all-systems" nix flake check --no-build --all-systems
        if [ "$build" = 1 ]; then gate build "nix flake check (builds checks)" nix flake check -L
        else record_skip build "--no-build"; fi
      else record_skip eval "nix not found"; record_skip build "nix not found"; fi
    else
      record_skip eval "non-flake project: run nix-instantiate --show-trace -A <attr> yourself"
      record_skip build "non-flake project: run nix-build -A <attr> yourself"
    fi
    ;;
  nixpkgs)
    pkgs=()
    while IFS= read -r p; do [ -n "$p" ] && pkgs+=("$p"); done <<< "$(pkg_names)"
    if [ ${#pkgs[@]} -eq 0 ]; then
      record_skip eval "no pkgs/by-name package changed (module or other change: evaluate it by hand)"
      record_skip build "no pkgs/by-name package changed"
    else
      for p in "${pkgs[@]}"; do
        if have nix-instantiate; then gate "eval $p" "nix-instantiate -A $p" nix-instantiate -A "$p" --quiet; else record_skip "eval $p" "nix-instantiate not found"; fi
      done
      if [ "$build" = 1 ]; then
        for p in "${pkgs[@]}"; do
          if have nix-build; then gate "build $p" "nix-build -A $p" nix-build -A "$p" --no-out-link; else record_skip "build $p" "nix-build not found"; fi
        done
      else record_skip build "--no-build"; fi
      for p in "${pkgs[@]}"; do
        if have nix-instantiate; then
          gate "meta $p" "meta evaluates" nix-instantiate --eval --strict --json -A "$p.meta"
        fi
      done
    fi
    if [ "$build" = 0 ]; then
      record_skip "by-name vet" "--no-build (ci/nixpkgs-vet.sh fetches the base branch from GitHub and builds worktrees)"
    elif [ -x ci/nixpkgs-vet.sh ]; then
      gate "by-name vet" "ci/nixpkgs-vet.sh ${BASE_REF:-master}" ./ci/nixpkgs-vet.sh "${BASE_REF:-master}"
    else
      record_skip "by-name vet" "ci/nixpkgs-vet.sh not found"
    fi
    ;;
  nixos)
    if have nix && [ -f flake.nix ]; then
      hosts=$(nix eval --json .#nixosConfigurations --apply builtins.attrNames 2>/dev/null | tr -d '[]" ' | tr ',' ' ')
      if [ -z "$hosts" ]; then
        record_skip eval "no nixosConfigurations found"
      else
        for h in $hosts; do
          gate "eval $h" "toplevel drvPath" nix eval ".#nixosConfigurations.$h.config.system.build.toplevel.drvPath"
          if [ "$build" = 1 ]; then
            gate "dry-build $h" "nix build --dry-run" nix build --dry-run ".#nixosConfigurations.$h.config.system.build.toplevel"
          fi
        done
        [ "$build" = 1 ] || record_skip build "--no-build"
      fi
    else
      record_skip eval "needs nix and a flake.nix (non-flake: nixos-rebuild dry-build)"
    fi
    ;;
esac

# --- gates a script can't automate -------------------------------------------------
case "$context" in
  nixpkgs) notrun+=("manual: passthru.tests / nixosTests" "manual: nixpkgs-review wip" "manual: build on each platform in meta.platforms") ;;
  project) notrun+=("manual: tests you wrote (nix flake check covers checks only)" "manual: run the built program once") ;;
  nixos) notrun+=("manual: boot the config in a VM (nixos-rebuild build-vm) before switching") ;;
esac

echo
echo "Gates run:   ${ran[*]:-none}"
echo "Not run:     ${notrun[*]:-none}"
exit "$failed"
