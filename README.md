# AnmaVoice-AI

💜 Free, fast text-to-speech in your browser — powered by Kokoro v1.0.

**🔴 Live demo:** *https://anmavoice-ai.streamlit.app/*

## ✨ Features

- 🗣 **12 voices** — 6 female, 6 male (Kokoro v1.0)
- 🌍 **8 languages** — English (US/UK), Spanish, French, Hindi, Italian, Japanese, Mandarin Chinese
- 🎭 **Emotions** — Normal, Deep, Calm, Happy, Sad, Excited
- 🎚 **Speed control** — 0.5x to 2.0x
- ▶ **Voice previews** — hear a sample before you generate
- 📚 **Voice library** — every generation saved; play, download, or delete
- 📊 **Progress bar** — per-chunk progress on long texts
- ⚡ **Fast ONNX engine** — runs on CPU, no GPU needed

## 🚀 Run locally

1. Install Python 3.10 or newer
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Download the model files into this folder:
   - [kokoro-v1.0.onnx (325MB)](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx)
   - [voices-v1.0.bin (28MB)](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin)
4. Start the app:
   ```
   streamlit run app.py
   ```

> Tip: if the model files are missing, the app downloads them automatically on first run.

## ☁ Deploy on Streamlit Cloud

1. Push this repo to GitHub
2. Deploy it at [share.streamlit.io](https://share.streamlit.io)
3. On the first visit the app downloads the model files itself (~350MB, takes a few minutes)

⚠ Never commit `*.onnx` / `*.bin` files — GitHub rejects files over 100MB (see `.gitignore`).

## 📁 What's in this repo

| File | Purpose |
|---|---|
| `app.py` | The Streamlit app |
| `requirements.txt` | Python dependencies — `streamlit`, `numpy`, `soundfile`, `kokoro-onnx`, `onnxruntime` |
| `packages.txt` | System package — `espeak-ng` (needed for speech on Linux) |
| `.gitignore` | Keeps model files (`*.onnx`, `*.bin`) and generated audio out of git |
| `generated/` | Saved voices (created automatically at runtime) |
| `previews/` | Cached voice previews (created automatically at runtime) |

## 🙏 Credits

- TTS model: [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) via [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx)
