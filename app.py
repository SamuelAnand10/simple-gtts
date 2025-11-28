import streamlit as st
from gtts import gTTS
import tempfile
import base64
import os

st.set_page_config(page_title="gTTS Autoplay", layout="centered")
st.title("gTTS — Autoplay Mode")

# UI
lang = st.selectbox("Language", ["en", "en-uk", "en-us"])
text = st.text_area("Text", "Hi there, I'm your personal assistant.")

def autoplay_audio(mp3_path):
    with open(mp3_path, "rb") as f:
        audio_bytes = f.read()
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(
        f"""
        <audio autoplay controls>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """,
        unsafe_allow_html=True
    )

if st.button("Speak", key="speak_btn"):
    if not text.strip():
        st.warning("Please enter some text.")
    else:
        tts = gTTS(text=text, lang="en")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp.name)

        autoplay_audio(tmp.name)
        st.success("Done! Your audio is playing automatically.")


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
