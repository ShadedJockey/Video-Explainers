import sys, time, numpy as np, soundfile as sf, torch
torch.set_num_threads(4)
from chatterbox.tts import ChatterboxTTS
txt, refdir, out = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(txt).read().strip().splitlines()
m = ChatterboxTTS.from_pretrained(device="cpu")
m.prepare_conditionals(f"{refdir}/ref.wav", exaggeration=0.4)
t0 = time.time(); outl = []
for ln in lines:
    w = m.generate(ln, exaggeration=0.4, cfg_weight=0.5).numpy().reshape(-1).astype(np.float32)
    outl += [w, np.zeros(int(m.sr * 0.55), np.float32)]
sf.write(out, np.concatenate(outl), m.sr); print("chatterbox clone", round(time.time() - t0), "s")
