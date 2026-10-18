"""
AnmaVoice AI — Simple TTS page (Streamlit + Kokoro)
====================================================
Run:
    pip install -r requirements.txt
    streamlit run app.py

Model files (put them in the same folder as this file):
    kokoro-v1.0.onnx , voices-v1.0.bin
"""

import io
import json
import os
import re

import numpy as np
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_CHARS = 20000  # txt file or text box — limit for both

# Folder where every generated voice is saved (survives restarts)
GENERATED_DIR = os.path.join(BASE_DIR, "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)

# Pre-generated voice trailers live here — instant playback, no re-processing
PREVIEW_DIR = os.path.join(BASE_DIR, "previews")
os.makedirs(PREVIEW_DIR, exist_ok=True)

# ---- Voice numbering: voice1.wav, voice2.wav, ... (restart-safe) ----
INDEX_PATH = os.path.join(GENERATED_DIR, "index.json")

def _load_index():
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_index(idx):
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)

def _next_voice_number():
    """Agla number = sab se bara maujood number + 1 (kabhi reuse nahi)."""
    nums = [0]
    for f in os.listdir(GENERATED_DIR):
        m = re.match(r"(?i)^voice(\d+)\.wav$", f)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1

@st.cache_resource
def _fresh_start_once():
    """Sirf ek dafa per app-start chalta hai (har rerun par nahi):
    purani voices delete, index reset — numbering voice1 se shuru."""
    for f in os.listdir(GENERATED_DIR):
        if f.lower().endswith(".wav"):
            try:
                os.remove(os.path.join(GENERATED_DIR, f))
            except OSError:
                pass
    _save_index({})
    return True

# Kokoro v1.0's 8 languages: code -> (label, kokoro lang code)
LANGUAGES = {
    "en": ("English (US)", "en-us"),
    "en-gb": ("English (UK)", "en-gb"),
    "es": ("Spanish", "es"),
    "fr": ("French", "fr-fr"),
    "hi": ("Hindi", "hi"),
    "it": ("Italian", "it"),
    "ja": ("Japanese", "ja"),
    "zh": ("Mandarin Chinese", "zh"),
}

# voice id -> (label, kokoro voice, gender)
VOICES = {
    "jenny": ("Jenny", "af_heart", "Female"),
    "aria": ("Aria", "af_bella", "Female"),
    "ana": ("Ana", "af_sarah", "Female"),
    "michelle": ("Michelle", "af_nicole", "Female"),
    "sana": ("Sana", "af_sky", "Female"),
    "fatima": ("Fatima", "af_aoede", "Female"),
    "xiaoxiao": ("Xiaoxiao", "af_kore", "Female"),
    "guy": ("Guy", "am_adam", "Male"),
    "christopher": ("Christopher", "am_michael", "Male"),
    "eric": ("Eric", "am_eric", "Male"),
    "roger": ("Roger", "am_onyx", "Male"),
    "aamir": ("Aamir", "am_fenrir", "Male"),
}

# Preview sample sentence per language (voice trailer)
SAMPLES = {
    "en": "Hello! Welcome to AnmaVoice AI.",
    "en-gb": "Hello! Welcome to AnmaVoice AI.",
    "es": "¡Hola! Bienvenidos a AnmaVoice AI.",
    "fr": "Bonjour ! Bienvenue sur AnmaVoice AI.",
    "hi": "नमस्ते! AnmaVoice AI में आपका स्वागत है।",
    "it": "Ciao! Benvenuti su AnmaVoice AI.",
    "ja": "こんにちは！AnmaVoice AIへようこそ。",
    "zh": "你好！欢迎使用 AnmaVoice AI。",
}

# lang codes for kokoro_onnx
ONNX_LANG = {
    "en": "en-us", "en-gb": "en-gb", "es": "es", "fr": "fr-fr",
    "hi": "hi", "it": "it", "ja": "ja", "zh": "zh",
}
# lang codes for kokoro pip package (KPipeline, single letter)
KPIPE_LANG = {
    "en": "a", "en-gb": "b", "es": "e", "fr": "f",
    "hi": "h", "it": "i", "ja": "j", "zh": "z",
}


@st.cache_resource
def load_onnx():
    """kokoro_onnx — local .onnx files, light and offline."""
    try:
        from kokoro_onnx import Kokoro
        model = Kokoro(
            os.path.join(BASE_DIR, "kokoro-v1.0.onnx"),
            os.path.join(BASE_DIR, "voices-v1.0.bin"),
        )
        return model, None
    except Exception as e:
        return None, str(e)


@st.cache_resource
def get_kpipeline(lang_code):
    """kokoro pip package — downloads from HF on first run."""
    from kokoro import KPipeline
    return KPipeline(lang_code=lang_code)


