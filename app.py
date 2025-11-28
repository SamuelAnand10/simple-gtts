"""
streamlit_gtts_stt_webrtc.py

- Uses streamlit-webrtc to capture microphone audio from the browser.
- Collects a short audio clip when you click Record (non-background blocking, short duration).
- Converts frames to WAV and transcribes using SpeechRecognition (Google Web API).
- Puts transcript directly into the TTS text area (session_state-backed).
- Has file upload fallback.

Notes:
- streamlit-webrtc uses WebRTC; no extra client library required beyond the package.
- You need ffmpeg available for pydub conversions (packages.txt on Streamlit Cloud).
"""

import streamlit as st
from gtts import gTTS
import tempfile, os, io, base64, time
import numpy as np

# webrtc
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

# STT
import speech_recognition as sr
from pydub import AudioSegment
import soundfile as sf  # to write WAV from numpy arrays

st.set_page_config(page_title="gTTS + STT (webrtc)", layout="centered")
st.title("gTTS — Autoplay Mode + STT (streamlit-webrtc)")

# -------------------------
# TTS UI (session_state-backed)
# -------------------------
if "tts_text" not in st.session_state:
    st.session_state["tts_text"] = "Hi there, I'm your personal assistant."

lang = st.selectbox("Language (gTTS codes)", ["en", "en-uk", "en-us", "de", "fr"], index=0)
text = st.text_area("Text to speak", value=st.session_state["tts_text"], key="tts_text")

def autoplay_audio_bytes(audio_bytes: bytes):
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(
        f"""
        <audio autoplay controls>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """,
        unsafe_allow_html=True,
    )

if st.button("Speak (TTS)"):
    if not text.strip():
        st.warning("Please enter some text.")
    else:
        gtts_lang = lang.split("-")[0]
        tts = gTTS(text=text, lang=gtts_lang)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        try:
            tts.save(tmp.name)
            with open(tmp.name, "rb") as f:
                autoplay_audio_bytes(f.read())
            st.success("Done! Audio playing.")
        finally:
            try:
                tmp.close(); os.unlink(tmp.name)
            except Exception:
                pass

st.markdown("---")

# -------------------------
# STT UI using streamlit-webrtc
# -------------------------
st.header("Speech-to-Text (STT) — browser recording (webrtc) or upload")
st.write("Click **Start WebRTC** then press **Record for 5s** to capture audio. The app will transcribe and you can push the transcript to the TTS box.")

# Recognizer
recog = sr.Recognizer()

# WebRTC configuration (public STUN servers). Keep default if you don't need ICE servers.
RTC_CONFIGURATION = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

webrtc_ctx = webrtc_streamer(
    key="stt",
    mode=WebRtcMode.SENDONLY,  # only sending audio from browser to server
    rtc_configuration=RTC_CONFIGURATION,
    media_stream_constraints={"audio": True, "video": False},
    async_processing=False,
    # suppress the built-in player UI (optional)
    # video_html_attrs={"style": "display:none;"},
)

def frames_to_wav_bytes(frames, sample_rate=48000):
    """
    Convert list of av.AudioFrame-like objects (frames) to WAV bytes.
    streamlit-webrtc gives us frames via webrtc_ctx.audio_receiver.get_frames()
    Each frame has .to_ndarray() -> numpy array shape (n_channels, n_samples) or (n_samples,)
    We'll concatenate them and write a WAV via soundfile.
    """
    # collect ndarray chunks and flatten to mono
    chunks = []
    sr_rate = None
    for frame in frames:
        try:
            arr = frame.to_ndarray()
        except Exception:
            # some builds return ndarray directly as frame
            arr = np.asarray(frame)
        # arr can be (channels, samples) or (samples,)
        if arr.ndim == 2:
            # convert to mono by averaging channels
            arr = np.mean(arr, axis=0)
        chunks.append(arr)
        # sample rate (frames usually have .sample_rate)
        if sr_rate is None:
            try:
                sr_rate = frame.sample_rate
            except Exception:
                sr_rate = sample_rate
    if not chunks:
        return None
    audio_np = np.concatenate(chunks).astype(np.float32)
    if sr_rate is None:
        sr_rate = sample_rate
    # write to bytes WAV
    bio = io.BytesIO()
    sf.write(bio, audio_np, sr_rate, format="WAV")
    return bio.getvalue()

def transcribe_wav_bytes(wav_bytes: bytes) -> str:
    # Use pydub to open bytes reliably (optional), but SpeechRecognition can read a temp wav
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    try:
        tmp.write(wav_bytes)
        tmp.flush()
        tmp.close()
        with sr.AudioFile(tmp.name) as source:
            audio_data = recog.record(source)
        try:
            return recog.recognize_google(audio_data)
        except sr.UnknownValueError:
            return "(Could not understand audio)"
        except sr.RequestError as e:
            return f"(Could not request results; {e})"
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

# Record control: user clicks a button to capture N seconds of audio from the webrtc audio receiver
record_seconds = st.number_input("Record duration (seconds)", min_value=1, max_value=30, value=5, step=1)

if st.button("Record for seconds (using webrtc)"):
    if webrtc_ctx.state.playing:
        st.info(f"Recording {record_seconds}s... please speak into your microphone")
        # Collect frames for record_seconds
        frames = []
        start = time.time()
        # Poll frames until time elapsed
        while time.time() - start < float(record_seconds):
            # get_frames(blocking=False) returns list; blocking mode can wait
            try:
                new_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1.0)
            except Exception:
                new_frames = []
            if new_frames:
                frames.extend(new_frames)
        if not frames:
            st.error("No audio frames received. Make sure your browser allowed microphone access and try again.")
        else:
            st.success(f"Captured {len(frames)} frames — converting...")
            wav_bytes = frames_to_wav_bytes(frames)
            if wav_bytes is None:
                st.error("Failed to convert frames to audio.")
            else:
                # show preview
                st.audio(wav_bytes, format="audio/wav")
                st.write("Transcribing...")
                transcript = transcribe_wav_bytes(wav_bytes)
                st.subheader("Transcription result")
                st.write(transcript)
                if st.button("Put transcription into TTS text area"):
                    st.session_state["tts_text"] = transcript
                    st.success("Transcription placed into TTS text area.")
                    st.experimental_rerun()
    else:
        st.error("Start the WebRTC streamer first by clicking 'Start' in the top-right of the WebRTC box.")

# ---------- Fallback: upload audio file ----------
st.markdown("---")
st.subheader("Or upload an audio file (wav, mp3, m4a, webm)")
uploaded = st.file_uploader("Upload audio", type=["wav", "mp3", "m4a", "webm"])
if uploaded is not None:
    st.write("Processing upload...")
    bytes_in = uploaded.read()
    # Convert to wav bytes with pydub to normalize
    try:
        seg = AudioSegment.from_file(io.BytesIO(bytes_in))
        bio = io.BytesIO()
        seg.export(bio, format="wav")
        wavbytes = bio.getvalue()
        st.audio(wavbytes)
        text_out = transcribe_wav_bytes(wavbytes)
        st.subheader("Transcription result")
        st.write(text_out)
        if st.button("Put transcription into TTS text area (uploaded)"):
            st.session_state["tts_text"] = text_out
            st.success("Transcription placed into TTS text area.")
            st.experimental_rerun()
    except Exception as e:
        st.error(f"Failed to convert/upload audio: {e}")

st.caption("Dependencies: streamlit, streamlit-webrtc, soundfile, numpy, SpeechRecognition, pydub, gTTS. System dependency: ffmpeg.")
