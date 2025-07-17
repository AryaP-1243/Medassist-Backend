const BACKEND_URL = `https://medassist-backend-jp57.onrender.com/ask`;

async function sendRequest() {
    const input = document.getElementById("input").value.trim();
    const type = document.getElementById("type").value;
    const output = document.getElementById("output");

    if (!input) {
        output.innerHTML = "❗ Please enter your query.";
        return;
    }

    output.innerHTML = "⏳ Processing...";

    try {
        const response = await fetch(BACKEND_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: input, type: type })
        });

        const data = await response.json();
        output.innerHTML = marked.parse(data.response);

    } catch (err) {
        output.innerHTML = `❌ Error: ${err.message}`;
    }
}
