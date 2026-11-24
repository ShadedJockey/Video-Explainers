# Claude Code prompt: build draft 3 of "The Hero With Infinite Faces"

Paste everything below the line into Claude Code. Attach or copy `hero_infinite_faces_running_ideas.md` (the design doc) into the repo first, as described in step 0.

---

You are building **draft 3** of a vertical explainer video, *The Hero With Infinite Faces*, in the repo `ShadedJockey/Video-Explainers`, branch `claude/bold-babbage-06wjm7`, folder `hero-archetypes/`. Drafts 1 and 2 already exist there, built by a scripted Python pipeline (`render.sh`, `tools/`, `draft2/`). Draft 3 reuses that pipeline but has a new script, a new layout for TikTok and a richer visual edit.

## The source of truth

The design doc `hero-archetypes/draft3/DESIGN.md` holds every decision. Read all of it before writing code. The sections you will use most:

| Section | What it gives you |
| --- | --- |
| **Script v2** | The exact narration: 13 beats (0–12), 918 words, with bold words, italic lines and a register per beat. Use it word for word. |
| **Writing style** → Delivery | Voice speed, pauses, and the slower prologue read |
| **Visual direction** | Principles, visual mode per register, type, motion grammar, sound, the beat-by-beat edit plan with timings, and the stack sequence line by line |
| **Visual references** | Public-domain images to use directly, and study-only references |
| **Production** | TikTok layout bands, the 12 fixes from the draft 2 review, heroes by beat, file-size limit |
| **Fact-check** | F1–F17 with sources and safe wording |

Ignore the older sections (Script draft v1, The full spine, Starter visual) except as background; where they conflict with the sections above, the sections above win.

## Rules

- **Keep drafts 1 and 2 intact.** Everything new goes in `hero-archetypes/draft3/` plus new scripts in `tools/` (`*_v3.py`). Do not change the behaviour of `v2-*` targets in `render.sh`; add `v3-*` targets.
- **Nothing paid.** No paid APIs or services. Local tools only: Python venv with Pillow, MoviePy, NumPy, rembg, Kokoro, ffmpeg (as in drafts 1 and 2).
- **Facts.** Use the script's wording, which already follows the fact-check. Add no new on-screen claims. Copy F1–F17 into `hero-archetypes/sources.md` as a new "Draft 3" section.
- **Rights.**
  - Record every downloaded image's source and licence at download time, as the existing harvester does.
  - Copyrighted characters appear only while the narration discusses them, mid-size, cut into collage pieces; no game or film footage, no official music.
  - Do **not** use the *Blade Runner 2049* or *Star Wars* posters. For K, use a character image (not Deckard) from Wikipedia's article infobox, as draft 2 did for other characters.
  - Never quote or echo lines from *The Fellowship of the Ring* film; only its style was borrowed.
- **Layout is fixed by TikTok's interface** (see Production → Layout for TikTok). No text or faces in the top 220 px, the bottom 480 px or the right 140 px of the 1080×1920 frame.
- **Look before trusting**, as in drafts 1 and 2: contact sheets, sampled stills and loudness checks at every stage.
- **Ask me before** dropping a feature from the edit plan, changing script wording, or spending more than an hour stuck on one asset.

## Steps

Work through these in order and keep a task list. Commit after each step that produces working output.

### 0. Set up and read

1. Check out the branch and read `hero-archetypes/README.md`, `render.sh`, `tools/render_v2.py`, `tools/v2_voice.py`, `tools/harvest_esoteric.py`, `draft2/config.yaml` and `draft2/narration.md` to learn the existing markup, timing references (`s3.2@0.5`) and config keys.
2. Create `hero-archetypes/draft3/` and save the design doc there as `DESIGN.md`.
3. Write a short plan in `draft3/PLAN.md`: what you will reuse from `render_v2.py`, what is new, and how the new scenes plug into the timeline.

### 1. Script

Write `draft3/narration.md` from **Script v2**:

