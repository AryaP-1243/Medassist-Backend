from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

class UserInput(BaseModel):
    message: str
    type: str  # "symptom" or "medicine"
    email: str
    food_history: str = ""

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise Exception("Set GROQ_API_KEY environment variable.")

client = Groq(api_key=api_key)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ask")
async def ask(input: UserInput):
    try:
        system_message = "You are MedAssist, an AI medical assistant with a friendly doctor tone. Always provide structured markdown output."

        # Basic health score (simple calculation based on food keywords)
        healthy_foods = ["salad", "fruits", "vegetables", "nuts", "whole grains", "water"]
        junk_foods = ["pizza", "burger", "fries", "soft drink", "ice cream", "alcohol"]

        score = 70
        for item in healthy_foods:
            if item in input.food_history.lower():
                score += 5
        for item in junk_foods:
            if item in input.food_history.lower():
                score -= 5
        score = min(max(score, 0), 100)

        base_prompt = f"""
User Email: {input.email}
Recent Food History: {input.food_history}

Health Score: {score}/100

"""

        if input.type == "medicine":
            med = input.message.strip()
            prompt = base_prompt + f"""
## 💊 Medicine: {med}

### 🧠 What It Does
Explain {med} in simple terms: its use and benefits.

### ⚙️ How It Works
Explain how {med} works in the human body.

### ⚠️ Side Effects & Precautions
List 3 side effects and general precautions.

### 🛒 Where to Buy
[Buy {med} on 1mg](https://www.1mg.com/search/all?name={med.replace(" ", "%20")})

### ❗ Disclaimer
This is not medical advice. Always consult a doctor.
"""
        elif input.type == "symptom":
            symptom = input.message.strip()
            prompt = base_prompt + f"""
## 🩺 Symptom: {symptom}

### ✅ Possible Causes
List 3 possible causes for {symptom}.

### 🏠 Home Remedies
Suggest 2-3 safe home remedies.

### 💊 Medicines
Suggest over-the-counter medicines, if any.

### 📊 Health Score Impact
Based on recent food history, inform the user whether their diet could have contributed to this symptom.

### 🛒 Where to Buy
For any suggested medicines, [search on 1mg](https://www.1mg.com/search/all?name={symptom.replace(" ", "%20")})

### ❗ Disclaimer
This is general advice, not a medical prescription.
"""
        else:
            raise HTTPException(status_code=400, detail="Type must be 'medicine' or 'symptom'.")

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1024
        )

        return {"response": response.choices[0].message.content.strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
