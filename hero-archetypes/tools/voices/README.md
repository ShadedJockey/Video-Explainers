# Voice auditions (draft 4)

Free, local TTS engines used to make `voice_samples/` (listening page: `voice_samples/auditions.html`, open it next to the mp3s).
Each engine lives in its own venv (they pin different torch versions). CPU-only torch comes from download.pytorch.org;
model weights come from Hugging Face (`HF_HUB_DISABLE_XET=1` avoids the xet transfer hosts).

```bash
uv venv -p 3.12 .tts/pocket && VIRTUAL_ENV=.tts/pocket uv pip install pocket-tts soundfile --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
uv venv -p 3.11 .tts/cbox   && VIRTUAL_ENV=.tts/cbox   uv pip install chatterbox-tts soundfile "setuptools<81" --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
uv venv -p 3.12 .tts/qwen   && VIRTUAL_ENV=.tts/qwen   uv pip install qwen-tts soundfile --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
```

| Script | Engine | Example |
|---|---|---|
| `kok.py` | Kokoro (project venv) | `.venv/bin/python tools/voices/kok.py tools/voices/sample.txt OUT` |
| `pocket.py` | Pocket TTS (Kyutai) | `.tts/pocket/bin/python tools/voices/pocket.py sample.txt OUT peter_yearsley,stuart_bell` |
| `qwen.py` | Qwen3-TTS Voice Design / presets | `.tts/qwen/bin/python tools/voices/qwen.py design sample.txt OUT designs.json` |
| `cbox.py` | Chatterbox (Resemble AI) | `.tts/cbox/bin/python tools/voices/cbox.py sample.txt OUT` |
| `analyse.py` | faster-whisper check (word error rate, pitch) | `asr/bin/python analyse.py sample.txt OUT analysis.json` |

Licences: Kokoro Apache 2.0 · Pocket TTS CC BY 4.0 (voices CC0 / CC BY 4.0; Cosette and Jean are non-commercial and not used) · Qwen3-TTS Apache 2.0 · Chatterbox MIT (adds an inaudible watermark).

## Cloning your own voice

`clone_all.sh RECORDING NAME` (run from the folder that holds the venvs and these scripts):
1. `prep_ref.py`: converts to 24 kHz mono, transcribes it (faster-whisper) and cuts the clearest 10–20 s of whole sentences → `ref.wav`, `ref.txt`.
2. Clones the audition lines with Qwen3-TTS Base (`clone_qwen.py`, Apache 2.0), Chatterbox (`clone_cbox.py`, MIT) and Pocket TTS (`clone_pocket.py`; its cloning model is gated, so it needs a Hugging Face token with the terms accepted at huggingface.co/kyutai/pocket-tts).
3. `spksim.py`: speaker similarity (SpeechBrain ECAPA, cosine) of each clone against the reference. On a test voice, clones scored 0.73–0.78; unrelated voices scored 0.0–0.37.

Draft 4 voice shortlist (user's picks): Pocket TTS Alba, Charles, Anna, Fantine.
