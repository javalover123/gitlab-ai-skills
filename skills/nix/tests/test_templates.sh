#!/usr/bin/env bash
# Parse and evaluate every template under assets/templates.
#
# Every *.nix file must parse (nix-instantiate --parse). Where a template can
# run, it's also evaluated for real against a local nixpkgs tree:
#   - callPackage templates: reach `.drvPath` with checkMeta on, plus a few
#     assertions on the attributes reviewers ask for;
#   - the flake templates: copied to a temp dir and checked with
#     `nix flake check --no-build` and `nix eval`, with nixpkgs overridden to
#     the local tree.
# Output is one PASS, FAIL, or SKIP line per check. The exit status is 1 when
# any check fails; a SKIP (missing tool, missing tree, no network) isn't a failure.
#
# Needs no network and no credentials by default. Without Nix on PATH the whole
# suite skips (exit 0); without a nixpkgs checkout only the parse checks run.
#
# Usage: bash tests/test_templates.sh
#   NIXPKGS_TREE   nixpkgs checkout to evaluate against. If unset, a locally cached
#                  nixpkgs is used when one can be found offline.
#   TEMPLATES_DIR  template tree to check (default: assets/templates)
#   ALLOW_NETWORK=1  also run the flake checks that fetch inputs (treefmt-nix, flake-parts)

set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TPL="${TEMPLATES_DIR:-$SKILL_DIR/assets/templates}"
NIXPKGS_TREE="${NIXPKGS_TREE:-}"

# <nixpkgs> lookups would hide a template that depends on the caller's channel.
export NIX_PATH=

PASS=0
FAIL=0
SKIP=0

pass() { PASS=$((PASS + 1)); printf 'PASS  %s\n' "$1"; }
skip() { SKIP=$((SKIP + 1)); printf 'SKIP  %s: %s\n' "$1" "$2"; }
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL  %s\n' "$1"
  if [ -n "${2:-}" ]; then
    printf '%s\n' "$2" | grep -v '^warning:' | head -n 12 | sed 's/^/        /'
  fi
}

have() { command -v "$1" >/dev/null 2>&1; }

if ! have nix-instantiate; then
  skip "all templates" "nix-instantiate not found on PATH"
  printf '\n%d passed, %d failed, %d skipped\n' "$PASS" "$FAIL" "$SKIP"
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# No tree given: ask Nix for a nixpkgs it already has (registry entry or flake input
# in the store). --offline means this never downloads; it just fails when none is cached.
if [ -z "$NIXPKGS_TREE" ] && have nix; then
  NIXPKGS_TREE="$(nix --extra-experimental-features 'nix-command flakes' --offline \
    eval --raw nixpkgs#path 2>/dev/null || true)"
fi

TREE_OK=0
if [ -f "$NIXPKGS_TREE/default.nix" ] && [ -d "$NIXPKGS_TREE/lib" ]; then TREE_OK=1; fi

# Run a command and record PASS or FAIL for the named check. Output is kept for
# the failure report.
run() { # name cmd...
  local name="$1" out
  shift
  if out="$("$@" 2>&1)"; then pass "$name"; else fail "$name" "$out"; fi
}

# Evaluate a Nix expression to a raw string; the check passes when evaluation
# succeeds. Reading `.drvPath` forces the derivation without building it.
eval_expr() { # name expr
  run "$1" nix-instantiate --eval --raw --expr "$2"
}

NIX_FLAKE=(nix --extra-experimental-features "nix-command flakes")

# Run a command, keeping stdout in OUT and stderr in ERR. Flake commands print
# progress to stderr, so comparing stdout alone keeps those lines out of the way.
capture() {
  OUT="$("$@" 2>"$TMP/stderr")"
  ERR="$(cat "$TMP/stderr")"
}

# nixpkgs imported without user config. checkMeta validates meta attribute types.
PKGS="import \"$NIXPKGS_TREE\" { config = { checkMeta = true; }; overlays = []; }"

rel() { printf '%s' "${1#"$TPL"/}"; }

network_ok() {
  [ "${ALLOW_NETWORK:-0}" = 1 ] || return 1
  if [ -z "${_NET:-}" ]; then
    if timeout 25 "${NIX_FLAKE[@]}" flake metadata --json github:numtide/treefmt-nix >/dev/null 2>&1; then
      _NET=yes
    else
      _NET=no
    fi
  fi
  [ "$_NET" = yes ]
}

