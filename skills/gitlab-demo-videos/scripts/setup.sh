#!/usr/bin/env bash
# Restore the GitLab demo-video kit into a working directory.
#
#   bash <skill-dir>/scripts/setup.sh [TARGET_DIR] [--gitlab-tag TAG]
#
# TARGET_DIR defaults to $PWD/gitlab-demo. --gitlab-tag (or GL_TAG=<tag>) picks the GitLab release whose
# frontend source the pages are built from, e.g. v18.11.2-ee, or master for the newest unreleased code. It
# rewrites TARGET_DIR/gl-src.pin, so later runs in that folder keep the same version. Default: kit/gl-src.pin.
#
# Idempotent: every step checks whether it is already done, so re-running after a failure
# only does the missing work. Works in Claude Code cloud sessions and on local macOS/Linux.
# Env knobs: SKIP_NARRATION=1 (no TTS install; silent videos only), KOKORO_MODEL=int8 (92 MB model instead of 326 MB),
#            WITH_PIPER=1 (also install the Piper TTS fallback), FORCE_CSS=1 (recompile GitLab CSS),
#            SKIP_BROWSER_INSTALL=1 (never download Playwright's Chromium).
# Details: references/setup.md
set -Eeuo pipefail
trap 'echo "setup.sh failed at line $LINENO; fix the cause and re-run (finished steps are skipped)" >&2' ERR

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIT="$SKILL_DIR/kit"
GL_TAG_OVERRIDE="${GL_TAG:-}"
TARGET=""
while [ $# -gt 0 ]; do
  case "$1" in
    --gitlab-tag)
      [ $# -ge 2 ] || { echo "--gitlab-tag needs a value, for example v19.4.1-ee" >&2; exit 1; }
      GL_TAG_OVERRIDE="$2"
      shift 2
      ;;
    --gitlab-tag=*) GL_TAG_OVERRIDE="${1#--gitlab-tag=}"; shift ;;
    -h | --help) sed -n '2,14p' "${BASH_SOURCE[0]}"; exit 0 ;;
    -*) echo "unknown option: $1 (see --help)" >&2; exit 1 ;;
    *) TARGET="$1"; shift ;;
  esac
done
TARGET="${TARGET:-$PWD/gitlab-demo}"
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"
log() { printf '\n== %s\n' "$*"; }

for tool in git node npm python3 curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "missing required tool: $tool (see references/setup.md)" >&2; exit 1; }
done

# ---------------------------------------------------------------- 1. kit sources
log "1/7 kit sources -> $TARGET"
if [ "$KIT" != "$TARGET" ]; then
  # Copy file by file and never overwrite, so local edits survive a re-run (portable: no GNU cp flags).
  (cd "$KIT" && find . -type f) | while IFS= read -r f; do
    if [ ! -e "$TARGET/$f" ]; then
      mkdir -p "$(dirname "$TARGET/$f")"
      cp "$KIT/$f" "$TARGET/$f"
    fi
  done
fi
chmod +x "$TARGET/narration/setup.sh"
repo="" tag="" commit=""
# shellcheck disable=SC1091  # sets repo, tag, commit
. "$TARGET/gl-src.pin"
if [ -z "$repo" ] || [ -z "$tag" ]; then echo "gl-src.pin must set repo and tag" >&2; exit 1; fi
if [ -n "$GL_TAG_OVERRIDE" ] && [ "$GL_TAG_OVERRIDE" != "$tag" ]; then
  case "$GL_TAG_OVERRIDE" in
    *[!A-Za-z0-9._/-]*) echo "not a valid GitLab tag or branch: $GL_TAG_OVERRIDE" >&2; exit 1 ;;
  esac
  # Another GitLab release: no pinned commit to compare against, so the commit check below is skipped.
  tag="$GL_TAG_OVERRIDE"
  commit=""
  printf 'repo=%s\ntag=%s\ncommit=\n' "$repo" "$tag" > "$TARGET/gl-src.pin"
  echo "GitLab version: $tag (written to $TARGET/gl-src.pin)"
