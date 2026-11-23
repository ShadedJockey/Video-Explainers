# Claude Code Task: Hero Archetypes Collage Explainer

## Goal

Build a 2.5 minute collage-style explainer video about the hero archetype: why heroes like Link, the Hero of Time from *The Legend of Zelda*, follow patterns that go back thousands of years, and the other archetypes that surround them. The look is cut-out paper collage. Ancient artwork, game stills and illustrations are cut out and layered on textured backgrounds, sliding and popping in, with bold captions and a narrated voiceover. The finished video is for YouTube (16:9, 1920x1080, 30fps), with an optional 9:16 vertical cut for Shorts.

## Deliverables

1. `final/hero_archetypes_1080p.mp4`, the full 2:30 video with voiceover, music bed and captions.
2. `final/hero_archetypes_vertical.mp4` (optional), a 60 second vertical version built around the Zelda section.
3. `final/captions.srt`, a subtitle file matched to the voiceover.
4. `script/narration.md`, the final narration script with timings.
5. `sources.md`, listing every fact used with its source link, plus every image with its source and licence.
6. A short README explaining how to re-render after changes.

## Images

- **Ancient and historical heroes:** use public-domain artwork only, such as Wikimedia Commons, The Met Open Access and other museum open-access collections. Good candidates are Gilgamesh reliefs, Greek vase paintings of Heracles and Odysseus, medieval Arthurian manuscripts, and classic illustrations of Sun Wukong and Anansi. Log each image's source page and licence in `sources.md`. Old paintings and engravings suit the collage look perfectly.
- **Zelda:** use only screenshots I supply in `assets/screenshots/`, named by subject (e.g. `link_ocarina.png`, `master_sword.png`, `ganondorf.png`, `zelda.png`, `deku_tree.png`).
- **Modern films (optional):** use only stills I supply in `assets/stills/`. If there are none, cover those examples with captions and text cards instead.
- Never use fan art or images from other creators.

## Audio Inputs

- `assets/voiceover.wav` (optional): if it's missing, generate a temporary voiceover with a text-to-speech tool so the timing can be checked.
- `assets/music.mp3` (optional): a royalty-free music bed. If it's missing, leave a silent placeholder track and tell me. No official game or film music.

## Tools to Set Up

Use Python in a virtual environment. Install and confirm each of these, and tell me if anything fails:

- **rembg** for background removal on cutouts
- **Pillow** for image editing (white sticker borders, drop shadows, paper textures, aged tints)
- **MoviePy** for building the video timeline
- **ffmpeg** for final encoding and audio mixing
- A TTS option for placeholder narration (a local engine, or an API I approve)

## Visual Style

- **Cutouts:** every figure gets a thick white sticker-style border and a soft drop shadow, like it was cut from a magazine or an old book.
- **Backgrounds:** paper, parchment and cardboard textures. Ancient sections lean on warm sepia, the Zelda sections on Hyrule greens and golds, and the modern sections on cleaner, brighter tones.
- **Connecting motif:** a hand-drawn dotted path that winds across scenes, representing the hero's journey. Each hero cutout lands on a stop along it.
- **Comparisons:** split-screen pairings that show the same archetype across eras, e.g. Excalibur next to the Master Sword, or Merlin next to the Great Deku Tree.
- **Montage pacing:** in the iconic fiction heroes section, cutouts arrive every 3 to 4 seconds, each stamped with its journey-stage caption.
- **Finale mosaic:** reuse every cutout from the video to build one large face or silhouette for the "thousand faces" callback, assembling piece by piece.
- **Motion:** cutouts slide in, pop with a slight overshoot and wobble gently, with occasional slow zooms. Lively but not frantic.
- **Text:** big, bold, slightly rotated caption labels for archetype names, dates and key ideas.
- **Transitions:** paper tears, quick wipes, or one cutout covering the frame.

## Script Outline

Draft the narration from this outline, at about 150 words per minute (roughly 375 words in total). Verify every fact against reliable sources before using it and log it in `sources.md`. Flag anything you can't confirm, especially dates for ancient texts.

