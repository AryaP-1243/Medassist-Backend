from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import os, json, random, time
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

class UserInput(BaseModel):
    message: str
    type: str
    email: str = None
    phone: str = None
    food_history: str = None

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DATA_FILE = "users_data.json"
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def save_user_data(email_or_phone, query, query_type, food=None):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    if email_or_phone not in data:
        data[email_or_phone] = {"history": [], "food": food}

    data[email_or_phone]["history"].append({
        "message": query,
        "type": query_type,
        "timestamp": datetime.now().isoformat()
    })

    if food:
        data[email_or_phone]["food"] = food

    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def calculate_health_score(food_history):
    bad_food = ["burger", "pizza", "mutton", "oily", "fried", "dessert", "cola", "alcohol"]
    good_food = ["salad", "fruits", "vegetable", "dal", "chapati", "protein", "green", "broccoli"]

    score = 70
    if any(x in food_history.lower() for x in bad_food):
        score -= 20
    if any(x in food_history.lower() for x in good_food):
        score += 20
    return min(max(score, 10), 100)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ask")
async def ask(input: UserInput):
    try:
        user_id = input.email or input.phone
        if not user_id:
            raise HTTPException(status_code=400, detail="Email or phone required.")

        save_user_data(user_id, input.message, input.type, input.food_history)

        health_score = None
        if input.food_history:
            health_score = calculate_health_score(input.food_history)

        base_system = "You are MedAssist, a professional AI doctor assistant. Respond in markdown with helpful, warm, non-repetitive, real-world answers. Give direct medicine suggestions with 1mg links."

        if input.type == "symptom":
            prompt = f"""
User: {input.message}

Respond as:

## 🩺 Symptom Assessment

### Possible Causes
[List top causes for {input.message}]

### Home Remedies
[Give 2-3 home remedies.]

### Recommended Medicines
- Paracetamol: [Buy on 1mg](https://www.1mg.com/search/all?name=Paracetamol)
- Ibuprofen: [Buy on 1mg](https://www.1mg.com/search/all?name=Ibuprofen)

### Health Score: {health_score if health_score else 'N/A'}
{ '🎉 Excellent! Keep it up.' if health_score and health_score > 80 else '' }

**Disclaimer**: This is for informational purposes only.
"""
        elif input.type == "medicine":
            medicine = input.message.replace("tell me about", "").strip()
            prompt = f"""
User wants info about: {medicine}

Respond as:

## 💊 Medicine: {medicine}

### What It Does
[Explain use of {medicine}]

### How It Works
[Mechanism]

### Side Effects & Precautions
[List 2-3 side effects, and warnings]

### Where to Buy
- [Buy {medicine} on 1mg](https://www.1mg.com/search/all?name={medicine.replace(' ', '%20')})

**Disclaimer**: Consult a healthcare professional.
"""
        else:
            raise HTTPException(status_code=400, detail="Type must be medicine or symptom")

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "system", "content": base_system},{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024
        )

        return {"response": response.choices[0].message.content.strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