fi

# ---------------------------------------------------------------- 2. playwright
log "2/7 playwright"
NODE_ROOT="$(npm root -g 2>/dev/null || true)"
if [ -n "${PLAYWRIGHT_NODE_ROOT:-}" ] && [ -d "$PLAYWRIGHT_NODE_ROOT/playwright" ]; then
  echo "playwright: $PLAYWRIGHT_NODE_ROOT/playwright"
elif [ -d "$NODE_ROOT/playwright" ]; then
  # Cloud sessions usually ship a global Playwright with browsers already installed.
  echo "playwright: $NODE_ROOT/playwright  browsers: ${PLAYWRIGHT_BROWSERS_PATH:-default}"
elif [ -d "$TARGET/tools/playwright/node_modules/playwright" ]; then
  echo "playwright: $TARGET/tools/playwright/node_modules/playwright"
else
  # Its own prefix, so a later `npm install` in app/ never prunes it.
  echo "no Playwright found; installing it into tools/playwright"
  mkdir -p "$TARGET/tools/playwright"
  npm install --prefix "$TARGET/tools/playwright" --no-audit --no-fund --loglevel=error playwright@1.56.1
  if [ "${SKIP_BROWSER_INSTALL:-0}" != 1 ]; then
    (cd "$TARGET/tools/playwright" && npx playwright install chromium)
  fi
fi

# ---------------------------------------------------------------- 3. gl-src sparse checkout
log "3/7 gl-src: sparse, blobless checkout of gitlab-org/gitlab @ $tag"
GL="$TARGET/gl-src"
checked_out=""
[ -f "$GL/.git/demo-checkout-ok" ] && checked_out="$(cat "$GL/.git/demo-checkout-ok")"
if [ "$checked_out" != "$tag" ] || ! cmp -s "$TARGET/gl-src.sparse-checkout" "$GL/.git/info/sparse-checkout"; then
  if [ ! -d "$GL/.git" ]; then
    # Never a full clone: no blobs up front, depth 1, only the tag.
    git clone --filter=blob:none --no-checkout --depth 1 --branch "$tag" "$repo" "$GL"
    ref="$tag"
  else
    # Existing checkout (maybe of another tag): fetch just this tag or branch, still shallow and blobless.
    git -C "$GL" fetch --filter=blob:none --depth 1 origin "$tag"
    ref="FETCH_HEAD"
  fi
  git -C "$GL" sparse-checkout init --no-cone
  # non-cone patterns (some use globs such as page_bundles/profile*)
  cp "$TARGET/gl-src.sparse-checkout" "$GL/.git/info/sparse-checkout"
  # populate the worktree; blobs for matching paths are fetched on demand in batches
  git -C "$GL" checkout -f "$ref"
  printf '%s\n' "$tag" > "$GL/.git/demo-checkout-ok"
fi
got="$(git -C "$GL" rev-parse HEAD)"
if [ -n "$commit" ] && [ "$got" != "$commit" ]; then echo "WARN: gl-src HEAD $got != pinned $commit"; fi
# GitLab's tailwind config and the Sass load paths resolve packages from gl-src/node_modules
[ -e "$GL/node_modules" ] || [ -L "$GL/node_modules" ] || ln -s ../app/node_modules "$GL/node_modules"
echo "gl-src: $(du -sh "$GL" | cut -f1)"

# ---------------------------------------------------------------- 4. npm deps
log "4/7 npm install (app/)"
if [ ! -x "$TARGET/app/node_modules/.bin/vite" ]; then
  (cd "$TARGET/app" && npm install --legacy-peer-deps --no-audit --no-fund --loglevel=error)