1. **Hook (0:00 to 0:10):** Even if you've never picked up a controller, Link feels familiar. That's because his story is one of the oldest we have.
2. **The hero with a thousand faces (0:10 to 0:30):** Introduce Joseph Campbell's *The Hero with a Thousand Faces* (1949). His claim was that myths worldwide share one hero wearing different faces, the monomyth or hero's journey: leaving home, facing trials, and returning changed. Briefly mention Carl Jung's idea of archetypes as recurring characters in human storytelling. This title is the spine of the whole video, so call back to it later.
3. **The Hero of Time (0:30 to 0:55):** Use Link in *Ocarina of Time* (1998) as the worked example. He's an ordinary boy from the forest, gets a call to adventure from the Great Deku Tree, draws the Master Sword, crosses into a darker world and saves the land. Note that Link's spirit is reborn across the series, a literal hero with many faces.
4. **Ancient roots (0:55 to 1:15):** Gilgamesh, from the oldest surviving epic, Heracles and his labours, and Odysseus and his long journey home. Show how each one hits the same beats. Pair King Arthur and the sword in the stone with Link and the Master Sword.
5. **Iconic fiction heroes (1:15 to 1:45):** Run a fast montage of modern heroes landing on the same journey stops. Suggested picks: Luke Skywalker (George Lucas openly drew on Campbell), Frodo Baggins, Harry Potter, Neo from *The Matrix*, Simba, Katniss Everdeen, Moana and Spider-Man. Give each a one-line caption showing which beat they hit, e.g. "the call", "the mentor", "the ordeal" and "the return". Pick 6 to 8 depending on which stills I provide.
6. **The supporting cast (1:45 to 2:08):** Cover the archetypes around the hero. The mentor is Merlin, Gandalf, Obi-Wan or the Great Deku Tree. The shadow is Ganondorf, Darth Vader or Voldemort. The trickster is Loki, Anansi or Sun Wukong, and the wise guide is Princess Zelda. Include at least one non-Western example per archetype where possible.
7. **A thousand faces (2:08 to 2:25):** Call back to Campbell. Every hero from the video assembles into one mosaic face, the "thousand faces" visual. We keep telling this story because it maps onto real life: leaving the familiar, being tested, and coming back different.
8. **Outro (2:25 to 2:30):** A short sign-off and a call to subscribe.

## Pipeline Steps

1. Research and verify the facts, then write `sources.md`.
2. Write `script/narration.md` and **stop for my approval**.
3. Make a storyboard (`script/storyboard.md`) listing each scene's narration line, the images used, the motion and the on-screen text. **Stop for my approval.**
4. Find and download the public-domain artwork, logging the licences, then list which Zelda screenshots or film stills you still need from me.
5. Cut out every figure with rembg, then add borders and shadows. Save them to `assets/cutouts/` and show me a contact sheet of every cutout so I can flag bad edges.
6. Generate placeholder TTS narration if I haven't provided `voiceover.wav`.
7. Build the timeline in MoviePy, syncing scenes to the narration timings.
8. Mix the voiceover over the music bed, ducking the music about 12 dB under speech.
9. Generate `captions.srt`.
10. Render a low-resolution preview first, and tell me so I can review before the final render.
11. Render the final files and write the README.

## Fair Use Guardrails

- This is commentary and education. Every game or film image should support what the narration is explaining at that moment.
- Use stills only, with no gameplay or film footage and no official music.
- Keep copyrighted images on screen only as long as the point needs.
- Add an end card crediting Nintendo, Lucasfilm and any other rights holders whose characters appear, plus the museums and archives the public-domain art came from.

## Folder Structure

```
hero-archetypes/
  assets/screenshots/
  assets/stills/
  assets/public_domain/
  assets/cutouts/
  assets/textures/
  script/
  build/
  final/
  sources.md
  README.md
```

## Working Rules

- Ask me before installing paid tools or using any API that costs money.
- Keep all render settings in one config file so I can tweak durations, colours and fonts easily.
- If a step fails, explain what happened in plain terms and suggest a fix before retrying.
