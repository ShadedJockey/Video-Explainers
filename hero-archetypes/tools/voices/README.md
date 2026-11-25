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