- Same markup as draft 2: `[tag: X]` per beat (use the topic after the "·" in each heading), `**word**` for bold, a line wrapped in `*…*` for italics, one sentence per line, a blank line between sections.
- Add two per-section keys the renderer will read: `[register: prologue | scripture | mythmaker | rational | labyrinth | stark]` (mapping in Writing style) and `[scene: stack]` on beat 5.
- Beat 0 is the prologue; beat 12 starts in `prologue` and moves to `scripture` at "The Hero recurs because…". Support a mid-section register switch.
- Add `pronunciations:` for Deutsch, Jung, Nausicaä, Estel, Gilgamesh, Guts, Galileo, Brecht, Dawkins, Popper.

### 2. Assets

1. Extend the harvester (`tools/harvest_v3.py`, or new theme lists for the existing one) with themed searches matching the edit plan: engraved hands, fire and torches, burning books, masks and faces from many cultures, costume plates, old maps, St George and dragons, anatomical eye plates (octopus and human), insect, bird and bat wings, Haeckel (fungi, radiolaria), soil sections, microscopes, emblem books (anchor, scales, lion, telescope), castle walls, ruins and broken statues, torch races, trees of knowledge, libraries, starfields.
2. Fetch the named public-domain works from **Visual references**: Doré *Paradiso* Canto 31, the Flammarion engraving, Fludd's *Utriusque Cosmi* plates, Michelspacher 1616, the Remmelin and Wellcome flap anatomies, the 1671 table of alchemical symbols and A. Bell's symbols plate, and Dürer's *Knight, Death and the Devil* (already in draft 2).
3. Reuse draft 2's hero images where they still fit (Link, Gilgamesh, Guts, Aragorn, Frodo and Sam, Nausicaä, Master Chief, Campbell, Jung, Popper, Deutsch, Ganondorf, Vader, Gandalf, the Deku Tree illustration). Get a K image and, if possible, sharper Frodo and Aragorn stills.
4. Known network problems from earlier drafts: Wikimedia returns 429s from the shared address (use direct file URLs, standard thumbnail sizes, retries in the background); the Art Institute of Chicago blocks user agents containing "python-requests"; the Met's image server serves a bot check (use Commons mirrors). If a host is blocked by the environment's allowlist, tell me which one.
5. Make a contact sheet of everything new and cull off-tone images into `draft3/collage_exclude.txt`.

### 3. Config

Write `draft3/config.yaml` with:

- **Layout bands** from Production: header tags y 230–290; text column y 300–1000, x 60–940, at most 7 strips; hero band y 1000–1440; collage-only below 1440 and in the right 140 px.
- **Palette:** draft 2's deep red, indigo, gold and starfield swatches, plus ember gold for the ember and mark, warm white paper, near-black ink.
- **Register modes:** the Visual mode per register table, as data (grade, piece interval, burst size, entry style, text wipe time, image themes).
- **Motion timings:** the Motion grammar table.
- **Heroes per beat**, each timed to its narration line with `s<beat>.<line>@<fraction>` references (villains on "the problem, given a face"; mentors on the mentor line; K on beat 9 only).
- **Hard cuts:** exactly four (title, into the stack, to black at the end of beat 7, end card).
- Header series name: leave a clear placeholder `SERIES_NAME` and tell me to fill it in. **No "Subscribe" tag.**

### 4. Renderer

Create `tools/render_v3.py`, starting from `render_v2.py`. It must implement:

1. **Layout and the draft 2 fixes** (Production → Fixes 1–5): lines fade before reaching the header band; column capped at 7 strips; one left margin (x 60, at most ±4 px jitter); hero band reserved and kept clear of new pieces while a hero holds.
2. **Register modes** switching grade, collage pace, entry style and image themes per section, with a smooth grade transition (about 1 s) between beats.
3. **Text:** standard strips; italic lines as **inscriptions** (black strip, warm white italic, held 1.2 s longer); prologue lines centred, italic, no strips, fading in.
4. **The ember:** a soft warm point of light with a 3 s pulse that drifts towards the current hero image, present in every beat.
5. **The mark:** a procedurally drawn open ring with an arrowhead, in ember gold, reusable at any size.
6. **Beat change:** staggered cascade of pieces sliding out to their nearest edge (0.6 s), column clears, new tag wipes in.
7. **Special moments** from the edit plan:
   - beat 0: hands receiving the ember; hard cut to the title card on "They were wrong about the number."
   - beat 1: eight faces in one second on "infinite"
   - beat 2: Campbell's circle drawn as a ring that opens into the mark; label lines drawing across the dragon engraving on "soluble problem"
   - beat 3: paired plates sliding in from opposite edges and lining up; beat 1's masks returning, aligned
   - beat 4: five virtue emblems; the mark as the cycle, with problem, guess, error and correction at its quarters, the ember travelling round once
   - beat 6: near-mono grade with red kept only in Guts
   - beat 7: crack through the mark mending with a gold seam; hard cut to black for the final italic lines
   - beat 8: wall stones sliding out on "no wall holds"
   - beat 9: the ember flickering on an anonymous portrait on "for one moment"
   - beat 10: the ember passed between engraved hands
   - beat 11: accelerating face cascade; Flammarion engraving on "edge of the map", starfield beyond
   - beat 12: stack reprise rising to Doré's light; "It could be you" alone on black; end card (title with the last word in italics, plus `SERIES_NAME`), 3 s
