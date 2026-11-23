"""Original ambient drone (placeholder music bed for draft 2). No samples, no rights issues.

Low detuned fifths with slow breathing, filtered 'air', and sparse distant chimes
through a simple reverb.  Usage: python tools/make_drone.py <seconds> <out.wav>
"""
import sys

import numpy as np
import soundfile as sf

SR = 48000


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(0, len(x), 4096):          # chunked one-pole filter (fast enough)
        seg = x[i:i + 4096]
        out = np.empty_like(seg)
        for j, v in enumerate(seg):
            acc = (1 - a) * v + a * acc
            out[j] = acc
        y[i:i + 4096] = out
    return y


def reverb(x, mix=0.35):
    out = x.copy()
    for d, g in ((1557, 0.78), (1617, 0.76), (1491, 0.77), (1422, 0.79), (1277, 0.8), (1356, 0.78)):
        buf = np.zeros_like(x)
        for i in range(d, len(x), d):
            seg = x[i - d:i] if i - d >= 0 else x[:i]
            buf[i:i + len(seg)] += seg[: len(buf[i:i + len(seg)])]
        # approximate feedback comb with a few taps
        y = np.zeros_like(x)
        for k in range(1, 7):
            sh = d * k
            if sh < len(x):
                y[sh:] += x[:-sh] * (g ** k)
        out += y * (mix / 6)
    return out


def main():
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 420
    path = sys.argv[2] if len(sys.argv) > 2 else "draft2/build/drone.wav"
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(3)
    L = np.zeros(n)
    R = np.zeros(n)
    # drone: A1, E2, A2, C#3 (soft), slowly breathing, detuned L/R
    for f, amp, rate in ((55.0, 0.30, 0.031), (82.41, 0.20, 0.023), (110.0, 0.14, 0.041), (164.8, 0.06, 0.017), (138.6, 0.035, 0.013)):
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * rate * t + rng.random() * 6.28)
        L += amp * lfo * np.sin(2 * np.pi * f * 0.998 * t)
        R += amp * lfo * np.sin(2 * np.pi * f * 1.002 * t + 0.7)
    # air: filtered noise with slow swell
    noise = lowpass(rng.normal(0, 1, n // 8 + 1), 700 / 8)
    noise = np.repeat(noise, 8)[:n]
    swell = 0.5 + 0.5 * np.sin(2 * np.pi * 0.011 * t)
    L += 0.05 * noise * swell
    R += 0.05 * np.roll(noise, 2400) * swell
    # chimes: A minor pentatonic, sparse
    notes = [440.0, 523.25, 587.33, 659.25, 783.99, 880.0, 1046.5]
    pos = 4.0
    chimes = np.zeros(n)
    while pos < dur - 6:
        f = rng.choice(notes)
        i0 = int(pos * SR)
        m = min(n - i0, int(5 * SR))
        tt = np.arange(m) / SR
        env = np.exp(-tt / 1.6) * (1 - np.exp(-tt / 0.004))
        chimes[i0:i0 + m] += 0.07 * env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.76 * tt))
        pos += rng.uniform(6, 12)
    wet = reverb(chimes, mix=1.0)
    L += 0.8 * chimes + 0.6 * wet
    R += 0.8 * np.roll(chimes, 900) + 0.6 * np.roll(wet, 1300)
    st = np.stack([L, R], 1)
    fade = np.minimum(1, np.minimum(t / 4.0, (dur - t) / 5.0))[:, None]
    st *= fade
    st /= np.sqrt(np.mean(st ** 2)) / 10 ** (-18 / 20)   # ≈ −18 dBFS RMS
    st = np.clip(st, -0.98, 0.98)
    sf.write(path, st.astype(np.float32), SR)
    print("wrote", path, f"{dur:.1f}s")


if __name__ == "__main__":
    main()
