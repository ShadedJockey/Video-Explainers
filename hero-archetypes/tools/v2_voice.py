"""Draft 2 narration: Kokoro TTS per line + timing + captions.

Reads draft2/narration.md (`>` lines; **bold**, *italic*, [tag: X] markup) and writes
  draft2/build/vo.wav, draft2/build/timing.json, final/hero_infinite_faces_captions.srt
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

ROOT = Path(__file__).resolve().parents[1]
D2 = ROOT / "draft2"
CFG = yaml.safe_load((D2 / "config.yaml").read_text())
SR = 24000


def parse(path):
    sections, cur = [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (\d+)\. (.+)$", raw)
        if m:
            cur = {"id": int(m.group(1)), "title": m.group(2).strip(), "tag": m.group(2).strip(), "lines": []}
            sections.append(cur)
            continue
        m = re.match(r"^\[tag:\s*(.+)\]$", raw.strip())
        if m and cur:
            cur["tag"] = m.group(1).strip()
            continue
        if raw.startswith("> ") and cur is not None:
            cur["lines"].append(raw[2:].strip())
    return [s for s in sections if s["lines"]]


def plain(t):
    return re.sub(r"\*+", "", t)


def spoken(t):
    t = plain(t)
    for k, v in CFG["voice"]["pronunciations"].items():
        t = t.replace(k, v)
    return t


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    from kokoro_onnx import Kokoro
    v = CFG["voice"]
    k = Kokoro(str(ROOT / "build/models/kokoro-v1.0.onnx"), str(ROOT / "build/models/voices-v1.0.bin"))
    cache = D2 / "build" / "vo_lines"
    cache.mkdir(parents=True, exist_ok=True)
    secs = parse(D2 / "narration.md")
    audio = [np.zeros(int(v["lead_in"] * SR), np.float32)]
    t = v["lead_in"]
    timing = {"sections": []}
    for si, s in enumerate(secs):
        if si:
            audio.append(np.zeros(int(v["gap_between_sections"] * SR), np.float32))
            t += v["gap_between_sections"]
        rec = {"id": s["id"], "title": s["title"], "tag": s["tag"], "start": round(t, 3), "lines": []}
        for li, line in enumerate(s["lines"]):
            if li:
                audio.append(np.zeros(int(v["gap_between_lines"] * SR), np.float32))
                t += v["gap_between_lines"]
            key = re.sub(r"[^a-z0-9]+", "_", f"{v['kokoro_voice']}_{v['speed']}_{spoken(line)}".lower())[:160]
            wav = cache / f"{key}.wav"
            if wav.exists():
                x, _ = sf.read(wav, dtype="float32")
            else:
                x, sr = k.create(spoken(line), voice=v["kokoro_voice"], speed=v["speed"], lang="en-us")
                idx = np.where(np.abs(x) > 0.01)[0]
                if len(idx):
                    x = x[max(0, idx[0] - 600): idx[-1] + 1500]
                sf.write(wav, x, SR)
            d = len(x) / SR
            rec["lines"].append({"index": li + 1, "text": line, "start": round(t, 3), "end": round(t + d, 3)})
            audio.append(x.astype(np.float32))
            t += d
        rec["end"] = round(t, 3)
        timing["sections"].append(rec)
        print(f"  §{s['id']:<2} {s['tag']:18} {rec['end'] - rec['start']:6.1f}s", flush=True)
    audio.append(np.zeros(int(v["tail"] * SR), np.float32))
    t += v["tail"]
    timing["duration"] = round(t, 3)
    (D2 / "build").mkdir(exist_ok=True)
    sf.write(D2 / "build" / "vo.wav", np.concatenate(audio), SR)
    (D2 / "build" / "timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    # captions: one cue per line, long lines split at punctuation
    n, out = 1, []
    for s in timing["sections"]:
        for ln in s["lines"]:
            txt = plain(ln["text"])
            parts = re.split(r"(?<=[.?!:])\s+", txt) if len(txt) > 84 else [txt]
            tot = sum(len(p) for p in parts)
            a = ln["start"]
            for p in parts:
                b = a + (ln["end"] - ln["start"]) * len(p) / tot
                out.append(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{p}\n")
                n += 1
                a = b
    (ROOT / "final" / "hero_infinite_faces_captions.srt").write_text("\n".join(out), encoding="utf-8")
    print(f"duration {t:.1f}s ({int(t // 60)}:{t % 60:04.1f})")


if __name__ == "__main__":
    sys.exit(main())
