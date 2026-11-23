#!/usr/bin/env bash
# Hero Archetypes: one-command build.
#
#   ./render.sh setup      create the Python venv, install tools, download models + fonts
#   ./render.sh images     download any images listed in assets/image_manifest.yaml that are missing
#   ./render.sh cutouts    cut out figures (rembg) + sticker borders → assets/cutouts/, contact sheet
#   ./render.sh voice      placeholder TTS narration + timings + final/captions.srt
#   ./render.sh preview    540p / 15 fps preview → build/preview_540p.mp4
#   ./render.sh final      1080p / 30 fps → final/hero_archetypes_1080p.mp4
#   ./render.sh vertical   60 s 9:16 Shorts cut (Zelda section) → final/hero_archetypes_vertical.mp4
#   ./render.sh docs       regenerate script/storyboard.md and the Images table in sources.md
#   ./render.sh still 42.5 render single frames (seconds or refs like s3.2@0.5) → build/still_*.png
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

case "${1:-preview}" in
  setup)
    python3 -m venv .venv
    .venv/bin/pip install -q --upgrade pip
    .venv/bin/pip install -q "rembg[cpu]" pillow moviepy numpy scipy kokoro-onnx soundfile requests pyyaml
    mkdir -p build/models assets/fonts ~/.u2net
    base=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
    [ -f build/models/kokoro-v1.0.onnx ] || curl -sL -o build/models/kokoro-v1.0.onnx $base/kokoro-v1.0.onnx
    [ -f build/models/voices-v1.0.bin ]  || curl -sL -o build/models/voices-v1.0.bin  $base/voices-v1.0.bin
    [ -f ~/.u2net/isnet-general-use.onnx ] || curl -sL -o ~/.u2net/isnet-general-use.onnx \
      https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx
    gf=https://raw.githubusercontent.com/google/fonts/main
    [ -f assets/fonts/Anton-Regular.ttf ]          || curl -sL -o assets/fonts/Anton-Regular.ttf $gf/ofl/anton/Anton-Regular.ttf
    [ -f assets/fonts/Oswald-Variable.ttf ]        || curl -sL -o assets/fonts/Oswald-Variable.ttf "$gf/ofl/oswald/Oswald%5Bwght%5D.ttf"
    [ -f assets/fonts/PermanentMarker-Regular.ttf ] || curl -sL -o assets/fonts/PermanentMarker-Regular.ttf $gf/apache/permanentmarker/PermanentMarker-Regular.ttf
    [ -f assets/fonts/SpecialElite-Regular.ttf ]   || curl -sL -o assets/fonts/SpecialElite-Regular.ttf $gf/apache/specialelite/SpecialElite-Regular.ttf
    command -v ffmpeg >/dev/null || echo "!! ffmpeg not found: install it (e.g. apt install ffmpeg / brew install ffmpeg)"
    ;;
  images)   $PY tools/fetch_images.py ;;
  cutouts)  $PY tools/make_cutouts.py "${@:2}" ;;
  voice)    $PY tools/make_voiceover.py ;;
  preview)  $PY tools/render.py preview ;;
  final)    $PY tools/render.py final ;;
  vertical) $PY tools/render_vertical.py ;;
  docs)     $PY tools/make_docs.py ;;
  still)    $PY tools/render.py still "${@:2}" ;;
  all)      $PY tools/make_cutouts.py && $PY tools/make_voiceover.py && $PY tools/make_docs.py && $PY tools/render.py final ;;
  *) sed -n '2,14p' "$0"; exit 1 ;;
esac