# ---------------------------------------------------------------------------
# 1. Parse every .nix file.
# ---------------------------------------------------------------------------
find "$TPL" -name '*.nix' | sort >"$TMP/nix-files"
while IFS= read -r f; do
  run "parse $(rel "$f")" nix-instantiate --parse "$f"
done <"$TMP/nix-files"

if [ "$TREE_OK" -eq 0 ]; then
  skip "evaluation checks" "no nixpkgs checkout (set NIXPKGS_TREE to one)"
  printf '\n%d passed, %d failed, %d skipped\n' "$PASS" "$FAIL" "$SKIP"
  [ "$FAIL" -eq 0 ]
  exit $?
fi

# ---------------------------------------------------------------------------
# 2. callPackage templates.
# ---------------------------------------------------------------------------

# by-name package templates: evaluate, then check the attributes a reviewer
# looks for first.
for f in package.nix package-python.nix package-go.nix package-rust.nix; do
  eval_expr "eval nixpkgs/$f (callPackage, checkMeta)" "
    let
      pkgs = $PKGS;
      d = pkgs.callPackage $TPL/nixpkgs/$f { };
    in
    assert d.meta ? description && d.meta ? license && d.meta ? mainProgram
      && d.meta ? changelog && d.meta ? homepage;
    assert d ? updateScript;
    assert d.version != \"\" && d.pname != \"\";
    d.drvPath"
done

# Non-flake-scope pkgs/ examples. Each takes only nixpkgs arguments.
for f in go-service c-tool node-frontend; do
  eval_expr "eval pkgs/$f (callPackage)" "
    let pkgs = $PKGS; in (pkgs.callPackage $TPL/pkgs/$f/package.nix { }).drvPath"
done

skip "eval pkgs/rust-app" "needs craneLib and rustToolchain from crane and rust-overlay flake inputs"
skip "eval pkgs/python-app" "needs a uv2nix pythonSet and workspace from flake inputs"
skip "eval pkgs/app-image" "needs the nix2container flake input"
skip "eval pkgs/ruby-app" "bundlerEnv reads Gemfile.lock and gemset.nix from the real project"

eval_expr "eval shells/default.nix (callPackage)" "
  let pkgs = $PKGS; in (pkgs.callPackage $TPL/shells/default.nix { }).drvPath"

# A VM test needs a Linux builder to evaluate its node closure.
if [ "$(uname -s)" = Linux ]; then
  eval_expr "eval checks/integration.nix (testers.runNixOSTest)" "
    let pkgs = $PKGS; in
    (pkgs.callPackage $TPL/checks/integration.nix { myapp = pkgs.hello; }).drvPath"
else
  skip "eval checks/integration.nix" "NixOS VM tests evaluate on Linux only"
fi

