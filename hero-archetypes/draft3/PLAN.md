# Draft 3 build plan

Source of truth: `draft3/DESIGN.md` (Script v2, Writing style, Visual direction, Visual references, Production, Fact-check). Drafts 1 and 2 stay untouched; new code lives in `tools/*_v3.py`, `tools/render_stack.py` and `render.sh v3-*` targets.

## Reused from draft 2

| From | What | How it changes |
|---|---|---|
| `tools/v2_voice.py` | Kokoro per-line TTS, timing JSON, captions | `tools/v3_voice.py`: per-register speed (prologue 0.85), longer prologue pauses, extra silences before two lines, `[register]`/`[scene]` keys, inline italics |
| `tools/render_v2.py` | Text strips, header tags, title card, collage piece cutting, edge slides, stale-area placement, hero cut-outs (rembg masks), vignette, mix | `tools/render_v3.py` starts from it |
| `tools/harvest_esoteric.py` | Themed Wellcome / Cleveland / AIC harvesting with licences | `tools/harvest_v3.py` reuses its source functions with draft-3 themes, plus named works by id |
| `tools/make_drone.py` | Original ambient drone | `tools/make_sound_v3.py`: per-beat intensity envelope, two silences, synthesised paper and fire foley |
| `assets/stills`, `build/masks` | Hero images and rembg masks | Reused; K added if a Wikipedia infobox image exists |

## New in draft 3

1. **TikTok layout bands** in config: header tags y 230–290, text column y 300–1000 (x 60–940, at most 7 strips, lines fade before the header band), hero band y 1000–1440 kept clear while a hero holds, collage only below 1440 and in the right 140 px.
2. **Register modes** (prologue, scripture, mythmaker, rational, labyrinth, stark) as data: grade, piece interval, burst size, entry style (slide or fade-drift), text wipe time, themes. The grade crossfades over about 1 s at each change; mid-section switches are supported.
3. **Text treatments:** standard strips; italic lines as inscriptions (black strip, warm white italic, +1.2 s hold); prologue lines centred italic with no strips, fading in.
4. **The ember** (soft warm pulsing light, 3 s period) drifting towards the current hero, in every beat; **the mark** (open ring + arrowhead in ember gold) drawn procedurally at any size, with a draw-on parameter.
5. **Beat change:** staggered cascade of collage pieces sliding out to the nearest edge (0.6 s), column clears, new tag wipes in.
6. **Special moments** for beats 0–12, implemented as scene "moments" keyed to narration references (`s4.10@0.2` style), each a small drawing function layered over the collage.
7. **The stack** (`tools/render_stack.py`): a self-contained 3D-ish scene (panes in depth with multiplane parallax, column of marks, tilt up to Doré's light) that render_v3 calls for beat 5 and for the beat 12 reprise.
8. **Exactly four hard cuts**: title (end of beat 0), into the stack (beat 5), to black (end of beat 7), end card. Everything else is continuous.
9. **Sound:** music envelope per beat, synthesised foley, 48 kHz final mix at about −15 LUFS, true peak below −1 dB.

## How the timeline fits together

`v3_voice.py` writes `draft3/build/timing.json` (sections, lines, register per line). `render_v3.py` builds: a piece schedule (per-register pace, beat-change exits), hero events from `config.yaml` (each at a narration reference), text-line layout, register grade curve, the ember path, and a list of moments. Each frame = collage canvas (baked landed pieces + moving pieces) → grade → moments → hero band → ember → text → tags; the stack scene replaces the collage during beat 5 and the beat 12 reprise; hard cuts are frames of black or title/end cards.
