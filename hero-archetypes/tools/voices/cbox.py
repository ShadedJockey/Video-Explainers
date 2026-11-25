import sys, time, numpy as np, soundfile as sf, torch
torch.set_num_threads(4)
from chatterbox.tts import ChatterboxTTS
lines = open(sys.argv[1]).read().strip().splitlines()
m = ChatterboxTTS.from_pretrained(device="cpu")
for name, ex, cfg in [("default", 0.5, 0.5), ("dramatic", 0.75, 0.3)]:
    t0 = time.time(); out = []
    for ln in lines:
        w = m.generate(ln, exaggeration=ex, cfg_weight=cfg).numpy().reshape(-1).astype(np.float32)
        out += [w, np.zeros(int(m.sr * 0.55), np.float32)]
    sf.write(f"{sys.argv[2]}/chatterbox_{name}.wav", np.concatenate(out), m.sr); print(name, round(time.time() - t0), "s", flush=True)
