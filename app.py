"""
Minimal Streamlit app:
- HTML/JS recorder (MediaRecorder) embedded in page.
- User downloads recorded file, then uploads it using the uploader.
- App converts uploaded file (webm/mp3/m4a/ogg/wav) to WAV via pydub,
  transcribes with SpeechRecognition (Google), and automatically puts the
  transcript into the TTS text area (session_state-backed).
- Click Speak (TTS) to hear it.

Requirements (requirements.txt):
streamlit>=1.24.0
gTTS>=2.3.0
pydub>=0.25.1
SpeechRecognition>=3.8.1
"""

import streamlit as st
from gtts import gTTS
import base64, tempfile, os, io
from pydub import AudioSegment
import speech_recognition as sr

st.set_page_config(page_title="Recorder → STT → TTS", layout="centered")
st.title("Recorder → STT → TTS (HTML recorder only)")

# -------------------------
# TTS UI (session_state-backed)
# -------------------------
if "tts_text" not in st.session_state:
    st.session_state["tts_text"] = "Hi there, I'm your personal assistant."

lang = st.selectbox("Language (gTTS codes)", ["en", "en-uk", "en-us", "de", "fr"], index=0)
# session-state-backed text area so we can programmatically set it
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
    if not st.session_state["tts_text"].strip():
        st.warning("Text area is empty.")
    else:
        gtts_lang = lang.split("-")[0]
        tts = gTTS(text=st.session_state["tts_text"], lang=gtts_lang)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        try:
            tts.save(tmp.name)
            with open(tmp.name, "rb") as f:
                autoplay_audio_bytes(f.read())
            st.success("Playing TTS.")
        finally:
            try:
                tmp.close(); os.unlink(tmp.name)
            except Exception:
                pass

st.markdown("---")

# -------------------------
# HTML recorder (only) + uploader
# -------------------------
st.header("Record in your browser (HTML recorder)")

st.write(
    "1) Click **Start Recording**, speak, then **Stop**.  "
    "2) Click **Download** to save (default filename: recording.webm).  "
    "3) Immediately upload the saved file below; the app will transcribe it and place the text into the TTS box."
)

RECORDER_HTML = r"""
<style>
.rec-btn { padding:8px 12px; margin:6px; font-size:14px; }
#controls { margin-top: 8px; }
#audioPlayer { margin-top: 10px; width: 100%; }
</style>

<div>
  <button id="recordBtn" class="rec-btn">Start Recording</button>
  <button id="stopBtn" class="rec-btn" disabled>Stop</button>
  <button id="playBtn" class="rec-btn" disabled>Play</button>
  <a id="downloadLink" style="display:none; margin-left: 10px;">Download</a>
  <p id="status" style="font-size:13px; color:#333;"></p>
  <audio id="audioPlayer" controls></audio>
</div>

<script>
let mediaRecorder;
let audioChunks = [];
const recordBtn = document.getElementById('recordBtn');
const stopBtn = document.getElementById('stopBtn');
const playBtn = document.getElementById('playBtn');
const downloadLink = document.getElementById('downloadLink');
const status = document.getElementById('status');
const audioPlayer = document.getElementById('audioPlayer');

recordBtn.onclick = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstart = () => {
      status.textContent = 'Recording...';
      recordBtn.disabled = true;
      stopBtn.disabled = false;
      playBtn.disabled = true;
      downloadLink.style.display = 'none';
    };
    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: 'audio/webm' });
      const url = URL.createObjectURL(blob);
      audioPlayer.src = url;
      playBtn.disabled = false;
      downloadLink.href = url;
      downloadLink.download = 'recording.webm';
      downloadLink.style.display = 'inline';
      downloadLink.textContent = 'Download (save & upload)';
      status.textContent = 'Recording stopped. Click Download to save the file, then upload it below.';
    };
    mediaRecorder.start();
  } catch (err) {
    status.textContent = 'Microphone access denied or not available. Refresh and allow microphone, then try again.';
  }
};

stopBtn.onclick = () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  recordBtn.disabled = false;
  stopBtn.disabled = true;
};

playBtn.onclick = () => {
  if (audioPlayer.src) {
    audioPlayer.play();
  }
};
</script>
"""

st.components.v1.html(RECORDER_HTML, height=220)

st.markdown("---")
st.header("Upload recorded file (required)")

uploaded = st.file_uploader("Upload the file you downloaded from the recorder (recording.webm)", type=["wav", "mp3", "m4a", "webm", "ogg"])
if uploaded is not None:
    st.info("File uploaded — processing now...")
    try:
        in_bytes = uploaded.read()
        # convert/normalize with pydub (ffmpeg required)
        seg = AudioSegment.from_file(io.BytesIO(in_bytes))
        bio = io.BytesIO()
        seg.export(bio, format="wav")
        wav_bytes = bio.getvalue()

        # optional preview
        st.audio(wav_bytes, format="audio/wav")

        # transcribe
        r = sr.Recognizer()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        try:
            tmp.write(wav_bytes)
            tmp.flush()
            tmp.close()
            with sr.AudioFile(tmp.name) as source:
                audio_data = r.record(source)
            try:
                transcript = r.recognize_google(audio_data)
            except sr.UnknownValueError:
                transcript = "(Could not understand audio)"
            except sr.RequestError as e:
                transcript = f"(Could not request results; {e})"
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

        # place transcript directly into TTS text area and rerun so text area updates
        st.session_state["tts_text"] = transcript
        st.success("Transcription placed into TTS text area.")
        st.experimental_rerun()

    except Exception as e:
        st.error(f"Failed to process uploaded audio: {e}")

st.markdown("---")
st.caption("Dependencies: streamlit, gTTS, pydub, SpeechRecognition. System dependency: ffmpeg (for pydub).")

