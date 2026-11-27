"""Draft 6 narration in your cloned voice (Qwen3-TTS Base, voice cloning), one line at a time, with a speech check.

    .tts/qwen/bin/python tools/v6_voice.py        (./render.sh v6-voice)

Reads draft6/narration.md and the `voice:` section of draft6/config.yaml (engine qwen_clone, or pocket for a stock voice).
Each line is generated, transcribed with faster-whisper and compared with the script; if words come out wrong, the line is
re-generated with another seed (up to max_takes) and the best take is kept. Takes are cached in draft6/build/vo_lines/.

Writes draft6/build/vo.wav, draft6/build/timing.json, draft6/build/voice_report.md and draft6/hero_infinite_faces_v6.srt.
Your reference recording lives in assets/private/ (git-ignored); it is never committed.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "draft6"
CFG = yaml.safe_load((D / "config.yaml").read_text())
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
    return re.sub(r"\*+", "", t).replace("—", ", ")


def spoken(t):
    t = plain(t)
    for k, v in V["pronunciations"].items():
        t = t.replace(k, v)
    return t


def words(t):
    t = t.lower().replace("nowsika", "nausicaa").replace("doytch", "deutsch").replace("meso-america", "mesoamerica")
    t = re.sub(r"\b1949\b", "nineteen forty nine", t)
    t = re.sub(r"\b1984\b", "nineteen eighty four", t)
    t = t.replace("4,000", "four thousand").replace("4000", "four thousand")
    return re.sub(r"[^a-z' ]", " ", t.replace("ä", "a")).split()


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def trim(x, sr):
    idx = np.where(np.abs(x) > 0.01)[0]
    return x[max(0, idx[0] - int(0.03 * sr)): idx[-1] + int(0.1 * sr)] if len(idx) else x


class Engine:
    def __init__(self):
        import torch
        torch.set_num_threads(4)
        self.torch = torch
        self.kind = V["engine"]
        if self.kind == "qwen_clone":
            from qwen_tts import Qwen3TTSModel
            self.m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", dtype=torch.float32)
            ref_text = (ROOT / V["clone_ref_text"]).read_text().strip()
            self.prompt = self.m.create_voice_clone_prompt(ref_audio=str(ROOT / V["clone_ref_audio"]), ref_text=ref_text)
            h = hashlib.sha1((ROOT / V["clone_ref_audio"]).read_bytes()).hexdigest()[:8]
            self.tag = f"qwenclone_{h}"
        else:
            from pocket_tts import TTSModel
            self.m = TTSModel.load_model()
            self.state = self.m.get_state_for_audio_prompt(V["pocket_voice"])
            self.tag = f"pocket_{V['pocket_voice']}"

    def say(self, text, seed):
        self.torch.manual_seed(seed)
        if self.kind == "qwen_clone":
            wavs, sr = self.m.generate_voice_clone(text=text, language="English", voice_clone_prompt=self.prompt)
            return np.asarray(wavs[0], np.float32).reshape(-1), sr
        return self.m.generate_audio(self.state, text).numpy().astype(np.float32).reshape(-1), self.m.sample_rate


def main():
    import jiwer
    import librosa
    from faster_whisper import WhisperModel
    eng = Engine()
    asr = WhisperModel("small.en", device="cpu", compute_type="int8")
    cache = D / "build" / "vo_lines"
    cache.mkdir(parents=True, exist_ok=True)
    report = ["# Voice report (draft 6)", "", f"Engine: {eng.tag}. WER = share of words the speech check heard differently from the script.", "",
              "| Line | Takes | WER | Heard |", "|---|---|---|---|"]
    sr_out = None
    pieces, timing = [], {"sections": [], "voice": eng.tag}
    t = V["lead_in"]
    lead = None
    for si, s in enumerate(parse(D / "narration.md")):
        if si:
            pieces.append(("gap", V["gap_between_sections"]))
            t += V["gap_between_sections"]
        rec = {"id": s["id"], "title": s["title"], "tag": s["tag"], "start": round(t, 3), "lines": []}
        for li, ln in enumerate(s["lines"]):
            if li:
                pieces.append(("gap", V["gap_between_lines"]))
                t += V["gap_between_lines"]
            text = spoken(ln["text"])
            key = hashlib.sha1(f"{eng.tag}|{text}".encode()).hexdigest()[:16]
            wav = cache / f"{key}.wav"
            meta = cache / f"{key}.json"
            if wav.exists() and meta.exists():
                x, sr = sf.read(wav, dtype="float32")
                info = json.loads(meta.read_text())
            else:
                best = None
                for take in range(V.get("max_takes", 3)):
                    x, sr = eng.say(text, V.get("seed", 7) + 1000 * take + 17 * (si * 50 + li))
                    x = trim(x, sr)
                    y16 = librosa.resample(x, orig_sr=sr, target_sr=16000)
                    heard = " ".join(seg.text for seg in asr.transcribe(y16, language="en", beam_size=5)[0]).strip()
                    err = jiwer.wer(" ".join(words(text)), " ".join(words(heard)) or "x")
                    if best is None or err < best[0]:
                        best = (err, x, sr, heard, take + 1)
                    if err <= 0.06:
                        break
                err, x, sr, heard, takes = best
                info = {"wer": round(err, 3), "heard": heard, "takes": takes}
                sf.write(wav, x, sr)
                meta.write_text(json.dumps(info))
            sr_out = sr
            d = len(x) / sr
            rec["lines"].append({"index": li + 1, "text": ln["text"], "start": round(t, 3), "end": round(t + d, 3)})
            pieces.append(("audio", x))
            t += d
            flag = " ⚠" if info["wer"] > 0.1 else ""
            report.append(f"| {s['id']}.{li + 1} | {info['takes']} | {info['wer']:.2f}{flag} | {info['heard'][:110]} |")
            print(f"  {s['id']}.{li + 1:<2} takes {info['takes']}  wer {info['wer']:.2f}{flag}", flush=True)
        rec["end"] = round(t, 3)
        timing["sections"].append(rec)
        print(f"§{s['id']} {s['tag']:16} {rec['end'] - rec['start']:6.1f}s  starts {rec['start']:6.1f}", flush=True)
    t += V["tail"]
    timing["duration"] = round(t, 3)
    timing["sample_rate"] = sr_out
    audio = [np.zeros(int(V["lead_in"] * sr_out), np.float32)]
    for kind, v in pieces:
        audio.append(np.zeros(int(v * sr_out), np.float32) if kind == "gap" else v)
    audio.append(np.zeros(int(V["tail"] * sr_out), np.float32))
    sf.write(D / "build" / "vo.wav", np.concatenate(audio), sr_out)
    (D / "build" / "timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    (D / "build" / "voice_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    n, out = 1, []
    for s in timing["sections"]:
        for ln in s["lines"]:
            txt = plain(ln["text"])
            parts = re.split(r"(?<=[.?!:,])\s+", txt) if len(txt) > 70 else [txt]
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
    (D / "hero_infinite_faces_v6.srt").write_text("\n".join(out), encoding="utf-8")
    print(f"duration {t:.1f}s ({int(t // 60)}:{t % 60:04.1f})")


if __name__ == "__main__":
    sys.exit(main())
