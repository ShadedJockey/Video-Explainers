"""Draft 3 narration: Kokoro TTS per line with registers, prologue pacing, inscription holds and silences.

Reads draft3/narration.md and writes
  draft3/build/vo.wav, draft3/build/timing.json, draft3/hero_infinite_faces_v3.srt
If assets/voiceover_draft3.wav exists, the renderer uses it instead of vo.wav (same mechanism as draft 2);
the line timings still come from this script, so a real read should follow the same line breaks.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "draft3"
CFG = yaml.safe_load((D3 / "config.yaml").read_text())
SR = 24000


def parse(path):
    """→ sections: {id, title, tag, scene, lines:[{text, register, italic}]}"""
    secs, cur, reg = [], None, None
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        m = re.match(r"^## (\d+)\. (.+)$", s)
        if m:
            cur = {"id": int(m.group(1)), "title": m.group(2).strip(), "tag": m.group(2).strip(), "scene": None, "lines": []}
            secs.append(cur)
            continue
        m = re.match(r"^\[(tag|register|scene):\s*(.+)\]$", s)
        if m and cur is not None:
            k, v = m.group(1), m.group(2).strip()
            if k == "register":
                reg = v
            else:
                cur[k] = v
            continue
        if raw.startswith("> ") and cur is not None:
            txt = raw[2:].strip()
            italic = bool(re.fullmatch(r"\*[^*].*[^*]\*", txt))
            cur["lines"].append({"text": txt, "register": reg, "italic": italic})
    return [x for x in secs if x["lines"]]


def plain(t):
    return re.sub(r"\*+", "", t)


def spoken(t):
    t = plain(t)
    for k, v in CFG["voice"]["pronunciations"].items():
        t = re.sub(rf"\b{re.escape(k)}\b", v, t)
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
    cache = D3 / "build" / "vo_lines"
    cache.mkdir(parents=True, exist_ok=True)
    secs = parse(D3 / "narration.md")
    z = lambda sec: np.zeros(int(sec * SR), np.float32)  # noqa: E731
    audio, t = [z(v["lead_in"])], v["lead_in"]
    timing = {"sections": []}
    prev_italic = False
    for si, s in enumerate(secs):
        if si:
            g = v["gap_between_sections"] + (v["inscription_hold"] if prev_italic else 0)
            audio.append(z(g))
            t += g
        rec = {"id": s["id"], "title": s["title"], "tag": s["tag"], "scene": s["scene"], "start": round(t, 3), "lines": []}
        for li, ln in enumerate(s["lines"]):
            reg = ln["register"]
            if li:
                g = v["register_line_gap"].get(reg, v["gap_between_lines"]) + (v["inscription_hold"] if prev_italic else 0)
                audio.append(z(g))
                t += g
            for prefix, extra in v["extra_silence_before"].items():
                if plain(ln["text"]).startswith(prefix):
                    audio.append(z(extra))
                    t += extra
                    ln["silence_before"] = extra
            speed = v["register_speed"].get(reg, v["speed"])
            key = re.sub(r"[^a-z0-9]+", "_", f"{v['kokoro_voice']}_{speed}_{spoken(ln['text'])}".lower())[:160]
            wav = cache / f"{key}.wav"
            if wav.exists():
                x, _ = sf.read(wav, dtype="float32")
            else:
                x, _ = k.create(spoken(ln["text"]), voice=v["kokoro_voice"], speed=speed, lang="en-gb")
                idx = np.where(np.abs(x) > 0.01)[0]
                if len(idx):
                    x = x[max(0, idx[0] - 600): idx[-1] + 1500]
                sf.write(wav, x, SR)
            d = len(x) / SR
            rec["lines"].append({"index": li + 1, "text": ln["text"], "register": reg, "italic": ln["italic"],
                                 "start": round(t, 3), "end": round(t + d, 3)})
            audio.append(x.astype(np.float32))
            t += d
            prev_italic = ln["italic"]
        rec["end"] = round(t, 3)
        timing["sections"].append(rec)
        print(f"  §{s['id']:<2} {s['tag']:22} {rec['end'] - rec['start']:6.1f}s  starts {rec['start']:6.1f}", flush=True)
    g = v["tail"] + (v["inscription_hold"] if prev_italic else 0)
    audio.append(z(g))
    t += g
    timing["duration"] = round(t, 3)
    sf.write(D3 / "build" / "vo.wav", np.concatenate(audio), SR)
    (D3 / "build" / "timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
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
    (D3 / "hero_infinite_faces_v3.srt").write_text("\n".join(out), encoding="utf-8")
    print(f"duration {t:.1f}s ({int(t // 60)}:{t % 60:04.1f})")


if __name__ == "__main__":
    sys.exit(main())
