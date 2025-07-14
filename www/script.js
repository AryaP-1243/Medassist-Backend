const BACKEND_URL = `http://${window.location.hostname}:8000/ask`;

async function sendRequest() {
    const input = document.getElementById("input").value.trim();
    const output = document.getElementById("output");
    const type = document.getElementById("type").value;

    if (!input) {
        output.innerHTML = "❗ Please enter some text.";
        return;
    }

    output.innerHTML = "⏳ Processing...";

    try {
        const response = await fetch(BACKEND_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: input, type: type })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail);
        }

        const data = await response.json();
        output.innerHTML = data.response;

    } catch (err) {
        output.className = "error";
        output.innerHTML = `❌ Error: ${err.message}`;
    }
}

function startVoiceInput() {
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = "en-US";
    recognition.start();

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        document.getElementById("input").value = transcript;
        sendRequest(); // Uses selected type
    };

    recognition.onerror = (event) => {
        document.getElementById("output").innerHTML = `❌ Voice error: ${event.error}`;
    };
}
