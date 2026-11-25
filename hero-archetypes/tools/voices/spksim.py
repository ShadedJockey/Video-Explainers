"""Speaker similarity (ECAPA, cosine) of each file against a reference. usage: spksim.py REF FILE..."""
import sys, numpy as np, librosa, torch
from speechbrain.inference.speaker import EncoderClassifier
enc = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir="/tmp/claude-0/-home-user-Video-Explainers/d6428705-0d27-5262-896d-7a7ecb251106/scratchpad/tts/ecapa")
def emb(f):
    y, _ = librosa.load(f, sr=16000)
    return enc.encode_batch(torch.tensor(y)[None]).squeeze().numpy()
r = emb(sys.argv[1])
for f in sys.argv[2:]:
    e = emb(f); print(f"{float(np.dot(r, e) / np.linalg.norm(r) / np.linalg.norm(e)):.3f}  {f}")
