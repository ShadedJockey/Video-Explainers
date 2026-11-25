import sys, time, numpy as np, soundfile as sf, torch
from qwen_tts import Qwen3TTSModel
torch.set_num_threads(4)
txt, refdir, out = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(txt).read().strip().splitlines()
m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", dtype=torch.float32)
ref_text = open(f"{refdir}/ref.txt").read().strip()
prompt = m.create_voice_clone_prompt(ref_audio=f"{refdir}/ref.wav", ref_text=ref_text)
t0 = time.time()
outl = []
for ln in lines:
    wv, sr = m.generate_voice_clone(text=ln, language="English", voice_clone_prompt=prompt)
    w = wv[0]
    outl += [np.asarray(w, np.float32).reshape(-1), np.zeros(int(sr * 0.55), np.float32)]
sf.write(out, np.concatenate(outl), sr); print("qwen clone", round(time.time() - t0), "s")
