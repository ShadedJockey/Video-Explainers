# Hero Archetypes: collage explainer

A cut-out paper collage explainer (about 3:27, 1920×1080, 30 fps) about the hero archetype: Link as the Hero of Time, his ancient roots, modern heroes, the supporting cast, and why the hero keeps coming back (Campbell → Popper and Deutsch).

Everything is built from text and data files by a small Python pipeline, so changes are made by editing a file and re-running one command.

## Quick start

```bash
./render.sh setup      # once: venv, rembg, MoviePy, Kokoro TTS, fonts (needs ffmpeg installed)
./render.sh preview    # 540p preview → build/preview_540p.mp4 (a few minutes)
./render.sh final      # 1080p master → final/hero_archetypes_1080p.mp4
```

## What to edit for common changes

| I want to… | Edit | Then run |
|---|---|---|
| Change the narration wording | `script/narration.md` (the `>` lines) | `./render.sh voice`, then `preview` |
| Use my own recorded voiceover | save it as `assets/voiceover.wav` (follow the same line breaks and pace) | `preview` |
| Add a music bed | save it as `assets/music.mp3` (ducked 12 dB under speech automatically) | `preview` |
| Change timings, positions, captions or which image appears | `script/scenes.yaml` | `preview` (and `docs`) |
| Change colours, fonts, sticker borders, motion, render quality | `config.yaml` | `preview` |
| Change the pause between lines (e.g. montage pacing) | `config.yaml` → `voice.section_line_gaps` | `voice`, then `preview` |
| Fix a name the TTS mispronounces | `config.yaml` → `voice.pronunciations` | `voice` |
| Swap an image for a better one | drop it in `assets/stills/<id>.png` (or `assets/public_domain/`) using the same id, set `source: local` in `assets/image_manifest.yaml` | `cutouts <id>`, then `preview` |
| Fix a bad cutout edge or crop | `assets/cutouts.yaml` (`mode: card` turns it into a hand-cut print instead) | `cutouts <id>` (check `build/contact_sheet.jpg`) |
| Check a single moment quickly | n/a | `./render.sh still s3.2@0.5` (section 3, halfway through line 2) |

Timings in `scenes.yaml` are tied to narration lines (`s5.3` = section 5, line 3), so when the narration changes, the visuals move with it.

## Pipeline

```
script/narration.md ──► tools/make_voiceover.py ──► build/vo/voiceover_tts.wav
                                                    build/narration_timing.json
                                                    final/captions.srt
assets/image_manifest.yaml ──► tools/fetch_images.py ──► assets/public_domain/, assets/stills/
assets/cutouts.yaml ──► tools/make_cutouts.py (rembg + Pillow) ──► assets/cutouts/, build/contact_sheet.jpg
script/scenes.yaml + config.yaml ──► tools/render.py (MoviePy timeline, ffmpeg mix + encode) ──► the videos
tools/make_docs.py ──► script/storyboard.md, sources.md (Images)
```

| Tool | Role |
|---|---|
| **rembg** (isnet-general-use model) | background removal for figure cutouts |
| **Pillow** + NumPy | sticker borders, drop shadows, paper textures, aged tints, captions, dotted path, paper tears |
| **MoviePy** | timeline → frames → video |
| **ffmpeg** | voiceover/music mix with ducking, loudness normalisation (−16 LUFS), H.264 encode |
| **Kokoro** (local, free, offline) | placeholder narration |

## Folder layout

```
assets/screenshots/   assets/stills/   assets/public_domain/   assets/cutouts/   assets/textures/   assets/fonts/
script/   (narration.md, scenes.yaml, storyboard.md)
tools/    (the pipeline)
build/    (intermediate files, preview)
final/    (deliverables)
sources.md  config.yaml  render.sh
```

## Rights

Public-domain and open-access art comes from the Cleveland Museum of Art, the Art Institute of Chicago and Wikimedia Commons. Copyrighted characters appear as low-resolution stills for commentary and education. Every image, its licence and its source are listed in `sources.md`, and rights holders are credited on the end card.
