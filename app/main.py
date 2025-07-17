from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
from datetime import datetime
from groq import Groq

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class UserInput(BaseModel):
    message: str
    type: str
    email: str

DATA_FILE = "users_data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def load_user_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_user_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.post("/ask")
async def ask(input: UserInput):
    try:
        data = load_user_data()

        # Store user history
        if input.email not in data:
            data[input.email] = {"history": [], "food": []}

        user_record = data[input.email]

        log_entry = {
            "message": input.message,
            "type": input.type,
            "timestamp": datetime.now().isoformat()
        }
        user_record["history"].append(log_entry)

        save_user_data(data)

        # Build prompt dynamically
        system_message = "You are MedAssist, a professional healthcare AI assistant. Use markdown formatting."

        if input.type == "symptom":
            prompt = f"""
User said: {input.message}

Provide:

## 🩺 Symptom Info

### Possible Causes:
- List 3 possible causes for the symptom.

### Home Remedies:
- List 2 simple home remedies.

### Medicines:
- List 2 over-the-counter medicines for this symptom.

### Health Score Impact:
- Based on previous food: {user_record['food']}
- Explain if this symptom could be linked to recent food behavior.

---
**Note:** Always consult a healthcare provider.
"""

        elif input.type == "medicine":
            med_name = input.message.lower().replace("tell me about", "").replace("what is", "").strip()
            prompt = f"""
Provide detailed information about **{med_name}** in markdown:

## 💊 Medicine: {med_name.title()}

### What It Does:
- Primary use.

### How It Works:
- Mechanism.

### Side Effects:
- List 3 side effects.

### Precautions:
- List precautions.

### Where to Buy:
[Buy {med_name.title()} on 1mg](https://www.1mg.com/search/all?name={med_name.replace(" ", "%20")})

---
**Note:** This is general information, not medical advice.
"""
        else:
            raise HTTPException(status_code=400, detail="Invalid type")

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=800
        )

        return {"response": response.choices[0].message.content.strip(), "history": user_record["history"]}

    except Exception as e:
        return {"detail": f"Internal server error: {str(e)}"}
