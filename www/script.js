const BACKEND_URL = "https://aryap-1243.github.io/medassist-ui//ask";
let lastSummary = "";

async function sendRequest() {
    const input = document.getElementById("input").value.trim();
    const type = document.getElementById("type").value;
    const output = document.getElementById("output");

    if (!input) {
        output.innerHTML = "❗ Please enter your query.";
        return;
    }

    output.innerHTML = "⏳ Processing...";
    lastSummary = "";

    try {
        const response = await fetch(BACKEND_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: input, type: type })
        });

        const data = await response.json();

        output.innerHTML = marked.parse(data.response);

        lastSummary = extractSummary(data.response);

    } catch (err) {
        output.innerHTML = `❌ Error: ${err.message}`;
    }
}

function startVoiceInput() {
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = "en-US";
    recognition.start();

    recognition.onresult = (event) => {
        document.getElementById("input").value = event.results[0][0].transcript;
        sendRequest();
    };
}

function extractSummary(text) {
    const div = document.createElement("div");
    div.innerHTML = marked.parse(text);
    const plainText = div.innerText;

    let summary = "";
    const lines = plainText.split("\n");
    for (let line of lines) {
        if (line.toLowerCase().includes("possible") ||
            line.toLowerCase().includes("medicine") ||
            line.toLowerCase().includes("condition")) {
            summary += line + ". ";
        }
    }

    return summary || "Here's a medical summary. Please check the screen for full details.";
}

function speakSummary() {
    if (!lastSummary) {
        alert("No summary to speak yet.");
        return;
    }

    const lang = document.getElementById("voiceLang").value;
    const utterance = new SpeechSynthesisUtterance(lastSummary);
    const voices = speechSynthesis.getVoices();

    const selectedVoice = voices.find(v => v.lang === lang) || voices.find(v => v.lang.startsWith('en'));
    if (selectedVoice) utterance.voice = selectedVoice;

    utterance.rate = 1;
    speechSynthesis.speak(utterance);
}

function stopSpeaking() {
    speechSynthesis.cancel();
}
