from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import os
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

class UserInput(BaseModel):
    message: str
    type: str

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise Exception("Set GROQ_API_KEY in environment variables.")

client = Groq(api_key=api_key)

def add_buy_links_to_medicines(text):
    """
    Finds medicine names in the text (in markdown lists or tables) and appends 1mg buy links dynamically.
    """
    pattern = r"\*\*(.*?)\*\*"  # Match bolded medicine names in ** **

    def replacer(match):
        med = match.group(1)
        link = f"[Buy on 1mg](https://www.1mg.com/search/all?name={med.replace(' ', '%20')})"
        return f"**{med}** ({link})"

    return re.sub(pattern, replacer, text)

@app.post("/ask")
async def ask(input: UserInput):
    try:
        system_message = (
            "You are MedAssist, a professional healthcare AI. "
            "Respond in markdown. Use natural, human-like explanations, and suggest relevant medicines only. "
            "Include home remedies if symptom-related. Do not suggest unnecessary medicines. Do not repeat the user's prompt directly."
        )

        if input.type == "symptom":
            prompt = f"""
Patient says: "{input.message}"

Provide the following in markdown:

## 🩺 Symptom Overview

### Possible Causes
- List the likely causes of this problem.

### Home Remedies
- Provide 3-4 home remedies if applicable.

### Relevant Medicines
- Suggest medicines only if required and only those relevant to this issue.
- Format each medicine like: **Medicine Name** - Purpose

### When to See a Doctor
- List red flags that require medical attention.

### Disclaimer
This is general information, not medical advice. Always consult a doctor.
"""

        elif input.type == "medicine":
            prompt = f"""
Provide details about "{input.message}" in markdown:

## 💊 Medicine Guide

### Overview
- What it is used for.

### How it Works
- Basic explanation.

### Side Effects
- List 3-5 common side effects.

### Precautions
- Who should avoid it.

### Disclaimer
This is informational, not a medical prescription.
"""

        else:
            raise HTTPException(status_code=400, detail="Type must be 'symptom' or 'medicine'.")

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1024
        )

        raw_output = response.choices[0].message.content.strip()

        # Dynamically add 1mg links to **Medicine Names**
        final_output = add_buy_links_to_medicines(raw_output)

        return {"response": final_output}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")
