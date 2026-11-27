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
#
#   Draft 2 — "The Hero With Infinite Faces" (vertical, text-led collage; settings in draft2/config.yaml)
#   ./render.sh v2-harvest   download themed public-domain art → assets/collage/
#   ./render.sh v2-voice     narration from draft2/narration.md → draft2/build/vo.wav + captions
#   ./render.sh v2-preview   540×960 preview → draft2/build/preview_540x960.mp4
#   ./render.sh v2-final     1080×1920 → final/hero_infinite_faces_vertical.mp4
#   ./render.sh v2-still s3.2@0.5   single frames → draft2/build/still_*.png
#   ./render.sh v2-docs      regenerate draft2/storyboard.md + draft2/collage_sources.md
#
#   Draft 3 — TikTok cut (settings in draft3/config.yaml, design in draft3/DESIGN.md)
#   ./render.sh v3-harvest   themed art + named works → assets/collage/, assets/v3/
#   ./render.sh v3-voice     narration from draft3/narration.md → draft3/build/vo.wav, timing, draft3/*.srt
#   ./render.sh v3-sound     drone envelope + foley → draft3/build/sound_bed.wav
#   ./render.sh v3-preview   540×960 preview → draft3/build/preview_540x960.mp4
#   ./render.sh v3-final     1080×1920 → final/hero_infinite_faces_v3_vertical.mp4
#   ./render.sh v3-still [--safe] s4.10@0.5   single frames (optionally with TikTok's covered areas) → draft3/build/
#   ./render.sh v3-docs      regenerate draft3/collage_sources.md
#   ./render.sh v3-range 191.5 197.5   re-render a span at final quality → draft3/build/range_*.mp4 (for splicing)
#
#   Draft 4 — 3-minute cut (settings in draft4/config.yaml, stage in draft4/scenes.yaml)
#   ./render.sh v4-setup     Pocket TTS for the narration voice → .tts/pocket
#   ./render.sh v4-voice     narration (Pocket TTS, voice "anna") → draft4/build/vo.wav, timing, draft4/*.srt
#   ./render.sh v4-preview   540×960 preview → draft4/build/preview_540x960.mp4
#   ./render.sh v4-final     1080×1920 → final/hero_infinite_faces_v4_vertical.mp4
#   ./render.sh v4-still [--safe] s3.4@0.8   single frames → draft4/build/
#   ./render.sh v4-docs      regenerate draft4/collage_sources.md
#
#   Draft 5 — Gemini's "Stark Epic" handoff (draft5/HANDOFF_FROM_GEMINI.md), same pipeline as draft 4
#   ./render.sh v5-voice · v5-preview · v5-final · v5-still [--safe] s4.1@0.7 · v5-docs
#
#   Draft 6 — your edit + themes, narrated in your cloned voice (Qwen3-TTS; reference in assets/private/, git-ignored)
#   ./render.sh v6-setup   Qwen3-TTS venv → .tts/qwen        ./render.sh v6-voice   → draft6/build/vo.wav + voice_report.md
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
  v2-harvest) $PY tools/harvest_esoteric.py ;;
  v2-voice)   $PY tools/v2_voice.py ;;
  v2-preview) $PY tools/render_v2.py preview ;;
  v2-final)   $PY tools/render_v2.py final ;;
  v2-still)   $PY tools/render_v2.py still "${@:2}" ;;
  v2-docs)    $PY tools/v2_docs.py ;;
  v3-harvest) $PY tools/harvest_v3.py themes && $PY tools/harvest_v3.py named && $PY tools/harvest_v3.py commons ;;
  v3-voice)   $PY tools/v3_voice.py ;;
  v3-sound)   $PY tools/make_sound_v3.py ;;
  v3-preview) $PY tools/render_v3.py preview ;;
  v3-final)   $PY tools/render_v3.py final ;;
  v3-still)   $PY tools/render_v3.py still "${@:2}" ;;
  v3-docs)    $PY tools/v3_docs.py ;;
  v3-range)   $PY tools/render_v3.py range "${@:2}" ;;
  v4-setup)   command -v uv >/dev/null || pip install -q uv
              uv venv -q -p 3.12 .tts/pocket && VIRTUAL_ENV=$PWD/.tts/pocket uv pip install -q pocket-tts soundfile pyyaml numpy \
                --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match ;;
  v4-voice)   HF_HUB_DISABLE_XET=1 .tts/pocket/bin/python tools/v4_voice.py ;;
  v4-preview) $PY tools/render_v4.py preview ;;
  v4-final)   $PY tools/render_v4.py final ;;
  v4-still)   $PY tools/render_v4.py still "${@:2}" ;;
  v4-docs)    $PY tools/v4_docs.py ;;
  v5-voice)   HF_HUB_DISABLE_XET=1 .tts/pocket/bin/python tools/v5_voice.py ;;
  v5-preview) $PY tools/render_v5.py preview ;;
  v5-final)   $PY tools/render_v5.py final ;;
  v5-still)   $PY tools/render_v5.py still "${@:2}" ;;
  v5-docs)    $PY tools/v5_docs.py ;;
  v6-setup)   uv venv -q -p 3.12 .tts/qwen && VIRTUAL_ENV=$PWD/.tts/qwen uv pip install -q qwen-tts soundfile pyyaml faster-whisper jiwer librosa \
                --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match ;;
  v6-voice)   HF_HUB_DISABLE_XET=1 .tts/qwen/bin/python tools/v6_voice.py ;;
  all)      $PY tools/make_cutouts.py && $PY tools/make_voiceover.py && $PY tools/make_docs.py && $PY tools/render.py final ;;
  *) sed -n '2,49p' "$0"; exit 1 ;;
esac
