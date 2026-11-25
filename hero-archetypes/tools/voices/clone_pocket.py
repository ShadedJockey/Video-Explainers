import sys, time, numpy as np, soundfile as sf
from pocket_tts import TTSModel
txt, refdir, out = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(txt).read().strip().splitlines()
m = TTSModel.load_model()
st = m.get_state_for_audio_prompt(f"{refdir}/ref.wav")
t0 = time.time(); outl = []
for ln in lines:
    outl += [m.generate_audio(st, ln).numpy().astype(np.float32).reshape(-1), np.zeros(int(m.sample_rate * 0.55), np.float32)]
sf.write(out, np.concatenate(outl), m.sample_rate); print("pocket clone", round(time.time() - t0), "s")
