import whisper
import sounddevice as sd
import numpy as np
import requests
import scipy.io.wavfile

API_URL = "http://127.0.0.1:8000/ask"
MODEL = whisper.load_model("base")  # You can use "tiny", "base", "small", etc.

DURATION = 5  # seconds
SAMPLE_RATE = 16000

def record_audio(duration, sample_rate):
    print("🎤 Recording...")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    return audio

def save_wav(audio, sample_rate, filename="temp.wav"):
    scipy.io.wavfile.write(filename, sample_rate, audio)

def transcribe(filename):
    result = MODEL.transcribe(filename)
    print(f"📝 Transcribed Text: {result['text']}")
    return result["text"]

def send_to_api(query_type, message):
    response = requests.post(API_URL, json={"type": query_type, "message": message})
    print("\n💬 Assistant says:\n", response.json().get("response", "No response."))

if __name__ == "__main__":
    query_type = input("Type (symptom or medicine): ").strip().lower()
    audio = record_audio(DURATION, SAMPLE_RATE)
    save_wav(audio, SAMPLE_RATE)
    text = transcribe("temp.wav")
    if text:
        send_to_api(query_type, text)
