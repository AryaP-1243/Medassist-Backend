from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import os

from app.prompts import symptom_checker_prompt, medicine_explainer_prompt
from app.formatter import format_symptom_response, format_medicine_response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserInput(BaseModel):
    message: str
    type: str  # "symptom" or "medicine"

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise Exception("Set GROQ_API_KEY in environment.")

client = Groq(api_key=api_key)

@app.post("/ask")
async def ask_assistant(input: UserInput):
    try:
        if input.type == "symptom":
            prompt = symptom_checker_prompt.format(message=input.message)
        elif input.type == "medicine":
            prompt = medicine_explainer_prompt.format(message=input.message)
        else:
            raise HTTPException(status_code=400, detail="Invalid type. Use 'symptom' or 'medicine'.")

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": """
                You are HEBO, a strictly medical assistant AI.

                Rules:
                1️⃣ Only answer healthcare-related questions: symptoms, diseases, medicines, first aid.
                2️⃣ If the user asks about symptoms, provide:
                   - Possible conditions 🩺
                   - Simple explanation 💡
                   - Over-the-counter medicine suggestions 💊 (only if safe and general, like paracetamol or ibuprofen, no prescriptions)
                   - When to see a doctor ❗
                3️⃣ If the user asks about a medicine, explain:
                   - What it is 💊
                   - How it works ⚙️
                   - Side effects and precautions ⚠️
                   - When to consult a doctor 🩺
                4️⃣ For unrelated queries, strictly respond:
                   "🚫 I can only assist with medical symptoms or medicines."

                Format:
                - Use bullet points
                - Add emojis
                - Use markdown for neat formatting
                - Keep the tone friendly but professional
                """},
                {"role": "user", "content": prompt}
            ]
        )

        raw_reply = response.choices[0].message.content.strip()

        if input.type == "symptom":
            formatted = format_symptom_response(raw_reply)
        else:
            formatted = format_medicine_response(raw_reply)

        return {"response": formatted}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
