# Hero Archetypes: collage explainer

> **Five drafts live here.**
> - **Draft 1** (below): *The Hero with a Thousand Faces*, 16:9 sticker-collage explainer, 3:27 → `final/hero_archetypes_1080p.mp4`.
> - **Draft 2**: *The Hero With Infinite Faces*, vertical 9:16, text-led esoteric archival collage, about 7:30 → `final/hero_infinite_faces_vertical.mp4`. Script: `draft2/narration.md` · settings: `draft2/config.yaml` · style: `style/collage_style_prompt.md` · storyboard: `draft2/storyboard.md`.
>
>
> **Draft 3 (TikTok cut)**: *The Hero With Infinite Faces*, 1080×1920, 6:47 → `final/hero_infinite_faces_v3_vertical.mp4`. Design: `draft3/DESIGN.md` · plan: `draft3/PLAN.md` · script: `draft3/narration.md` · settings: `draft3/config.yaml` · captions: `draft3/hero_infinite_faces_v3.srt` · credits: `draft3/collage_sources.md`.
>
> | To change (draft 3) | Edit | Then run |
> |---|---|---|
> | Narration, bold/italic words, topic tags, registers | `draft3/narration.md` (`[register: …]`, `[scene: stack]`) | `./render.sh v3-voice`, then `v3-final` |
> | Series name in the header and end card | `series_name:` in `draft3/config.yaml` (now `SERIES_NAME`) | `./render.sh v3-final` |
> | Layout bands, colours, register looks, motion timings | `draft3/config.yaml` | `./render.sh v3-final` |
> | Which hero appears on which line | `heroes:` in `draft3/config.yaml` (`s<beat>.<line>@<fraction>` refs) | `./render.sh v3-final` |
> | Images used in the special moments | `draft3/moments.yaml` | `./render.sh v3-final` |
> | Drop an image from the collage | add its id to `draft3/collage_exclude.txt` | `./render.sh v3-final` |
> | Music intensity per beat, silences, foley levels | `music:` / `foley:` in `draft3/config.yaml` | `./render.sh v3-final` |
> | Real voice or music | `assets/voiceover_draft3.wav`, `assets/music.mp3` | `./render.sh v3-final` |
> | Check one moment against TikTok's covered areas | nothing | `./render.sh v3-still --safe s4.10@0.5` |
>
> **Draft 5 (Gemini's "Stark Epic" handoff)**: same pipeline as draft 4 with Gemini's script, scenes, config, renderer and sound changes (`draft5/HANDOFF_FROM_GEMINI.md`): crushed-black monochrome look, all-caps stamps, flash section breaks, the two convergences spelled out, about 3:40 → `final/hero_infinite_faces_v5_vertical.mp4`. Edit `draft5/narration.md`, `draft5/scenes.yaml`, `draft5/config.yaml`; run `./render.sh v5-voice` then `v5-final`.
>
> **Draft 4 (3-minute cut)**: *The Hero With Infinite Faces*, 1080×1920, about 3:05, narrated by Pocket TTS ("anna") → `final/hero_infinite_faces_v4_vertical.mp4`. Script: `draft4/narration.md` · what appears on screen per line: `draft4/scenes.yaml` · settings: `draft4/config.yaml` · plan: `draft4/PLAN.md` · captions: `draft4/hero_infinite_faces_v4.srt` · credits: `draft4/collage_sources.md`.
>
> | To change (draft 4) | Edit | Then run |
> |---|---|---|
> | Narration wording | `draft4/narration.md` | `./render.sh v4-voice`, then `v4-final` |
> | Voice | `pocket_voice:` in `draft4/config.yaml` (auditions: `voice_samples/`) or record `assets/voiceover_draft4.wav` | `./render.sh v4-voice` |
> | Which picture, label or chip appears on a line | `draft4/scenes.yaml` | `./render.sh v4-still --safe s3.4@0.8`, then `v4-final` |
> | Background collage subjects | `collage:` in `draft4/config.yaml`, `draft4/collage_exclude.txt` | `./render.sh v4-final` |
>
> Draft 2 quick commands: `./render.sh v2-voice` (after editing the script) → `./render.sh v2-preview` → `./render.sh v2-final`.
> Edit text in `draft2/narration.md`: `**bold**` = bold word on screen, `*…*` = italic line, `[tag: X]` = topic tag. Hero images per section, collage pacing, colours and fonts are in `draft2/config.yaml`. To drop an image from the collage, add its id to `draft2/collage_exclude.txt`. A real music bed goes in `assets/music.mp3` (otherwise a generated drone is used), and a recorded draft-2 voiceover goes in `assets/voiceover_draft2.wav`.

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
