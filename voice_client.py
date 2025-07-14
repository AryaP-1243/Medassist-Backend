import speech_recognition as sr
import requests

API_URL = "http://127.0.0.1:8000/ask"  # your local FastAPI server

def get_voice_input():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    print("🎤 Please speak now...")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    try:
        text = recognizer.recognize_google(audio)
        print(f"📝 You said: {text}")
        return text
    except sr.UnknownValueError:
        print("🤖 Could not understand audio.")
        return None
    except sr.RequestError as e:
        print(f"⚠️ Could not request results; {e}")
        return None

def send_to_assistant(query_type, message):
    payload = {
        "type": query_type,
        "message": message
    }
    response = requests.post(API_URL, json=payload)
    print("\n💡 Assistant says:\n", response.json().get("response", "No response"))

if __name__ == "__main__":
    print("Welcome to the voice-driven healthcare assistant.")
    query_type = input("Type (symptom or medicine): ").strip().lower()

    voice_text = get_voice_input()
    if voice_text:
        send_to_assistant(query_type, voice_text)
