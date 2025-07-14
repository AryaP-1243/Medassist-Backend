async function askAssistant() {
  const message = document.getElementById("user-input").value;
  const type = document.getElementById("query-type").value;
  const responseDiv = document.getElementById("response");

  responseDiv.innerHTML = "🧠 Thinking...";

  try {
    const res = await fetch("http://127.0.0.1:8000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, message }),
    });

    const data = await res.json();
    const markdown = data.response || "No response.";
    responseDiv.innerHTML = marked.parse(markdown);
  } catch (error) {
    responseDiv.innerHTML = "❌ Failed to get a response.";
    console.error(error);
  }
}