fi
# kit/app/package.json pins the frontend packages of the default tag; another tag may need others.
pkg_version() { grep -m1 "^ *\"$1\":" "$2" 2>/dev/null | sed 's|^[^:]*: *"[~^]*\([^"]*\)".*|\1|' || true; }
for pkg in @gitlab/ui @gitlab/svgs; do
  want="$(pkg_version "$pkg" "$GL/package.json")"
  have="$(pkg_version "$pkg" "$TARGET/app/package.json")"
  if [ -n "$want" ] && [ "$want" != "$have" ]; then
    echo "WARN: GitLab $tag uses $pkg $want, app/package.json has $have (see references/setup.md, Use another GitLab version)"
  fi
done

# ---------------------------------------------------------------- 5. compiled GitLab CSS + static assets
log "5/7 compiled GitLab CSS (app/public/assets)"
A="$TARGET/app/public/assets"
mkdir -p "$A" "$TARGET/app/public/uploads"
NM="$TARGET/app/node_modules"
[ -s "$A/icons.svg" ]      || cp "$NM/@gitlab/svgs/dist/icons.svg" "$A/"
[ -s "$A/file_icons.svg" ] || cp "$NM/@gitlab/svgs/dist/file_icons/file_icons.svg" "$A/"
[ -d "$A/gitlab-sans" ]    || cp -R "$NM/@gitlab/fonts/gitlab-sans" "$A/"
[ -d "$A/gitlab-mono" ]    || cp -R "$NM/@gitlab/fonts/gitlab-mono" "$A/"
[ -d "$A/blooms" ]         || cp -R "$GL/app/assets/images/blooms" "$A/"
css_tag="$(cat "$A/.gitlab-tag" 2>/dev/null || true)"
# CSS built before this marker existed came from the same pin.
if [ -z "$css_tag" ] && [ -s "$A/application.css" ]; then css_tag="$tag"; fi
if [ "${FORCE_CSS:-0}" = 1 ] || [ ! -s "$A/application.css" ] || [ ! -s "$A/page_bundles_settings.css" ] || [ "$css_tag" != "$tag" ]; then
  # application.scss + fonts + tailwind (content = all GitLab sources + demos) + every CE/EE page bundle, 3-5 min
  (cd "$TARGET/app" && npm run -s css | tail -3)
else
  echo "compiled CSS present; FORCE_CSS=1 to rebuild"
fi
printf '%s\n' "$tag" > "$A/.gitlab-tag"

# ---------------------------------------------------------------- 6. ffmpeg
log "6/7 ffmpeg"
mkdir -p "$TARGET/tools"
if ! "$TARGET/tools/ffmpeg" -version >/dev/null 2>&1; then
  if command -v ffmpeg >/dev/null 2>&1; then
    ln -sfn "$(command -v ffmpeg)" "$TARGET/tools/ffmpeg"
  else
    # static build from the imageio-ffmpeg wheel (Linux x86_64/arm64, macOS x86_64/arm64)
    python3 -m pip install -q --target "$TARGET/tools/pyff" imageio-ffmpeg==0.6.0
    bin=""
    for f in "$TARGET"/tools/pyff/imageio_ffmpeg/binaries/ffmpeg-*; do
      [ -f "$f" ] && bin="$f" && break
    done
    [ -n "$bin" ] || { echo "no ffmpeg binary in the imageio-ffmpeg wheel; install ffmpeg and re-run" >&2; exit 1; }
    chmod +x "$bin"
    ln -sfn "pyff/imageio_ffmpeg/binaries/$(basename "$bin")" "$TARGET/tools/ffmpeg"
  fi
fi
"$TARGET/tools/ffmpeg" -version | head -1

# ---------------------------------------------------------------- 7. narration (Kokoro TTS)
log "7/7 narration: Kokoro TTS venv + model + voices"
if [ "${SKIP_NARRATION:-0}" = 1 ]; then
  echo "skipped"
else
  WITH_PIPER="${WITH_PIPER:-0}" KOKORO_MODEL="${KOKORO_MODEL:-}" bash "$TARGET/narration/setup.sh"
fi

mkdir -p "$TARGET/out"
log "done. Kit at $TARGET"
echo "Next:  cd $TARGET && node harness/narrated.mjs credit-caps     # about 2-3 min -> out/credit-caps/credit-caps-narrated.mp4"
