"""Prepare a reference clip: denoise-free cleanup, pick the clearest ~15 s of speech, transcribe it.
usage: prep_ref.py INPUT OUTDIR  -> OUTDIR/ref.wav, OUTDIR/ref.txt, OUTDIR/ref_full.wav"""
import sys, subprocess, json, numpy as np, soundfile as sf, librosa
from faster_whisper import WhisperModel
src, out = sys.argv[1], sys.argv[2]
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", "24000",
                "-af", "highpass=f=70,loudnorm=I=-18:TP=-2", f"{out}/ref_full.wav"], check=True)
y, sr = sf.read(f"{out}/ref_full.wav")
m = WhisperModel("small.en", device="cpu", compute_type="int8")
segs = list(m.transcribe(librosa.resample(y.astype(np.float32), orig_sr=sr, target_sr=16000), language="en", beam_size=5, vad_filter=True)[0])
print("total", round(len(y) / sr, 1), "s;", len(segs), "segments")
# take consecutive whole segments adding up to 10-20 s
best = None
for i in range(len(segs)):
    t0 = segs[i].start
    for j in range(i, len(segs)):
        d = segs[j].end - t0
        if d > 20: break
        if d >= 10 and (best is None or d > best[2]):
            best = (i, j, d)
i, j, _ = best if best else (0, len(segs) - 1, 0)
a, b = max(0, segs[i].start - 0.15), min(len(y) / sr, segs[j].end + 0.25)
sf.write(f"{out}/ref.wav", y[int(a * sr):int(b * sr)].astype(np.float32), sr)
text = " ".join(s.text.strip() for s in segs[i:j + 1])
open(f"{out}/ref.txt", "w").write(text)
json.dump({"start": a, "end": b, "full_transcript": " ".join(s.text.strip() for s in segs)}, open(f"{out}/ref.json", "w"), indent=1)
print(f"ref {a:.1f}-{b:.1f}s:", text)
