"""Draft 3 sound bed: drone with a per-beat intensity envelope, two silences, synthesised foley.

    python tools/make_sound_v3.py [path/to/music.mp3]   → draft3/build/sound_bed.wav (48 kHz stereo)

Without a music file, an original drone (tools/make_drone.py style) follows the beat envelope in
draft3/config.yaml (sparse prologue → peak in the stack → near silence in beats 6–7 → rebuild → swell).
With a music file, it is looped to length and only the two silences are applied.
Foley (no downloads): a soft paper slide for every collage piece that lands (≈ −30 dB) and a fire
crackle in the cold open and wherever the ember is passed (≈ −27 dB).
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parents[1]
SR = 48000


def db(x):
    return 10 ** (x / 20)


def onepole(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    from scipy.signal import lfilter
    return lfilter([1 - a], [1, -a], x)


def drone(n, rng):
    t = np.arange(n) / SR
    L = np.zeros(n)
    R = np.zeros(n)
    for f, amp, rate in ((55.0, 0.30, 0.031), (82.41, 0.20, 0.023), (110.0, 0.14, 0.041), (164.8, 0.06, 0.017), (138.6, 0.035, 0.013), (220.0, 0.03, 0.019)):
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * rate * t + rng.random() * 6.28)
        L += amp * lfo * np.sin(2 * np.pi * f * 0.998 * t)
        R += amp * lfo * np.sin(2 * np.pi * f * 1.002 * t + 0.7)
    air = onepole(rng.normal(0, 1, n), 700)
    swell = 0.5 + 0.5 * np.sin(2 * np.pi * 0.011 * t)
    L += 0.12 * air * swell
    R += 0.12 * np.roll(air, 2400) * swell
    # sparse chimes (A minor pentatonic) with a simple echo
    notes = [440.0, 523.25, 587.33, 659.25, 783.99, 880.0]
    pos = 6.0
    ch = np.zeros(n)
    while pos < n / SR - 6:
        f = rng.choice(notes)
        i0 = int(pos * SR)
        m = min(n - i0, int(5 * SR))
        tt = np.arange(m) / SR
        env = np.exp(-tt / 1.8) * (1 - np.exp(-tt / 0.004))
        ch[i0:i0 + m] += 0.05 * env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.76 * tt))
        pos += rng.uniform(7, 13)
    for d, g in ((0.37, 0.45), (0.71, 0.3), (1.13, 0.18)):
        k = int(d * SR)
        ch[k:] += ch[:-k] * g
    L += ch
    R += np.roll(ch, 700)
    return np.stack([L, R], 1)


def paper(rng):
    m = int(0.28 * SR)
    tt = np.arange(m) / SR
    x = rng.normal(0, 1, m)
    x = onepole(x, 3200) - onepole(x, 600)          # band-pass-ish rustle
    env = (1 - np.exp(-tt / 0.012)) * np.exp(-tt / 0.07)
    return x * env / (np.abs(x * env).max() + 1e-9)


def crackle(n, rng):
    x = np.zeros(n)
    k = rng.poisson(n / SR * 22)
    for p in rng.integers(0, n - 400, k):
        L = rng.integers(40, 300)
        x[p:p + L] += rng.normal(0, 1, L) * np.exp(-np.arange(L) / (L / 4)) * rng.uniform(0.2, 1.0)
    x = onepole(x, 5000) - onepole(x, 900)
    rumble = onepole(rng.normal(0, 1, n), 180) * 0.6
    y = x + rumble
    return y / (np.abs(y).max() + 1e-9)


def main():
    import render_v3 as R
    CFG, T, SECS, DUR = R.CFG, R.T, R.SECS, R.DUR
    n = int(DUR * SR) + SR
    t = np.arange(n) / SR
    rng = np.random.default_rng(31)
    music_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    # ── music: user file (looped) or the generated drone with the beat envelope ──
    if music_path and music_path.exists():
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(music_path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                             capture_output=True, check=True).stdout
        mus = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
        mus = np.tile(mus, (int(np.ceil(n / len(mus))), 1))[:n]
        mus /= np.sqrt(np.mean(mus ** 2)) + 1e-9
        env = np.ones(n)
    else:
        mus = drone(n, rng)
        mus /= np.sqrt(np.mean(mus ** 2)) + 1e-9
        E = CFG["music"]["envelope"]
        pts = []
        for s in SECS:
            pts.append((s["start"] - 1.0, E.get(s["id"], 0.5)))
            pts.append((s["end"] - 0.2, E.get(s["id"], 0.5)))     # plateau per beat
        pts = [(0.0, E.get(0, 0.3))] + pts + [(DUR - 3.0, E.get(SECS[-1]["id"], 1.0)), (DUR, 0.0)]
        xs, ys = zip(*sorted(pts))
        env = np.interp(t, xs, ys)
        env = onepole(env, 0.6)          # smooth the steps (≈ 1–2 s glides)
    # two silences before key lines
    for s in SECS:
        for ln in s["lines"]:
            for pref in CFG["music"]["silences"]:
                if R.re.sub(r"\*+", "", ln["text"]).startswith(pref):
                    a, b = ln["start"] - ln.get("silence_before", 1.5) - 0.4, ln["start"] + 0.3
                    m = np.clip(np.minimum((t - a) / 0.35, (b - t) / 0.35), 0, 1)
                    env = env * (1 - 0.95 * m)
    bed = mus * env[:, None] * db(-40)      # ≈ 24 dB under the voice before the final loudness pass
    # ── foley: paper slides for collage pieces, crackle where the ember passes ──
    r = R.Renderer("preview")
    fol = np.zeros(n)
    for ev in r.events:
        land = ev["t"] + ev.get("dur", 0.3) * (0.7 if ev.get("entry") == "slide" else 0.3)
        i0 = int(land * SR)
        p = paper(rng) * rng.uniform(0.6, 1.0)
        if i0 + len(p) < n:
            fol[i0:i0 + len(p)] += p * db(CFG["foley"]["paper_db"])
    cr = crackle(n, rng)
    cmask = np.zeros(n)
    spans = [(0.0, r.cut_title)]
    spans += [(T("s10.5") - 0.4, T("s10.7e") + 0.5), (T("s12.4") - 0.4, T("s12.5e") + 0.5)]
    for a, b in spans:
        cmask += np.clip(np.minimum((t - a) / 0.8, (b - t) / 0.8), 0, 1)
    fol += cr * np.clip(cmask, 0, 1) * db(CFG["foley"]["crackle_db"])
    out = bed + fol[:, None] * np.array([1.0, 0.92])
    out = np.clip(out, -0.98, 0.98).astype(np.float32)
    dest = ROOT / "draft3" / "build" / "sound_bed.wav"
    sf.write(dest, out, SR)
    print("wrote", dest.relative_to(ROOT), f"{n / SR:.1f}s")


if __name__ == "__main__":
    main()