# Emotion styles (approximate — Kokoro has no native emotion control,
# so each style adjusts tempo + pauses to create the feel).
# code -> (label, speed_multiplier, pause_seconds_between_chunks)
EMOTIONS = {
    "normal": ("Normal 🙂", 1.0, 0.25),
    "deep": ("Deep 🎙", 0.88, 0.45),
    "calm": ("Calm 😌", 0.82, 0.60),
    "happy": ("Happy 😄", 1.12, 0.15),
    "sad": ("Sad 😔", 0.85, 0.50),
    "excited": ("Excited 🤩", 1.22, 0.12),
}


def _split_chunks(text, max_len=400):
    parts = re.split(r"(?<=[.!?।])\s+", text.strip())
    chunks, cur = [], ""
    for p in parts:
        if len(cur) + len(p) + 1 <= max_len:
            cur = (cur + " " + p).strip()
        else:
            if cur:
                chunks.append(cur)
            while len(p) > max_len:
                chunks.append(p[:max_len])
                p = p[max_len:]
            cur = p
    if cur:
        chunks.append(cur)
    return chunks or [text]


def synthesize(text, voice_id, language, speed=1.0, emotion="normal"):
    """Returns (wav_bytes, engine_name, seconds)."""
    import time
    t0 = time.time()
    _, kokoro_voice, _ = VOICES[voice_id]
    emo = EMOTIONS.get(emotion, EMOTIONS["normal"])
    eff_speed = min(2.0, max(0.5, speed * emo[1]))  # slider × emotion
    pause_sec = emo[2]
    chunks = _split_chunks(text)
    audios, sr = [], 24000

    onnx, onnx_err = load_onnx()
    if onnx is not None:
        # Path 1: kokoro_onnx (local files) — fast
        engine = "kokoro_onnx (fast)"
        lang_code = ONNX_LANG.get(language, "en-us")
        for chunk in chunks:
            samples, sr = onnx.create(chunk, voice=kokoro_voice,
                                      speed=eff_speed, lang=lang_code)
            audios.append(np.asarray(samples, dtype=np.float32))
    else:
        # Path 2: kokoro pip package (KPipeline) — torch, slow on CPU
        engine = "kokoro pip (torch, slow)"
        try:
            pipe = get_kpipeline(KPIPE_LANG.get(language, "a"))
        except Exception as e:
            raise RuntimeError(
                "No Kokoro model loaded. Either put 'kokoro-v1.0.onnx' + "
                "'voices-v1.0.bin' in this folder (kokoro_onnx), or run "
                f"'pip install kokoro torch'. Detail: {onnx_err} / {e}"
            )
        for chunk in chunks:
            for _, _, audio in pipe(chunk, voice=kokoro_voice, speed=eff_speed):
                a = audio.detach().cpu().numpy() if hasattr(audio, "detach") \
                    else np.asarray(audio)
                audios.append(np.asarray(a, dtype=np.float32).ravel())

    for i in range(len(audios)):  # emotion pause between chunks
        audios.insert(i * 2 + 1, np.zeros(int(sr * pause_sec), dtype=np.float32))
    audio = np.concatenate(audios) if audios else np.zeros(0, dtype=np.float32)
    peak = np.max(np.abs(audio)) if audio.size else 0
    if peak > 0.99:
        audio = audio * (0.99 / peak)
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue(), engine, time.time() - t0


def get_preview(voice_id, language, emotion="normal"):
    """Voice trailer: pehli dafa banta hai, phir file se instant bajta hai.
    Returns (wav_bytes, was_cached)."""
    fname = f"preview_{voice_id}_{language}_{emotion}.wav"
    fpath = os.path.join(PREVIEW_DIR, fname)
    if os.path.exists(fpath):
        with open(fpath, "rb") as f:
            return f.read(), True
    wav, _, _ = synthesize(SAMPLES.get(language, SAMPLES["en"]),
                           voice_id, language, 1.0, emotion)
    with open(fpath, "wb") as f:
        f.write(wav)
    return wav, False


# ---------------- PAGE ----------------
st.set_page_config(page_title="AnmaVoice AI", page_icon="💜")
_fresh_start_once()  # restart par purani voices saaf, numbering voice1 se

st.title("💜 AnmaVoice AI")
st.caption("v1.7 · voice previews + emotions + numbered library (fresh each restart)")
st.write("Paste your text, choose a voice and a language, then click Generate.")

# 1. Text (type or upload a .txt file)
text = st.text_area("Paste your text here", height=150, max_chars=MAX_CHARS,
                    placeholder="Type or paste your text here…")
uploaded = st.file_uploader("Or upload a .txt file", type=["txt"])
if uploaded is not None:
    text = uploaded.read().decode("utf-8", errors="ignore")[:MAX_CHARS]
    st.info(f"Loaded {len(text)} characters from file.")
