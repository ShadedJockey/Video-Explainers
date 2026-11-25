import sys, time, numpy as np, soundfile as sf
from pocket_tts import TTSModel
m = TTSModel.load_model()
lines = open(sys.argv[1]).read().strip().splitlines()
for v in sys.argv[3].split(","):
    t0 = time.time()
    st = m.get_state_for_audio_prompt(v)
    out = []
    for ln in lines:
        a = m.generate_audio(st, ln).numpy().astype(np.float32).reshape(-1)
        out += [a, np.zeros(int(m.sample_rate * 0.55), np.float32)]
    sf.write(f"{sys.argv[2]}/pocket_{v}.wav", np.concatenate(out), m.sample_rate)
    print(v, round(time.time() - t0, 1), "s", flush=True)
