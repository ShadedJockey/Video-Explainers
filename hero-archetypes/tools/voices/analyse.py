"""Transcribe each sample (word error rate vs the script), median pitch, speaking rate, length."""
import sys, json, glob, os, re, numpy as np, librosa, jiwer
from faster_whisper import WhisperModel
txt = open(sys.argv[1]).read()
ref = re.sub(r"[^a-z' ]", " ", txt.lower()); ref = " ".join(ref.split())
nwords = len(ref.split())
m = WhisperModel("small.en", device="cpu", compute_type="int8")
res = json.load(open(sys.argv[3])) if os.path.exists(sys.argv[3]) else {}
for f in sorted(glob.glob(f"{sys.argv[2]}/*.wav")):
    k = os.path.basename(f)[:-4]
    if k in res: continue
    y, sr = librosa.load(f, sr=16000)
    segs, _ = m.transcribe(y, language="en", beam_size=5, condition_on_previous_text=False)
    hyp = " ".join(s.text for s in segs)
    h = " ".join(re.sub(r"[^a-z' ]", " ", hyp.lower()).split())
    f0, vf, _ = librosa.pyin(y, fmin=60, fmax=400, sr=16000, frame_length=1024)
    voiced = (librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0] > 0.01).sum() * 256 / 16000
    res[k] = {"wer": round(jiwer.wer(ref, h), 3), "f0": round(float(np.nanmedian(f0)), 1), "dur": round(len(y) / 16000, 1),
              "wpm": round(nwords / (voiced / 60), 0), "hyp": hyp.strip()}
    print(k, res[k]["wer"], res[k]["f0"], res[k]["wpm"], flush=True)
    json.dump(res, open(sys.argv[3], "w"), indent=1)