eval_expr "eval lib/eachSystem.nix" "
  let
    lib = (import \"$NIXPKGS_TREE/lib\");
    eachSystem = import $TPL/lib/eachSystem.nix { inherit lib; systems = [ \"a\" \"b\" ]; };
    r = eachSystem (s: s + \"!\");
  in
  assert r == { a = \"a!\"; b = \"b!\"; };
  \"ok\""

eval_expr "eval non-flake/shell.nix (sources stubbed with the local tree)" "
  (import $TPL/non-flake/shell.nix {
    sources.nixpkgs = $NIXPKGS_TREE;
    system = builtins.currentSystem;
  }).drvPath"

# ---------------------------------------------------------------------------
# 3. NixOS module and its test.
# ---------------------------------------------------------------------------
if [ "$(uname -s)" = Linux ]; then
  HOST='{ pkgs, ... }: {
      imports = [ '"$TPL"'/nixpkgs/module.nix ];
      system.stateVersion = "26.05";
      boot.loader.grub.devices = [ "nodev" ];
      fileSystems."/" = { device = "/dev/disk/by-label/nixos"; fsType = "ext4"; };
      services.example.package = pkgs.hello;
    }'

  nixos_eval() { # extra-config -> expression reaching the toplevel drvPath
    cat <<EOF
let
  system = builtins.currentSystem;
  eval = import "$NIXPKGS_TREE/nixos" {
    inherit system;
    configuration = { pkgs, lib, ... }: {
      imports = [ ($HOST) ({ ... }: { $1 }) ];
    };
  };
in
$2
EOF
  }

  eval_expr "eval nixpkgs/module.nix (enabled, default settings)" \
    "$(nixos_eval 'services.example.enable = true;' 'eval.config.system.build.toplevel.drvPath')"

  eval_expr "eval nixpkgs/module.nix (tokenFile, openFirewall, extraArgs)" \
    "$(nixos_eval 'services.example = { enable = true; tokenFile = "/run/secrets/example-token"; openFirewall = true; extraArgs = [ "--verbose" ]; };' \
      'assert builtins.elem 8080 eval.config.networking.firewall.allowedTCPPorts;
       assert eval.config.systemd.services.example.serviceConfig.LoadCredential == [ "token:/run/secrets/example-token" ];
       eval.config.system.build.toplevel.drvPath')"

  eval_expr "eval nixpkgs/module.nix (disabled module evaluates and adds no unit)" \
    "$(nixos_eval '' 'assert !(eval.config.systemd.services ? example); eval.config.system.build.toplevel.drvPath')"

  # The assertion must fire: user without password_file is a failed assertion.
  capture nix-instantiate --eval --raw --expr "$(nixos_eval \
    'services.example = { enable = true; settings.user = "a"; };' \
    'if (builtins.tryEval eval.config.system.build.toplevel.drvPath).success then "evaluated" else "rejected"')"
  if [ "$OUT" = "rejected" ]; then
    pass "module assertion rejects settings.user without settings.password_file"
  else
    fail "module assertion rejects settings.user without settings.password_file" "toplevel $OUT${ERR:+: $ERR}"
  fi

  eval_expr "eval nixpkgs/nixos-test.nix (testers.runNixOSTest with the module)" "
    let
      pkgs = $PKGS;
    in
    (pkgs.testers.runNixOSTest {
      imports = [ $TPL/nixpkgs/nixos-test.nix ];
      nodes.machine =
        { pkgs, ... }:
        {
          imports = [ $TPL/nixpkgs/module.nix ];
          services.example.package = pkgs.hello;
        };
    }).drvPath"
else
  skip "eval nixpkgs/module.nix and nixos-test.nix" "NixOS evaluation needs Linux"
fi

# ---------------------------------------------------------------------------
# 4. envrc: watch_file must come before use flake.
# ---------------------------------------------------------------------------
envrc_order="$(grep -n -E '^(watch_file|use flake)' "$TPL/envrc" | head -n 50)"
first_use="$(printf '%s\n' "$envrc_order" | grep -m1 'use flake' | cut -d: -f1)"
last_watch="$(printf '%s\n' "$envrc_order" | grep 'watch_file' | tail -n 1 | cut -d: -f1)"
if [ -n "$first_use" ] && [ -n "$last_watch" ] && [ "$last_watch" -lt "$first_use" ]; then
  pass "envrc: every watch_file precedes use flake"
else
  fail "envrc: every watch_file precedes use flake" "$envrc_order"
fi

# ---------------------------------------------------------------------------
# 5. Flake templates, evaluated in temp copies with nixpkgs overridden to the
#    local tree.
# ---------------------------------------------------------------------------
if ! have git; then
  skip "flake templates" "git not found (needed to use the nixpkgs tree as a flake input)"
else
  TREE_FLAKE="git+file://$NIXPKGS_TREE"
  [ -d "$NIXPKGS_TREE/.git" ] || TREE_FLAKE="path:$NIXPKGS_TREE"
  SYSTEM="$(nix-instantiate --eval --raw --expr builtins.currentSystem 2>/dev/null)"

  # nixos/flake.nix: nixpkgs is its only input, so this check stays offline.
  d="$TMP/nixos"
  mkdir -p "$d"
  cp "$TPL/nixos/flake.nix" "$d/flake.nix"
  run "flake nixos/flake.nix: nix flake check --no-build" \
    "${NIX_FLAKE[@]}" flake check --no-build --all-systems --no-write-lock-file \
    --override-input nixpkgs "$TREE_FLAKE" "$d"
  run "flake nixos/flake.nix: toplevel is exposed as a check" \
    "${NIX_FLAKE[@]}" eval --raw --no-write-lock-file --override-input nixpkgs "$TREE_FLAKE" \
    "$d#checks.x86_64-linux.example.drvPath"

  # flake.nix and friends need the treefmt-nix input from the network.
  if network_ok; then
    d="$TMP/thin"
    mkdir -p "$d/pkgs/example" "$d/pkgs/consumer"
    cp "$TPL/flake.nix" "$TPL/treefmt.nix" "$d/"
    cp -r "$TPL/lib" "$TPL/shells" "$TPL/checks" "$d/"
    # One real package plus a sibling that takes it as an argument, to prove
    # the overlay resolves pkgs/ entries by name.
    cp "$TPL/nixpkgs/package.nix" "$d/pkgs/example/package.nix"
    # Name the package the flake exposes the same as the sibling's argument.
    sed -i.bak 's/pname = "foo"/pname = "example"/; s/mainProgram = "foo"/mainProgram = "example"/' \
      "$d/pkgs/example/package.nix"
    rm -f "$d/pkgs/example/package.nix.bak"
    cat >"$d/pkgs/consumer/package.nix" <<'EOF'
{ runCommand, example }:
runCommand "consumer" { } "echo ${example} > $out"
EOF
    OV=(--no-write-lock-file --override-input nixpkgs "$TREE_FLAKE")

    run "flake flake.nix: nix flake check --no-build" \
      "${NIX_FLAKE[@]}" flake check --no-build "${OV[@]}" "$d"

    capture "${NIX_FLAKE[@]}" eval --json "${OV[@]}" "$d#packages.$SYSTEM" --apply builtins.attrNames
    if [ "$OUT" = '["consumer","example"]' ]; then
      pass "flake flake.nix: packages holds only the autoloaded packages (no scope attributes)"
    else
      fail "flake flake.nix: packages holds only the autoloaded packages (no scope attributes)" "$OUT${ERR:+
$ERR}"
    fi

    capture "${NIX_FLAKE[@]}" eval --raw "${OV[@]}" "$d#packages.$SYSTEM.consumer.drvPath"
    case "$OUT" in
      /nix/store/*-consumer.drv) pass "flake flake.nix: sibling package resolves through the overlay" ;;
      *) fail "flake flake.nix: sibling package resolves through the overlay" "$OUT${ERR:+
$ERR}" ;;
    esac

    # Applied with a stub callPackage so only the names it defines show up.
    capture "${NIX_FLAKE[@]}" eval --json "${OV[@]}" "$d#overlays.default" \
      --apply 'o: builtins.attrNames (o { callPackage = _: _; } { })'
    if [ "$OUT" = '["consumer","example"]' ]; then
      pass "flake flake.nix: overlay adds only package names"
    else
      fail "flake flake.nix: overlay adds only package names" "$OUT${ERR:+
$ERR}"
    fi

    run "flake flake.nix: devShells.default evaluates" \
      "${NIX_FLAKE[@]}" eval --raw "${OV[@]}" "$d#devShells.$SYSTEM.default.drvPath"
    run "flake flake.nix + treefmt.nix: formatter evaluates" \
      "${NIX_FLAKE[@]}" eval --raw "${OV[@]}" "$d#formatter.$SYSTEM.drvPath"

    # treefmt.nix mentions programs in comments; each must exist upstream.
    tf_src="$("${NIX_FLAKE[@]}" flake metadata --json github:numtide/treefmt-nix 2>/dev/null |
      python3 -c 'import json,sys; print(json.load(sys.stdin)["path"])' 2>/dev/null)"
    if [ -n "$tf_src" ] && [ -d "$tf_src/programs" ]; then
      missing=""
      grep -oE '^[[:space:]]*(# )?[a-z0-9-]+\.enable' "$TPL/treefmt.nix" |
        sed -E 's/^[[:space:]]*(# )?//; s/\.enable$//' >"$TMP/treefmt-programs" || true
      while IFS= read -r p; do
        [ -f "$tf_src/programs/$p.nix" ] || missing="$missing $p"
      done <"$TMP/treefmt-programs"
      if [ -z "$missing" ]; then
        pass "treefmt.nix: every program named in it exists in treefmt-nix"
      else
        fail "treefmt.nix: every program named in it exists in treefmt-nix" "missing:$missing"
      fi
    else
      skip "treefmt.nix program names" "could not locate the treefmt-nix source"
    fi

    # The integration check is commented out in flake.nix; evaluate the wired-in form.
    d2="$TMP/thin-integration"
    mkdir -p "$d2"
    cp -r "$d/." "$d2/"
    cp "$TPL/nixpkgs/package.nix" "$d2/pkgs/example/package.nix"
    sed -i.bak 's/pname = "foo"/pname = "myapp"/; s/mainProgram = "foo"/mainProgram = "myapp"/' \
      "$d2/pkgs/example/package.nix"
    rm -f "$d2/pkgs/example/package.nix.bak"
    mv "$d2/pkgs/example" "$d2/pkgs/myapp"
    rm -rf "$d2/pkgs/consumer"
    sed -i.bak 's|# integration = pkgs.callPackage|integration = pkgs.callPackage|' "$d2/flake.nix"
    rm -f "$d2/flake.nix.bak"
    if [ "$(uname -s)" = Linux ]; then
      run "flake flake.nix: checks.integration (uncommented) evaluates" \
        "${NIX_FLAKE[@]}" eval --raw "${OV[@]}" "$d2#checks.$SYSTEM.integration.drvPath"
    else
      skip "flake flake.nix: checks.integration" "NixOS VM tests evaluate on Linux only"
    fi

    # The commented nix2container overlay in flake.nix: enable it exactly as its comment
    # says, then pkgs/app-image must resolve `nix2container` by name.
    if have python3; then
      d4="$TMP/n2c"
      mkdir -p "$d4/pkgs/myapp" "$d4/pkgs/app-image"
      cp "$TPL/flake.nix" "$TPL/treefmt.nix" "$d4/"
      cp -r "$TPL/lib" "$TPL/shells" "$d4/"
      cp "$TPL/pkgs/app-image/package.nix" "$d4/pkgs/app-image/package.nix"
      cp "$TPL/nixpkgs/package.nix" "$d4/pkgs/myapp/package.nix"
      sed -i.bak 's/pname = "foo"/pname = "myapp"/; s/mainProgram = "foo"/mainProgram = "myapp"/' \
        "$d4/pkgs/myapp/package.nix"
      rm -f "$d4/pkgs/myapp/package.nix.bak"
      python3 - "$d4/flake.nix" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
text = text.replace("    treefmt-nix = {", "    nix2container = {\n      url = \"github:nlewo/nix2container\";\n      inputs.nixpkgs.follows = \"nixpkgs\";\n    };\n    treefmt-nix = {", 1)
text = text.replace("      nixpkgs,\n      treefmt-nix,\n", "      nixpkgs,\n      nix2container,\n      treefmt-nix,\n", 1)
text = text.replace("            # pkgs/app-image/package.nix takes it as an argument.\n",
                    "            (_final: _prev: {\n              inherit (nix2container.packages.${system}) nix2container;\n            })\n", 1)
open(path, "w").write(text)
PY
      run "flake flake.nix: enabling the nix2container overlay lets pkgs/app-image resolve it" \
        "${NIX_FLAKE[@]}" eval --raw "${OV[@]}" "$d4#packages.$SYSTEM.app-image.drvPath"
    else
      skip "flake flake.nix: nix2container overlay" "python3 not found"
    fi

    # flake-parts.nix pulls in four more inputs.
    d3="$TMP/parts"
    mkdir -p "$d3/pkgs/by-name/ex/example"
    cp "$TPL/flake-parts.nix" "$d3/flake.nix"
    cp "$TPL/nixpkgs/package.nix" "$d3/pkgs/by-name/ex/example/package.nix"
    run "flake flake-parts.nix: nix flake check --no-build" \
      "${NIX_FLAKE[@]}" flake check --no-build "${OV[@]}" "$d3"
  else
    skip "flake flake.nix (thin template)" "needs the network for the treefmt-nix input"
    skip "flake treefmt.nix" "needs the network for treefmt-nix"
    skip "flake flake-parts.nix" "needs the network for flake-parts and friends"
  fi
fi

printf '\n%d passed, %d failed, %d skipped\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -eq 0 ]
