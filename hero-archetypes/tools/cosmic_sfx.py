"""Original "cosmic" transition sounds for section breaks (synthesised; no samples, no downloads).

    python tools/cosmic_sfx.py            → draft5/sfx/<name>.wav (on their own) + draft5/sfx/<name>_in_context.wav

Each sound has an anchor: the moment that lines up with the section break. Some rise into it, some bloom out of it.
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, sosfilt

ROOT = Path(__file__).resolve().parents[1]
SR = 48000


def t_axis(sec):
    return np.arange(int(sec * SR)) / SR


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], btype="band", fs=SR, output="sos"), x)


def lp(x, f):
    return sosfilt(butter(2, f, btype="low", fs=SR, output="sos"), x)


def hp(x, f):
    return sosfilt(butter(2, f, btype="high", fs=SR, output="sos"), x)


def space(x, decay=3.0, mix=0.45, seed=1, bright=6000):
    """Synthetic stereo hall: decaying noise impulse responses, decorrelated left/right."""
    rng = np.random.default_rng(seed)
    n = int(decay * SR)
    tt = np.arange(n) / SR
    env = np.exp(-tt * 6.9 / decay)
    irs = [lp(rng.normal(0, 1, n), bright) * env for _ in range(2)]
    irs = [ir / np.sqrt(np.sum(ir ** 2)) for ir in irs]
    mono = x if x.ndim == 1 else x.mean(1)
    wet = np.stack([fftconvolve(mono, ir)[: len(mono) + n] for ir in irs], 1)
    dry = np.zeros_like(wet)
    dry[: len(mono)] = (np.stack([mono, mono], 1) if x.ndim == 1 else x)
    return dry * (1 - mix) + wet * mix * 2.2


def fade(x, a=0.01, b=0.4):
    n = len(x)
    e = np.ones(n)
    ia, ib = int(a * SR), int(b * SR)
    e[:ia] = np.linspace(0, 1, ia)
    e[n - ib:] = np.linspace(1, 0, ib) ** 2
    return x * (e[:, None] if x.ndim == 2 else e)


def norm(x, peak=0.9):
    return x * peak / (np.abs(x).max() + 1e-9)


# ── the six options (each returns stereo audio and its anchor in seconds) ──
def starfield(rng):
    """1. Starfield shimmer: a cloud of high glassy partials that swells in and sparkles away."""
    tt = t_axis(4.0)
    out = np.zeros((len(tt), 2))
    notes = [880, 1108.7, 1318.5, 1760, 2217.5, 2637, 3520]
    for _ in range(34):
        f = rng.choice(notes) * rng.uniform(0.997, 1.003)
        on = rng.uniform(0.0, 0.9)
        env = np.clip((tt - on) / 0.25, 0, 1) * np.exp(-np.clip(tt - on, 0, None) / rng.uniform(0.6, 1.6))
        trem = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(3, 9) * tt + rng.uniform(0, 6))
        s = np.sin(2 * np.pi * f * tt) * env * trem * rng.uniform(0.3, 1.0)
        pan = rng.uniform(0.1, 0.9)
        out[:, 0] += s * (1 - pan)
        out[:, 1] += s * pan
    return space(out, 3.2, 0.55, 2), 0.9


def bell(rng):
    """2. Celestial bell: an inharmonic FM bell, slowly detuned, ringing into a wide hall."""
    tt = t_axis(4.5)
    out = np.zeros((len(tt), 2))
    for i, (fc, amp) in enumerate(((329.6, 1.0), (493.9, 0.55), (659.3, 0.35))):
        for side, det in ((0, 0.998), (1, 1.002)):
            idx = 2.4 * np.exp(-tt / 0.9)
            mod = np.sin(2 * np.pi * fc * 1.41 * det * tt) * idx
            env = (1 - np.exp(-tt / 0.004)) * np.exp(-tt / (2.2 - 0.4 * i))
            out[:, side] += amp * np.sin(2 * np.pi * fc * det * tt + mod) * env
    return space(out, 3.8, 0.5, 3), 0.02


def nebula(rng):
    """3. Nebula whoosh: airy noise sweeping up through the spectrum and across the stereo field."""
    tt = t_axis(3.6)
    noise = rng.normal(0, 1, len(tt))
    out = np.zeros((len(tt), 2))
    # sweep by blending fixed bands (cheap, smooth enough for a whoosh)
    bands = [(150, 400), (300, 800), (600, 1600), (1200, 3200), (2400, 6400), (4000, 10000)]
    centre = np.interp(tt, [0, 1.1, 1.4, 3.6], [0, 5, 5, 1.5])
    for i, (a, b) in enumerate(bands):
        w = np.clip(1 - np.abs(centre - i), 0, 1)
        out[:, 0] += bp(noise, a, b) * w
        out[:, 1] += bp(np.roll(noise, 900), a, b) * w
    env = np.interp(tt, [0, 1.15, 1.35, 3.6], [0, 1, 0.8, 0]) ** 1.4
    pan = np.interp(tt, [0, 3.6], [0.15, 0.85])
    out[:, 0] *= env * (1 - pan) * 2
    out[:, 1] *= env * pan * 2
    sub = np.sin(2 * np.pi * (38 + 6 * tt) * tt) * np.interp(tt, [0, 1.2, 3.6], [0, 0.35, 0])
    out += sub[:, None]
    return space(out, 2.5, 0.35, 4), 1.2


def pulsar(rng):
    """4. Pulsar ping: a clean sonar-like signal bouncing away in ping-pong echoes, with faint radio hiss."""
    tt = t_axis(4.2)
    out = np.zeros((len(tt), 2))
    for k in range(7):
        t0 = k * 0.38
        g = 0.62 ** k
        f = 1046.5 * (1 - 0.012 * k)
        e = np.clip(tt - t0, 0, None)
        ping = np.sin(2 * np.pi * f * e) * np.exp(-e / 0.22) * (tt >= t0) * g
        ping += 0.3 * np.sin(2 * np.pi * f * 2.01 * e) * np.exp(-e / 0.08) * (tt >= t0) * g
        out[:, k % 2] += ping
        out[:, 1 - k % 2] += ping * 0.35
    hiss = hp(rng.normal(0, 0.02, len(tt)), 3000) * np.interp(tt, [0, 0.2, 3.0, 4.2], [0, 1, 0.6, 0])
    out += np.stack([hiss, np.roll(hiss, 500)], 1)
    return space(out, 2.6, 0.4, 5), 0.0


def aurora(rng):
    """5. Aurora bloom: a soft chord heard backwards (rising into the break), then blooming forwards."""
    tt = t_axis(2.2)
    chord = np.zeros(len(tt))
    for f in (220, 329.6, 493.9, 659.3):
        for d in (0.996, 1.0, 1.004):
            chord += np.sin(2 * np.pi * f * d * tt) * 0.25
    chord = lp(chord, 2500) * np.exp(-tt / 0.7) * (1 - np.exp(-tt / 0.01))
    wet = space(chord, 3.0, 0.9, 6)
    rev = wet[::-1][-int(2.4 * SR):]                      # reversed tail: rises into the break
    fwd = space(chord, 3.5, 0.55, 7)
    out = np.concatenate([rev * 0.9, fwd])
    return out, len(rev) / SR


def stardust(rng):
    """6. Stardust cascade: a fall of tiny high glints that slide downward, over a soft low swell."""
    tt = t_axis(4.0)
    out = np.zeros((len(tt), 2))
    for _ in range(90):
        t0 = rng.uniform(0, 1.6)
        f0 = rng.uniform(2500, 6000) * (1 - t0 / 3)
        e = np.clip(tt - t0, 0, None)
        g = np.sin(2 * np.pi * f0 * (1 - 0.25 * e) * e) * np.exp(-e / 0.09) * (tt >= t0) * rng.uniform(0.2, 0.7)
        p = rng.uniform(0, 1)
        out[:, 0] += g * (1 - p)
        out[:, 1] += g * p
    swell = np.sin(2 * np.pi * 110 * tt) + 0.5 * np.sin(2 * np.pi * 164.8 * tt)
    swell *= np.interp(tt, [0, 0.8, 4.0], [0, 0.25, 0])
    out += swell[:, None]
    return space(out, 3.0, 0.5, 8), 0.3


OPTIONS = [("1_starfield_shimmer", starfield), ("2_celestial_bell", bell), ("3_nebula_whoosh", nebula),
           ("4_pulsar_ping", pulsar), ("5_aurora_bloom", aurora), ("6_stardust_cascade", stardust)]


def make(name):
    rng = np.random.default_rng(sum(map(ord, name)))
    fn = dict(OPTIONS)[name]
    x, anchor = fn(rng)
    x = x[: int((anchor + 4.0) * SR)]              # at most 4 s after the break, so tails never sit under the narration
    return norm(fade(x, 0.01, 1.2)), anchor


def main():
    out = ROOT / "draft5" / "sfx"
    out.mkdir(parents=True, exist_ok=True)
    for name, _ in OPTIONS:
        x, anchor = make(name)
        sf.write(out / f"{name}.wav", x.astype(np.float32), SR)
        print(f"{name:22} {len(x) / SR:4.1f}s  anchor {anchor:.2f}s")


if __name__ == "__main__":
    sys.exit(main())
