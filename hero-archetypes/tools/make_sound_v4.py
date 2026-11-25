"""Draft 4 sound bed: the generated drone (or assets/music.mp3) with a per-section envelope, plus paper foley.

    python tools/make_sound_v4.py [path/to/music.mp3]   → draft4/build/sound_bed.wav (48 kHz stereo)
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
from make_sound_v3 import SR, db, drone, onepole, paper  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    import render_v4 as R
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
    bed = mus * env[:, None] * db(-40)
    r = R.Renderer("preview")
    fol = np.zeros(n)
    for ts in sorted(set(round(x, 2) for x in r.sfx)):
        i0 = int(ts * SR)
        p = paper(rng) * rng.uniform(0.7, 1.0)
        if 0 <= i0 and i0 + len(p) < n:
            fol[i0:i0 + len(p)] += p * db(CFG["foley"]["paper_db"])
    for ev in r.events:              # background pieces, quieter
        i0 = int((ev["t"] + ev["dur"] * 0.7) * SR)
        p = paper(rng) * rng.uniform(0.4, 0.7)
        if i0 + len(p) < n:
            fol[i0:i0 + len(p)] += p * db(CFG["foley"]["paper_db"] - 6)
    out = np.clip(bed + fol[:, None] * np.array([1.0, 0.92]), -0.98, 0.98).astype(np.float32)
    dest = ROOT / "draft4" / "build" / "sound_bed.wav"
    sf.write(dest, out, SR)
    print("wrote", dest.relative_to(ROOT), f"{n / SR:.1f}s")


if __name__ == "__main__":
    main()
