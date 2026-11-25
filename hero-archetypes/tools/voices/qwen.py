import sys, time, json, numpy as np, soundfile as sf, torch
from qwen_tts import Qwen3TTSModel
torch.set_num_threads(4)
mode, txt, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(txt).read().strip().splitlines()
def save(name, wavs, sr):
    out = []
    for w in wavs:
        out += [np.asarray(w, np.float32).reshape(-1), np.zeros(int(sr * 0.55), np.float32)]
    sf.write(f"{outdir}/{name}.wav", np.concatenate(out), sr)
if mode == "design":
    m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", dtype=torch.float32)
    designs = json.load(open(sys.argv[4]))
    for name, ins in designs.items():
        t0 = time.time()
        wavs, sr = m.generate_voice_design(text=lines, instruct=[ins] * len(lines), language=["English"] * len(lines))
        save(f"qwen_design_{name}", wavs, sr); print(name, round(time.time() - t0), "s", flush=True)
else:
    m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", dtype=torch.float32)
    print(m.get_supported_speakers())
    for spk in sys.argv[4].split(","):
        t0 = time.time()
        wavs, sr = m.generate_custom_voice(text=lines, speaker=[spk] * len(lines), language=["English"] * len(lines),
                                           instruct=["Speak calmly and clearly at a natural pace, like a thoughtful documentary presenter explaining an idea."] * len(lines))
        save(f"qwen_{spk.lower()}", wavs, sr); print(spk, round(time.time() - t0), "s", flush=True)
