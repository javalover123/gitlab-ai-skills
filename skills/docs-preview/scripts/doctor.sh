#!/usr/bin/env bash
# Preflight for a local docs.gitlab.com preview. Read-only: prints OK, WARN, or
# FAIL per check with the fix, and changes nothing.
#
# Usage: doctor.sh <docs-gitlab-com dir> [mount name] [port]
#   mount name  the sibling directory Hugo mounts for your project, for example
#               gitlab, gitlab-runner, cli (see config/_default/hugo.yaml)
#   port        preview port (default 1313)
# Example: doctor.sh ~/src/docs-site/docs-gitlab-com gitlab-runner
# Exit: 0 no FAIL, 1 at least one FAIL, 2 usage error.
set -Eeuo pipefail
case "${1:-}" in -h | --help)
  sed -n '2,/^[^#]/{/^#/s/^# \{0,1\}//p;}' "$0"
  exit 0
  ;;
esac
trap 'echo "doctor: error on line $LINENO" >&2' ERR

if [[ $# -lt 1 ]]; then
    sed -n '5,10p' "$0" >&2
    exit 2
fi
dgc=$1 mount=${2:-} port=${3:-1313}
fails=0
ok() { echo "OK   $*"; }
warn() { echo "WARN $*"; }
fail() { echo "FAIL $*"; fails=$((fails + 1)); }

if [[ ! -f $dgc/config/_default/hugo.yaml ]]; then
    fail "$dgc is not a docs-gitlab-com checkout (no config/_default/hugo.yaml)." \
        "Clone https://gitlab.com/gitlab-org/technical-writing/docs-gitlab-com.git"
    exit 1
fi
dgc=$(CDPATH='' cd -- "$dgc" && pwd)
parent=$(dirname "$dgc")
ok "docs-gitlab-com at $dgc"

# 1. Checkout freshness: an old clone builds an old side nav.
if command -v git >/dev/null 2>&1 && git -C "$dgc" rev-parse --git-dir >/dev/null 2>&1; then
    branch=$(git -C "$dgc" branch --show-current || true)
    age=$(git -C "$dgc" log -1 --format=%cr 2>/dev/null || echo unknown)
    dirty=$(git -C "$dgc" status --porcelain --untracked-files=no | wc -l | tr -d ' ')
    msg="docs-gitlab-com on '${branch:-detached}', last commit $age, $dirty changed files"
    if [[ $branch != main ]]; then
        warn "$msg. Previews usually build from main."
    else
        ok "$msg. Update with: git -C $dgc pull (only if the changes are yours to drop)"
    fi
else
    warn "cannot read git state of $dgc (git missing or not a clone)"
fi

# 2. mise: installs Hugo, Go, and Node at the versions docs-gitlab-com pins.
if command -v mise >/dev/null 2>&1; then
    ok "mise $(mise --version 2>/dev/null | awk '{print $1}'). If tool installs fail with 'no asset found', upgrade mise."
    echo "     Run mise inside docs-gitlab-com with: MISE_CEILING_PATHS=$parent MISE_TRUSTED_CONFIG_PATHS=$dgc mise exec -- <cmd>"
else
    warn "mise not found. Install it, or install the tools in $dgc/mise.toml yourself."
fi

# 3. Yarn: the site pins Yarn 4 through packageManager; a global Yarn 1 breaks installs.
want=$(sed -n 's/.*"packageManager": *"yarn@\([0-9][0-9]*\).*/\1/p' "$dgc/package.json" | head -1)
if ! have=$(cd "$dgc" 2>/dev/null && yarn --version 2>/dev/null); then
    have=""
fi
if [[ -z $want ]]; then
    warn "package.json has no yarn packageManager entry; skipping the Yarn check"
elif [[ -z $have ]]; then
    warn "yarn not found. Enable it with: corepack enable --install-directory <dir on PATH> yarn"
elif [[ ${have%%.*} != "$want" ]]; then
    fail "yarn $have, but package.json wants yarn $want. Put an existing Yarn $want shim directory first on PATH, or create one: corepack enable --install-directory <dir> yarn"
else
    ok "yarn $have"
fi

# 4. Port: Hugo silently picks a random port when the default is taken.
if command -v lsof >/dev/null 2>&1; then
    holder=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR == 2 {print $1 " pid " $2}' || true)
    if [[ -n $holder ]]; then
        warn "port $port is in use by $holder. Reuse that server, or stop it if you started it."
    else
        ok "port $port is free"
    fi
else
    warn "lsof not found; cannot check whether port $port is free"
fi

# 5. Mount: Hugo skips a missing mount source without an error, so the section is just absent.
if [[ -n $mount ]]; then
    if ! grep -qE "source: *['\"]?\.\./$mount(/|['\"]|$)" "$dgc/config/_default/hugo.yaml"; then
        fail "hugo.yaml has no mount with source ../$mount/. List mounts with: grep -n 'source: ../' $dgc/config/_default/hugo.yaml"
    elif [[ ! -e $parent/$mount ]]; then
        fail "$parent/$mount does not exist. Clone your project there or symlink it: ln -sfn <your checkout> $parent/$mount"
    else
        ok "$parent/$mount -> $(CDPATH='' cd -- "$parent/$mount" && pwd -P)"
    fi
fi

# 6. Nav data: the sidebar reads page-metadata.json, which Hugo does not regenerate.
meta=$dgc/data/en-us/page-metadata.json nav=$dgc/data/en-us/navigation.yaml
if [[ ! -f $meta ]]; then
    warn "no $meta yet. make view creates it; after nav edits run scripts/regen-nav-data.sh"
elif [[ $nav -nt $meta ]]; then
    warn "navigation.yaml is newer than page-metadata.json. Run scripts/regen-nav-data.sh $dgc"
else
    ok "page-metadata.json is newer than navigation.yaml"
fi

echo "doctor: $fails failure(s)"
if [[ $fails -gt 0 ]]; then exit 1; fi
