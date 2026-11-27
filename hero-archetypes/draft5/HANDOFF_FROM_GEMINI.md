# Claude Code Handoff: Draft 5 (Stark Epic Overhaul)

Copy these 5 files directly over your `hero-archetypes/` repository root:

- `hero-archetypes/draft4/narration.md`
- `hero-archetypes/draft4/scenes.yaml`
- `hero-archetypes/draft4/config.yaml`
- `hero-archetypes/tools/render_v4.py`
- `hero-archetypes/tools/make_sound_v4.py`

## Summary of Changes Included

1. **Script & Narrative (`draft4/narration.md`)**
   - Explicitly separates **Convergence 1 (hero stories)** in §3 from **Convergence 2 (real people)** in §4.
   - Adds the radical, anti-establishment tone layer: framing the error-correcting hero as a revolutionary cultural force that static societies have reliably held back.

2. **Visual & Aesthetic Overhaul (`draft4/config.yaml`, `tools/render_v4.py`)**
   - Crushed-black monochrome background grade with subtle film grain and a dark stage scrim for sharp foreground separation.
   - Pure white (`#f5f5f5`), obsidian black (`#090909`), and crimson ember (`#d9381e`) palette.
   - Hard-edged brutalist insets (zero tilt, zero blur shadows, crisp 2px hairline border) and stark all-caps 1-line stamps with a crimson left accent bar.
   - Snappy kinetic entry/exit (`din=0.14`, `dout=0.12`) and 2-frame invert/black flash section breaks replacing Voronoi shards.
   - Fixed header tag overflow/clipping, removed `SERIES_NAME` placeholder (set `series_name` in `config.yaml` when ready), capped captions to `max_strips: 4` (`text_y: [300, 740]`), expanded stage to `[780, 1430]`, and fixed the end-card composite fade.
   - Expanded finale face mosaic pool (`extra_pool=True` for subdivisions) to avoid repetitive tiles.

3. **Scene & Pacing Fixes (`draft4/scenes.yaml`)**
   - `s2.1`: All four hero qualities now land together in a `layout: grid2x2`.
   - `s3.3`: Overlapped wings and eyes transitions to remove the blank gap on "octopuses and humans".
   - `s3.6` & `s4.1–s4.2`: Added `"1. stories converge"` and `"2. people converge"` beats (filling the previously empty `s4.1` slot).
   - `s4.5`: Swapped the mushroom watercolor for `still:nausicaa_jungle` (add a film still at `assets/stills/nausicaa_jungle.jpg`, or point it to `still:nausicaa_study`).
   - `s7.1–s7.3`: Extended finale grid to `end-3.0` so the end card fades cleanly over the mosaic.

4. **Sound Bed (`tools/make_sound_v4.py`)**
   - Wired `music.level_db` from `config.yaml` (no longer hardcoded).
   - Replaced paper-rustle foley with deep sub-bass impact hits on section breaks.

## Build Commands

```bash
cd hero-archetypes
./render.sh v4-voice
./render.sh v4-still --safe s1.3@0.5 s2.1@0.85 s3.3@0.54 s3.6@0.6 s4.1@0.7 s7.3@0.8 end-2.5
./render.sh v4-final
```
