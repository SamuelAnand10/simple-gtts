"""
Streamlit app: gTTS + Autoplay + STT

How to run:
1) pip install streamlit gTTS SpeechRecognition pydub streamlit-audio-recorder
2) Install ffmpeg on your system (pydub needs it). On Ubuntu: sudo apt install ffmpeg
3) Run: streamlit run streamlit_gtts_with_stt.py

Notes:
- This app uses `streamlit-audio-recorder` to record from the browser. If that component isn't available, use the "Upload audio file" fallback.
- Speech-to-text uses the SpeechRecognition package with Google's free recognizer (requires internet). Replace with Whisper/local model if you prefer.
"""

import streamlit as st
from gtts import gTTS
import tempfile
import base64
import os
import io

st.set_page_config(page_title="gTTS + STT", layout="centered")
st.title("gTTS — Autoplay Mode + STT (Speech-to-Text)")

# --- UI: TTS ---
st.header("Text-to-Speech (TTS)")
lang = st.selectbox("Language (gTTS codes)", ["en", "en-uk", "en-us", "de", "fr"], index=0)
# use session_state-backed text area so we can programmatically set its value from the STT section
if 'tts_text' not in st.session_state:
    st.session_state['tts_text'] = "Hi there, I'm your personal assistant."
text = st.text_area("Text to speak", value=st.session_state['tts_text'], key="tts_text")

# helper to autoplay mp3 bytes
def autoplay_audio_bytes(audio_bytes):
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
        tts = gTTS(text=text, lang=lang.split('-')[0])
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        try:
            tts.save(tmp.name)
            with open(tmp.name, "rb") as f:
                audio_bytes = f.read()
            autoplay_audio_bytes(audio_bytes)
            st.success("Done! Your audio is playing automatically.")
        finally:
            try:
                tmp.close()
                os.unlink(tmp.name)
            except Exception:
                pass

st.markdown("---")

# --- STT section ---
st.header("Speech-to-Text (STT)")
st.write("You can record from your browser (click Record), or upload an audio file. The app will transcribe using Google Speech Recognition via the SpeechRecognition Python library.")

use_recorder = False
try:
    # try to lazy-import the audio recorder component
    from streamlit_audio_recorder import audio_recorder
    use_recorder = True
except Exception:
    use_recorder = False

import speech_recognition as sr
from pydub import AudioSegment

recog = sr.Recognizer()

transcript = None

if use_recorder:
    st.subheader("Record from your browser")
    st.write("Click the Record button below. When you stop, the recorded audio will be sent to the app for transcription.")
    audio_bytes = audio_recorder()
    if audio_bytes:
        st.success("Audio recorded — processing...")
        # write bytes to temporary file
        tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
        try:
            tmp_in.write(audio_bytes)
            tmp_in.flush()
            tmp_in.close()

            # convert to WAV using pydub (needs ffmpeg)
            wav_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            try:
                AudioSegment.from_file(tmp_in.name).export(wav_tmp.name, format="wav")
                wav_tmp.close()

                with sr.AudioFile(wav_tmp.name) as source:
                    audio_data = recog.record(source)
                try:
                    transcript = recog.recognize_google(audio_data)
                except sr.UnknownValueError:
                    transcript = "(Could not understand audio)"
                except sr.RequestError as e:
                    transcript = f"(Could not request results; {e})"
            finally:
                try:
                    os.unlink(wav_tmp.name)
                except Exception:
                    pass
        finally:
            try:
                os.unlink(tmp_in.name)
            except Exception:
                pass

# Fallback: upload audio file
st.subheader("Or upload an audio file")
uploaded = st.file_uploader("Upload audio (wav, mp3, m4a, webm)", type=["wav", "mp3", "m4a", "webm"])
if uploaded is not None:
    st.write("File uploaded — processing...")
    # save and convert to WAV
    in_bytes = uploaded.read()
    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1])
    try:
        tmp_in.write(in_bytes)
        tmp_in.flush()
        tmp_in.close()

        wav_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        try:
            AudioSegment.from_file(tmp_in.name).export(wav_tmp.name, format="wav")
            wav_tmp.close()

            with sr.AudioFile(wav_tmp.name) as source:
                audio_data = recog.record(source)
            try:
                transcript = recog.recognize_google(audio_data)
            except sr.UnknownValueError:
                transcript = "(Could not understand audio)"
            except sr.RequestError as e:
                transcript = f"(Could not request results; {e})"
        finally:
            try:
                os.unlink(wav_tmp.name)
            except Exception:
                pass
    finally:
        try:
            os.unlink(tmp_in.name)
        except Exception:
            pass

if transcript:
    st.subheader("Transcription result")
    st.write(transcript)
    # directly put the transcript into the TTS text area by setting session_state
    if st.button("Put transcription into TTS text area"):
        st.session_state['tts_text'] = transcript
        st.success("Transcription placed into the TTS text area.")
        # rerun so the text area updates immediately with the new value
        st.experimental_rerun()

# If transcription was saved to session_state, show how to use it
if 'tts_from_stt' in st.session_state:
    st.info("Transcription saved to session state as 'tts_from_stt'. You can copy it into the TTS text box above.")

st.markdown("---")
st.caption("Dependencies: streamlit, gTTS, SpeechRecognition, pydub, streamlit-audio-recorder (optional). ffmpeg required for pydub conversion.")