st.caption(f"{len(text)} / {MAX_CHARS:,}")

# 2. Voice + Language + Speed + Emotion
c1, c2, c3, c4 = st.columns(4)
voice_labels = {vid: f"{name} — {gender}" for vid, (name, _, gender) in VOICES.items()}
with c2:
    lang = st.selectbox("Language", options=list(LANGUAGES.keys()),
                        format_func=lambda c: LANGUAGES[c][0])
with c4:
    emotion = st.selectbox("Emotion", options=list(EMOTIONS.keys()),
                           format_func=lambda e: EMOTIONS[e][0],
                           help="Approximate style — Kokoro has no built-in "
                                "emotions, so this adjusts tempo & pauses.")
with c1:
    voice_id = st.selectbox("Voice", options=list(voice_labels.keys()),
                            format_func=lambda v: voice_labels[v])
    # Voice trailer: listen first, then pick the voice you like
    if st.button("🔊 Preview voice", use_container_width=True,
                 help="Listen to a short sample of this voice"):
        try:
            with st.spinner("Preview…"):
                pv_wav, cached = get_preview(voice_id, lang, emotion)
            st.audio(pv_wav, format="audio/wav")
            if cached:
                st.caption("⚡ instant preview")
        except Exception as e:
            st.error(f"⚠ {e}")
with c3:
    speed = st.slider("Speed", 0.5, 2.0, 1.0, 0.1, format="%.1fx")

# 3. Generate
if st.button("🎙 Generate", type="primary", use_container_width=True):
    if not text.strip():
        st.error("Give either text or a .txt file first.")
    else:
        try:
            with st.spinner("Audio is processing…"):
                wav, engine, secs = synthesize(text.strip(), voice_id, lang,
                                               speed, emotion)
            st.success("Done ✓")
            st.caption(f"Engine: {engine} · {EMOTIONS[emotion][0]} · Time: {secs:.1f}s")
            # save to disk as voiceN.wav (sequence numbering, restart-safe)
            import datetime
            n = _next_voice_number()
            fname = f"voice{n}.wav"
            with open(os.path.join(GENERATED_DIR, fname), "wb") as f:
                f.write(wav)
            idx = _load_index()
            idx[str(n)] = {
                "file": fname,
                "voice": voice_id,
                "language": lang,
                "emotion": emotion,
                "speed": speed,
                "text": text.strip()[:200],
                "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            _save_index(idx)
            st.caption(f"💾 Saved as Voice {n}")
            st.audio(wav, format="audio/wav")
            st.download_button("⬇ Download Voice", data=wav,
                               file_name=fname, mime="audio/wav",
                               use_container_width=True)
        except Exception as e:
            st.error(f"⚠ {e}")

# ---------------- SAVED VOICES LIBRARY ----------------
st.markdown("---")
st.subheader("📚 Saved Voices")
st.caption("Every generated voice is saved in the 'generated' folder for "
           "this session — restarting the app clears them and numbering "
           "starts again from Voice 1.")

saved = sorted(
    [f for f in os.listdir(GENERATED_DIR)
     if re.match(r"(?i)^voice\d+\.wav$", f)],
    key=lambda f: int(re.match(r"(?i)^voice(\d+)\.wav$", f).group(1)),
)
idx = _load_index()
if not saved:
    st.caption("Nothing saved yet — generate your first voice above.")
for fname in saved:
    n = re.match(r"(?i)^voice(\d+)\.wav$", fname).group(1)
    meta = idx.get(n, {})
    fpath = os.path.join(GENERATED_DIR, fname)
    with st.expander(f"🎧 Voice {n}"):
        if meta.get("voice") not in (None, "?", ""):
            v_label = voice_labels.get(meta.get("voice"), meta.get("voice"))
            l_label = LANGUAGES.get(meta.get("language"),
                                    (meta.get("language"),))[0]
            e_label = EMOTIONS.get(meta.get("emotion"), ("?",))[0]
            st.caption(f"{v_label} · {l_label} · {e_label} · "
                       f"{meta.get('created', '')}")
            if meta.get("text"):
                st.caption(f"📝 {meta['text'][:120]}")
        with open(fpath, "rb") as f:
            data = f.read()
        st.audio(data, format="audio/wav")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("⬇ Download", data=data, file_name=fname,
                               mime="audio/wav", key=f"dl-{fname}",
                               use_container_width=True)
        with d2:
            if st.button("🗑 Delete", key=f"del-{fname}",
                         use_container_width=True):
                os.remove(fpath)
                idx = _load_index()
                idx.pop(n, None)
                _save_index(idx)
                st.rerun()
