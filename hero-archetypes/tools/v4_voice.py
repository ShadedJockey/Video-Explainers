"""Draft 4 narration with Kyutai Pocket TTS (voice set in draft4/config.yaml), one line at a time.

    .tts/pocket/bin/python tools/v4_voice.py     (./render.sh v4-voice)

Writes draft4/build/vo.wav, draft4/build/timing.json and draft4/hero_infinite_faces_v4.srt.
If assets/voiceover_draft4.wav exists, the renderer uses it instead (a real read should follow the same line breaks).
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

ROOT = Path(__file__).resolve().parents[1]
D4 = ROOT / "draft4"
CFG = yaml.safe_load((D4 / "config.yaml").read_text())
V = CFG["voice"]


def parse(path):
    secs, cur = [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        m = re.match(r"^## (\d+)\. (.+)$", s)
        if m:
            cur = {"id": int(m.group(1)), "title": m.group(2).strip(), "tag": m.group(2).strip(), "lines": []}
            secs.append(cur)
            continue
        m = re.match(r"^\[tag:\s*(.+)\]$", s)
        if m and cur is not None:
            cur["tag"] = m.group(1).strip()
            continue
        if raw.startswith("> ") and cur is not None:
            cur["lines"].append({"text": raw[2:].strip()})
    return [x for x in secs if x["lines"]]


def plain(t):
    return re.sub(r"\*+", "", t)


def spoken(t):
    t = plain(t)
    for k, v in V["pronunciations"].items():
        t = t.replace(k, v)
    return t


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def trim(x, sr):
    idx = np.where(np.abs(x) > 0.008)[0]
    return x[max(0, idx[0] - int(0.03 * sr)): idx[-1] + int(0.08 * sr)] if len(idx) else x


def main():
    from pocket_tts import TTSModel
    model = TTSModel.load_model()
    sr = model.sample_rate
    state = model.get_state_for_audio_prompt(V["pocket_voice"])
    cache = D4 / "build" / "vo_lines"
    cache.mkdir(parents=True, exist_ok=True)
    z = lambda s: np.zeros(int(s * sr), np.float32)  # noqa: E731
    audio, t = [z(V["lead_in"])], V["lead_in"]
    timing = {"sections": [], "voice": f"pocket:{V['pocket_voice']}"}
    for si, s in enumerate(parse(D4 / "narration.md")):
        if si:
            audio.append(z(V["gap_between_sections"]))
            t += V["gap_between_sections"]
        rec = {"id": s["id"], "title": s["title"], "tag": s["tag"], "start": round(t, 3), "lines": []}
        for li, ln in enumerate(s["lines"]):
            if li:
                audio.append(z(V["gap_between_lines"]))
                t += V["gap_between_lines"]
            key = re.sub(r"[^a-z0-9]+", "_", f"pocket_{V['pocket_voice']}_{spoken(ln['text'])}".lower())[:150]
            wav = cache / f"{key}.wav"
            if wav.exists():
                x, _ = sf.read(wav, dtype="float32")
            else:
                x = trim(model.generate_audio(state, spoken(ln["text"])).numpy().astype(np.float32).reshape(-1), sr)
                sf.write(wav, x, sr)
            d = len(x) / sr
            rec["lines"].append({"index": li + 1, "text": ln["text"], "start": round(t, 3), "end": round(t + d, 3)})
            audio.append(x)
            t += d
        rec["end"] = round(t, 3)
        timing["sections"].append(rec)
        print(f"  §{s['id']} {s['tag']:16} {rec['end'] - rec['start']:6.1f}s  starts {rec['start']:6.1f}", flush=True)
    audio.append(z(V["tail"]))
    t += V["tail"]
    timing["duration"] = round(t, 3)
    timing["sample_rate"] = sr
    sf.write(D4 / "build" / "vo.wav", np.concatenate(audio), sr)
    (D4 / "build" / "timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    n, out = 1, []
    for s in timing["sections"]:
        for ln in s["lines"]:
            txt = plain(ln["text"])
            parts = re.split(r"(?<=[.?!:,])\s+", txt) if len(txt) > 70 else [txt]
            # merge tiny fragments back
            merged = []
            for p in parts:
                if merged and (len(p) < 24 or len(merged[-1]) < 24):
                    merged[-1] += " " + p
                else:
                    merged.append(p)
            tot = sum(len(p) for p in merged)
            a = ln["start"]
            for p in merged:
                b = a + (ln["end"] - ln["start"]) * len(p) / tot
                out.append(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{p}\n")
                n += 1
                a = b
    (D4 / "hero_infinite_faces_v4.srt").write_text("\n".join(out), encoding="utf-8")
    print(f"duration {t:.1f}s ({int(t // 60)}:{t % 60:04.1f})")


if __name__ == "__main__":
    sys.exit(main())