8. **The stack scene** (`tools/render_stack.py`), driven by the line-by-line table in Visual direction → The stack sequence: one hero with the mark → pull back into a collage of heroes, each with a slightly varied mark → the collage flattens into a translucent pane → 12–20 panes fan out in depth with multiplane parallax, each holding a different collage → the marks snap into one vertical column of light → camera tilts up to Doré's light, stopping just short → camera keeps rising as new panes appear above. About 45 s in beat 5, reprised for about 10 s in beat 12.
9. A `--still s<beat>.<line>@<fraction>` mode, as in draft 2, and a 540×960 preview mode.

### 5. Voice

Extend `v2_voice.py` as `v3_voice.py`: Kokoro, one of its British female voices as the placeholder, speed 0.93; prologue lines at 0.85 with longer pauses between them; 1.5 s of extra silence before "This is not a definition" and 1 s before "It could be you". Keep draft 2's per-line timing output. If `assets/voiceover_draft3.wav` exists, use it instead, following whatever mechanism draft 2 used for a real recording.

### 6. Music and sound

- Extend the drone generator with an **intensity envelope per beat**: sparse in the prologue, building to a peak in the stack, falling almost silent in beats 6–7, rebuilding through 8–11, swelling at the close. If `assets/music.mp3` exists, use it instead and still apply the two silences.
- Synthesise quiet foley (no downloads): paper slides for collage pieces at about −30 dB, and a soft fire crackle in the cold open and wherever the ember is passed.
- Mix: music about 24 dB under the voice with ducking; resample the final mix to **48 kHz** (draft 2 came out at 44.1); integrated loudness about −15 LUFS, true peak below −1 dB.

### 7. Captions

Write `draft3/hero_infinite_faces_v3.srt` from the line timings.

### 8. Preview and checks

1. Render the 540×960 preview.
2. Render stills at: the title cut, "infinite" (beat 1), the dragon labels (beat 2), the cycle (beat 4), each step of the stack, Guts, the gold seam (beat 7), the Flammarion moment, the final line, the end card.
3. Overlay TikTok's covered areas (top 220, bottom 480, right 140 px) on every still and confirm no text or face falls inside them.
4. Make a contact sheet with one frame every 5 seconds of the preview and look at it as a whole: does the frame move from dark to light, are the four hard cuts the only cuts, do heroes appear only during their lines?
5. Show me the stills and contact sheet and wait for my go-ahead before the full render.

### 9. Final

1. Render the full 1080×1920, 30 fps master to `final/hero_infinite_faces_v3_vertical.mp4`. Keep it under GitHub's 100 MB limit (draft 2 needed CRF 23; adjust if needed).
2. Check duration (about 6:25, ±30 s), loudness, sample rate and file size with ffprobe and ffmpeg.
3. Add `v3-*` targets to the README's table of what to edit for common changes, and update credits in `draft3/collage_sources.md`.
4. Commit and push to the branch. Report what was built, any feature you could not implement, and any open items.

## Open items to leave for me

- `SERIES_NAME` in the header tags and end card
- Real voiceover (`assets/voiceover_draft3.wav`) and music bed (`assets/music.mp3`)
- Any asset you could not find, listed with what you tried
