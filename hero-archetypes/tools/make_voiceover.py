"""Generate the placeholder narration with Kokoro TTS (local, offline).

Reads the `>` lines from script/narration.md, renders each line separately,
joins them with configurable gaps and writes:

  build/vo/voiceover_tts.wav      the full narration track (24 kHz mono)
  build/narration_timing.json     start/end of every line, used by the timeline
  final/captions.srt              subtitles matched to the narration

If assets/voiceover.wav exists the timeline still uses these line timings,
so a human read should follow the same line breaks.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
SR = 24000


def parse_script(path):
    sections, cur = [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (\d+)\. (.+)$", raw)
        if m:
            cur = {"id": int(m.group(1)), "title": m.group(2).strip(), "lines": []}
            sections.append(cur)
            continue
        if raw.startswith("> ") and cur is not None:
            text = raw[2:].strip().replace("*", "")
            cur["lines"].append(text)
    return [s for s in sections if s["lines"]]


def spoken(text):
    out = text
    for k, v in CFG["voice"]["pronunciations"].items():
        out = out.replace(k, v)
    return out


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap_caption(text, width=42):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return lines


def split_for_captions(text, start, end, max_chars=84):
    """Split a long line into caption chunks at sentence/clause breaks, timing by length."""
    if len(text) <= max_chars:
        return [(text, start, end)]
    parts = re.split(r"(?<=[.?!:;])\s+|(?<=,)\s+(?=\w)", text)
    chunks, cur = [], ""
    for p in parts:
        if len(cur) + len(p) + 1 > max_chars and cur:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    chunks.append(cur)
    total = sum(len(c) for c in chunks)
    out, t = [], start
    for c in chunks:
        d = (end - start) * len(c) / total
        out.append((c, t, t + d))
        t += d
    return out


def main():
    from kokoro_onnx import Kokoro

    vcfg = CFG["voice"]
    models = ROOT / "build" / "models"
    kokoro = Kokoro(str(models / "kokoro-v1.0.onnx"), str(models / "voices-v1.0.bin"))
    sections = parse_script(ROOT / "script" / "narration.md")

    cache = ROOT / "build" / "vo" / "lines"
    cache.mkdir(parents=True, exist_ok=True)

    audio = [np.zeros(int(vcfg["lead_in"] * SR), dtype=np.float32)]
    t = vcfg["lead_in"]
    timing = {"sections": []}
    for si, sec in enumerate(sections):
        if si > 0:
            gap = vcfg["gap_between_sections"]
            audio.append(np.zeros(int(gap * SR), dtype=np.float32))
            t += gap
        srec = {"id": sec["id"], "title": sec["title"], "start": t, "lines": []}
        for li, line in enumerate(sec["lines"]):
            if li > 0:
                gap = vcfg.get("section_line_gaps", {}).get(sec["id"], vcfg["gap_between_lines"])
                audio.append(np.zeros(int(gap * SR), dtype=np.float32))
                t += gap
            key = re.sub(r"[^a-z0-9]+", "_", f"{vcfg['kokoro_voice']}_{vcfg['speed']}_{spoken(line)}".lower())[:150]
            wav = cache / f"{key}.wav"
            if wav.exists():
                samples, _ = sf.read(wav, dtype="float32")
            else:
                samples, sr = kokoro.create(spoken(line), voice=vcfg["kokoro_voice"], speed=vcfg["speed"], lang="en-us")
                assert sr == SR
                # trim leading/trailing silence so gaps are controlled by config
                idx = np.where(np.abs(samples) > 0.01)[0]
                if len(idx):
                    samples = samples[max(0, idx[0] - 600): idx[-1] + 1200]
                sf.write(wav, samples, SR)
            dur = len(samples) / SR
            srec["lines"].append({"index": li + 1, "text": line, "start": round(t, 3), "end": round(t + dur, 3)})
            audio.append(samples.astype(np.float32))
            t += dur
            print(f"  §{sec['id']}.{li+1}  {dur:5.2f}s  {line[:60]}", flush=True)
        srec["end"] = round(t, 3)
        timing["sections"].append(srec)
    audio.append(np.zeros(int(vcfg["tail"] * SR), dtype=np.float32))
    t += vcfg["tail"]
    timing["duration"] = round(t, 3)

    full = np.concatenate(audio)
    out = ROOT / "build" / "vo" / "voiceover_tts.wav"
    sf.write(out, full, SR)
    (ROOT / "build" / "narration_timing.json").write_text(json.dumps(timing, indent=2), encoding="utf-8")

    # captions.srt
    n, srt = 1, []
    for sec in timing["sections"]:
        for ln in sec["lines"]:
            for text, a, b in split_for_captions(ln["text"], ln["start"], ln["end"]):
                srt.append(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n" + "\n".join(wrap_caption(text)) + "\n")
                n += 1
    (ROOT / "final").mkdir(exist_ok=True)
    (ROOT / "final" / "captions.srt").write_text("\n".join(srt), encoding="utf-8")
    print(f"Narration: {t:.1f}s  ({int(t//60)}:{t%60:04.1f})  → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
