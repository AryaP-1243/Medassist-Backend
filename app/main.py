from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import os

app = FastAPI()

# CORS setup
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

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ask")
async def ask_assistant(input: UserInput):
    try:
        # Use dynamic prompt with controlled randomness
        prompt = ""
        if input.type == "symptom":
            prompt = f"""
You are HEBO, a strictly medical assistant AI.

Patient says: "{input.message}"

Respond with:

🩺 **Possible Conditions**  
- List 3 to 4 likely conditions.

💊 **Medicine Suggestions**  
- Recommend **safe over-the-counter medicines** for the symptoms.
- Provide specific medicines (not just paracetamol), include variations if relevant.

🛒 **Where to Buy**  
- Give direct links using the medicine name:  
[1mg](https://www.1mg.com/search/all?name=<MEDICINE>)  
[Netmeds](https://www.netmeds.com/catalogsearch/result?q=<MEDICINE>)  
[Apollo Pharmacy](https://www.apollopharmacy.in/search/<MEDICINE>)

❗ **Disclaimer**  
This is general advice. Consult a healthcare professional for serious cases.
            """
        elif input.type == "medicine":
            prompt = f"""
You are HEBO, a medical assistant. The user asked about "{input.message}".

Provide:

💊 **What It Does**  
- Explain what the medicine is for.

⚙️ **How It Works**  
- Mechanism of action.

⚠️ **Side Effects & Precautions**  
- List the most common side effects.

🛒 **Where to Buy**  
Give direct links:  
[1mg](https://www.1mg.com/search/all?name={input.message})  
[Netmeds](https://www.netmeds.com/catalogsearch/result?q={input.message})  
[Apollo Pharmacy](https://www.apollopharmacy.in/search/{input.message})

❗ **Disclaimer**  
This is for general information only.
            """
        else:
            raise HTTPException(status_code=400, detail="Invalid type")

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            temperature=0,  # Deterministic output
            messages=[
                {"role": "system", "content": "Only reply to medical-related queries. Use markdown."},
                {"role": "user", "content": prompt}
            ]
        )

        return {"response": response.choices[0].message.content.strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
