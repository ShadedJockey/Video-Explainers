"""Draft 5 sound bed: drone (or assets/music.mp3) with per-section envelope + sub-bass section impacts.

    python tools/make_sound_v5.py [path/to/music.mp3]   → draft5/build/sound_bed.wav (48 kHz stereo)
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
from make_sound_v3 import SR, db, drone, onepole  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def sub_impact(rng):
    """Short, dark sub-bass thud + filtered transient for hard-cut section breaks."""
    m = int(0.85 * SR)
    tt = np.arange(m) / SR
    freq = 95.0 * np.exp(-tt / 0.14) + 36.0
    phase = 2 * np.pi * np.cumsum(freq) / SR
    boom = np.sin(phase) * (1 - np.exp(-tt / 0.004)) * np.exp(-tt / 0.24)
    crack = onepole(rng.normal(0, 1, m), 1400) * np.exp(-tt / 0.035) * 0.25
    y = boom + crack
    return y / (np.abs(y).max() + 1e-9)


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

    # sub-bass impact hits on each section break (no paper rustles)
    imp = np.zeros(n)
    hit_db = CFG.get("foley", {}).get("impact_db", -18)
    for s in SECS[1:]:
        ts = s["start"] - CFG["motion"]["section_change_s"] - 0.05
        i0 = int(ts * SR)
        h = sub_impact(rng)
        if 0 <= i0 and i0 + len(h) < n:
            imp[i0:i0 + len(h)] += h * db(hit_db)

    out = np.clip(bed + imp[:, None], -0.98, 0.98).astype(np.float32)
    dest = ROOT / "draft5" / "build" / "sound_bed.wav"
    sf.write(dest, out, SR)
    print("wrote", dest.relative_to(ROOT), f"{n / SR:.1f}s")


if __name__ == "__main__":
    main()
