# Draft 4 plan (3-minute cut): approved and implemented

Built from the 15 notes on draft 3. Script: `draft4/narration.md` (462 words, about 3:00 at normal speed).

## How the script answers the notes
| Note | Where |
|---|---|
| 1 Past and present heroes; Jung and Campbell | §1 |
| 2 Qualities of heroes | §2 |
| 3 Convergent evolution: concept → biology → culture → the hero | §3 |
| 4 Context for people and works | Gilgamesh (Mesopotamia, ~4,000 years), Jung (Swiss psychiatrist), Campbell (1949 book), Zelda (games), Popper (philosopher), Miyazaki (1984 film), Deutsch (physicist, *The Beginning of Infinity*), Achilles (Homer's *Iliad*) |
| 5 "Faces" = different people, different instances | §1 line 6, then Link as the example |
| 6 Correcting errors in oneself, better than one's culture; reliable, not perfect; known and unknown domains | §4 (Popper, Nausicaä) |
| 7 Reach: all problems treated alike because soluble | §5 (Deutsch) |
| 8 Maps: Campbell's meta-map, placed with Campbell | §1 last two lines |
| 9 "Jung blamed inheritance" | removed |
| 10 Rediscovered and improved; flawed, domain-limited past heroes | §6 (Gilgamesh, Achilles) |
| 13 Less dramatic, less blunt | whole script; no "this is not a definition…", no "It could be you" |
| 14 Every example has a job | Gilgamesh = oldest + flawed; Achilles = heroic in one domain; Link = faces as instances; wings/eyes/writing = convergence; Nausicaä = correcting her culture's error |
| 15 Three minutes | 462 words |

## Two convergences: keep them distinct

The video relies on two different convergences. They are related, but they are not the same thing.

| | 1. Convergence in story-making | 2. Convergence in people |
|---|---|---|
| What converges | The **story**: cultures that never met invent tales with the same hero figure (Gilgamesh, Achilles, knights, Link, Nausicaä…). | The **person**: real people, in different times and places, separately become heroic by arriving at the same capacity: reliably finding and correcting their own errors, and treating problems as soluble. |
| What is being copied | Nothing. The pattern is reinvented, not inherited (no Jungian inheritance, no shared source). | Nothing. Each person builds the knowledge themselves, in their own setting. |
| Why it happens | Every culture faces problems and benefits from people who solve them, so a story shape that describes such people is useful and keeps being invented. | The world keeps presenting new, unpredictable problems; error correction is the solution that works on all of them, so people who succeed tend to converge on it. |
| Closest analogy | Writing invented separately in Mesopotamia, China and Mesoamerica (a cultural invention). | Wings or camera-like eyes in unrelated species (the same solution to the same problem). |
| Campbell's place | Campbell mapped convergence 1: his monomyth is a map of the stories (a map of maps). | Convergence 2 is the territory those maps describe. |
| Where in the script | §1 (heroes then and now, Campbell's map), §3 lines 5–6 ("The hero may be another example… stories about those people keep being invented."), §6 (stories rediscovered and improved). | §4 (Popper; Nausicaä as a fictional illustration of a person correcting her culture's error), §5 (Deutsch, reach), §7 ("anyone who corrects their own errors…"). |

**How they connect:** the stories (1) are maps of the people (2). Because stories are made by people who can also correct errors, the stories themselves improve over time (§6): later heroes keep what worked and drop the flaws. That is convergence 2 applied to convergence 1.

**Watch-out in the current narration:** §3 ends on convergence 1 (stories keep being invented) and §4 opens on convergence 2 ("What makes someone good at solving problems?") without saying that the subject has moved from stories to people. Possible fix, not applied (it would change the narration, which needs your OK):
- after §3 line 6, add: "People converge too: in every age, some learn, separately, to solve problems the same way."
- or open §4 with: "That is convergence in stories. There is also convergence in people."
Either adds about 3–4 seconds. On screen, the matching chips would be "stories converge" (§3.6, over the face grid) and "people converge" (§4.1).

## Visual changes (notes 1, 11, 12)
- **New intro**: a sliding timeline of artefacts with museum-style labels (what, where, when): a Gilgamesh cuneiform tablet, a Greek vase showing Achilles, a medieval knight from a manuscript, then film and game heroes. Replaces the black screen of italic lines.
- **Remove** the ember (fire light) and the golden ring/cycle-arrow mark everywhere.
- **Remove religious and heavenly imagery**: Doré's *Paradiso*, Flammarion, Fludd, angels, saints and church scenes are filtered out of the collage pool.
- Campbell's map drawn as a route on old map paper (home → test → return), not a circle.
- Convergence as side-by-side panels: wings (moth, bird, bat), eyes (octopus, human), early writing (cuneiform, oracle bone, Maya glyphs).
- Text strips, tags and TikTok-safe layout stay. The stack scene is dropped (it fit the old "lineage" beat).

## New factual claims to source before rendering
Gilgamesh ≈ 4,000 years old and opens with Gilgamesh oppressing Uruk · Achilles withdraws from battle in the *Iliad* · Jung's archetypes · Campbell 1949 · Zelda: Link a different person across eras · convergent evolution (wings; camera eyes in octopus and vertebrates) · independent invention of writing in Mesopotamia, China, Mesoamerica · Popper on error correction · *Nausicaä* (1984): the jungle purifies poisoned soil · Deutsch, *The Beginning of Infinity*: problems are soluble.

## As built
- Voice: Kyutai Pocket TTS, voice "anna" (VCTK p228, CC BY 4.0), `tools/v4_voice.py`. Narration 3:05.6 including the title (2.4 s) and end card.
- Renderer: `tools/render_v4.py`; per-line stage in `draft4/scenes.yaml` (conveyor, cards with museum labels and chips, Campbell's route map, lineage branches, face grids, chains).
- No ember, no gold ring, no stack scene. Background collage filtered for religious, heavenly, occult, funerary and ceremonial subjects (title filter + `draft4/collage_exclude.txt`).
- New pictures: `assets/v4/` (credits `draft4/asset_credits.json`), all from open-access museum APIs; candidates in `draft4/candidates.json`.
- Only one hard cut: into the end card (a 0.6 s fade). Section changes use the collage shard break.
