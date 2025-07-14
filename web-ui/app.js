const chatBox = document.getElementById("chat-box");
const textInput = document.getElementById("text-input");
const sendBtn = document.getElementById("send-btn");
const voiceBtn = document.getElementById("voice-btn");

// Your FastAPI backend
const API_URL = "http://127.0.0.1:8000/ask";

function addMessage(text, sender) {
  const msg = document.createElement("div");
  msg.classList.add("message", sender);
  msg.textContent = text;
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage(message, type = "symptom") {
  addMessage(message, "user");

  const res = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, message })
  });

  const data = await res.json();
  addMessage(data.response || "No response", "assistant");
}

sendBtn.onclick = () => {
  const text = textInput.value;
  if (!text) return;
  sendMessage(text);
  textInput.value = "";
};

voiceBtn.onclick = () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Speech recognition not supported");
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.start();

  recognition.onresult = (event) => {
    const voiceText = event.results[0][0].transcript;
    textInput.value = voiceText;
    sendMessage(voiceText);
  };

  recognition.onerror = (e) => {
    console.error("Speech Error:", e);
  };
};
