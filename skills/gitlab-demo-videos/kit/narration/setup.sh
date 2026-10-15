#!/usr/bin/env bash
# One-time install of the local TTS engines used by narrate.py (no API keys, runs offline after this).
# Idempotent: re-running only fills in what is missing.
#   narration/setup.sh                    # Kokoro, full-precision model (default engine)
#   KOKORO_MODEL=int8 narration/setup.sh  # Kokoro, 92 MB quantized model (narrate.py picks it up)
#   WITH_PIPER=1 narration/setup.sh       # also the Piper fallback engine
set -Eeuo pipefail
trap 'echo "narration/setup.sh failed at line $LINENO" >&2' ERR
cd "$(dirname "$0")"
mkdir -p models/piper work

fetch() {  # fetch URL DEST  (atomic: never leaves a truncated model behind)
  [ -s "$2" ] && return 0
  echo "downloading $(basename "$2") ..."
  curl -fsSL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"
}

# Kokoro model + voices from the kokoro-onnx GitHub release (no huggingface.co access needed).
KO=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
case "${KOKORO_MODEL:-}" in
  int8) fetch "$KO/kokoro-v1.0.int8.onnx" models/kokoro-v1.0.int8.onnx ;;   # 92 MB
  fp16) fetch "$KO/kokoro-v1.0.fp16.onnx" models/kokoro-v1.0.fp16.onnx ;;   # 177 MB
  *)    fetch "$KO/kokoro-v1.0.onnx"      models/kokoro-v1.0.onnx ;;        # 326 MB
esac
fetch "$KO/voices-v1.0.bin" models/voices-v1.0.bin    # 28 MB, all voices

if ! .venv/bin/python -c 'import kokoro_onnx, soundfile' 2>/dev/null; then
  rm -rf .venv
  python3 -m venv .venv
  .venv/bin/pip install -q kokoro-onnx==0.6.1 soundfile
fi

# espeak-ng (phonemes) silently ignores data paths longer than ~160 chars, and some work dirs are longer.
# narrate.py copies the data to ~/.cache/espeak-ng-data on first use; do it here too so the first run is clean.
.venv/bin/python - <<'EOF'
import shutil, espeakng_loader
from pathlib import Path
short = Path.home() / '.cache' / 'espeak-ng-data'
if not (short / 'phontab').exists():
    shutil.copytree(espeakng_loader.get_data_path(), short, dirs_exist_ok=True)
print('espeak-ng data:', short)
EOF

# Optional second engine (Piper). The classic voices are on the v0.0.2 GitHub release.
if [ "${WITH_PIPER:-0}" = 1 ]; then
  [ -s models/piper/en-us-lessac-medium.onnx ] || curl -fsSL https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-lessac-medium.tar.gz | tar xz -C models/piper
  .venv-piper/bin/piper --help >/dev/null 2>&1 || { rm -rf .venv-piper; python3 -m venv .venv-piper && .venv-piper/bin/pip install -q piper-tts; }
fi
echo "narration setup ok"
