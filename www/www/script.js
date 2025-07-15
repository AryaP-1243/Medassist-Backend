const BACKEND_URL = "https://medassist.loca.lt/ask";
document.getElementById("askBtn").onclick = async () => {
    const message = document.getElementById("message").value;
    if (!message) return alert("Please enter a message");

    const type = document.getElementById("type").value;

const payload = {
    message: message,
    type: type
};
    const res = await fetch(backendURL, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });

    const data = await res.json();
    document.getElementById("response").innerText = data.response || "❌ No response.";
};

document.getElementById("voiceBtn").onclick = () => {
    if (!('webkitSpeechRecognition' in window)) {
        alert("Your browser does not support voice input.");
        return;
    }

    const recognition = new webkitSpeechRecognition();
    recognition.lang = 'en-US';
    recognition.start();

    recognition.onresult = (event) => {
        document.getElementById("message").value = event.results[0][0].transcript;
    };
};
