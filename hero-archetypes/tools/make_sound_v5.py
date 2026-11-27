"""Draft 5 sound: drone (or assets/music.mp3) with a per-section envelope, plus the transition sound on section breaks.

    python tools/make_sound_v5.py [path/to/music.mp3]
        → draft5/build/sound_bed.wav     (music; ducked under the voice in the mix)
        → draft5/build/transitions.wav   (the chosen cosmic sound at every section break; not ducked)

The transition sound and its level are set under `transition:` in draft5/config.yaml (options: tools/cosmic_sfx.py).
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
from make_sound_v3 import SR, db, drone, onepole  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    import render_v5 as R
    CFG, SECS, DUR = R.CFG, R.SECS, R.DUR
    n = int(DUR * SR) + SR
    t = np.arange(n) / SR
    rng = np.random.default_rng(44)
    music_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if music_path and music_path.exists():
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(music_path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                             capture_output=True, check=True).stdout
        mus = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
        mus = np.tile(mus, (int(np.ceil(n / len(mus))), 1))[:n]
    else:
        mus = drone(n, rng)
    mus /= np.sqrt(np.mean(mus ** 2)) + 1e-9
    E = CFG["music"]["envelope"]
    pts = [(0.0, 0.5)]
    for s in SECS:
        pts += [(s["start"] - 1.0, E.get(s["id"], 0.5)), (s["end"] - 0.2, E.get(s["id"], 0.5))]
    pts += [(DUR - 3.4, 1.0), (DUR - 0.3, 0.9), (DUR, 0.0)]
    xs, ys = zip(*sorted(pts))
    env = onepole(np.interp(t, xs, ys), 0.6)
    bed = mus * env[:, None] * db(CFG["music"]["level_db"] - 16)

    # transition sound on each section break, lined up so its anchor lands on the visual break
    import cosmic_sfx
    tr = CFG.get("transition", {})
    trk = np.zeros((n, 2))
    if tr.get("sound"):
        x, anchor = cosmic_sfx.make(tr["sound"])
        x = x * db(tr.get("level_db", -12))
        for s in SECS[1:]:
            ts = s["start"] - CFG["motion"]["section_change_s"] - 0.05
            i0 = int((ts - anchor) * SR)
            j0, j1 = max(0, i0), min(n, i0 + len(x))
            trk[j0:j1] += x[j0 - i0:j1 - i0]
    sf.write(ROOT / "draft5" / "build" / "transitions.wav", np.clip(trk, -0.98, 0.98).astype(np.float32), SR)

    out = np.clip(bed, -0.98, 0.98).astype(np.float32)
    dest = ROOT / "draft5" / "build" / "sound_bed.wav"
    sf.write(dest, out, SR)
    print("wrote", dest.relative_to(ROOT), f"{n / SR:.1f}s")


if __name__ == "__main__":
    main()
