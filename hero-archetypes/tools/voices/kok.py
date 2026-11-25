import sys, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
k = Kokoro("build/models/kokoro-v1.0.onnx", "build/models/voices-v1.0.bin")
print(sorted(k.get_voices()))
lines = open(sys.argv[1]).read().strip().splitlines()
for v, sp in [("bf_emma",1.0),("bf_isabella",1.0),("bf_alice",1.0),("bf_lily",1.0),("bm_george",.97),("bm_fable",.97),("bm_lewis",.97),("bm_daniel",.97),("am_michael",.97),("am_onyx",.97),("am_adam",.97),("af_heart",1.0),("af_bella",1.0)]:
    out=[]
    for ln in lines:
        a, sr = k.create(ln, voice=v, speed=sp, lang="en-gb" if v[0]=="b" else "en-us")
        out += [a, np.zeros(int(sr*0.55), np.float32)]
    sf.write(f"{sys.argv[2]}/kokoro_{v}.wav", np.concatenate(out), sr); print(v)
