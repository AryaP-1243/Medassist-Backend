from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, auth, firestore
from groq import Groq
import os
from datetime import datetime
import json

# Init app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Firebase Setup
creds_dict = json.loads(firebase_creds)
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

cred = credentials.Certificate(creds_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Groq setup
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Request models
class AskRequest(BaseModel):
    message: str
    type: str
    uid: str

class OTPRequest(BaseModel):
    id_token: str
    food_history: str

# Health Score Calculation (Simple logic for now)
def calculate_health_score(food):
    unhealthy = ['mutton', 'pizza', 'burger', 'oily', 'fried', 'alcohol']
    healthy = ['salad', 'fruits', 'vegetables', 'protein', 'grilled']
    score = 80
    for word in unhealthy:
        if word in food.lower():
            score -= 10
    for word in healthy:
        if word in food.lower():
            score += 5
    return max(0, min(100, score))

# Routes
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/send-otp")
def send_otp():
    return {"msg": "Use Firebase Authentication Client SDK for phone/email OTP."}

@app.post("/verify-otp")
def verify_otp(data: OTPRequest):
    try:
        decoded = auth.verify_id_token(data.id_token)
        uid = decoded['uid']
        email = decoded.get('email', '')
        phone = decoded.get('phone_number', '')

        user_ref = db.collection('users').document(uid)
        user_ref.set({
            'email': email,
            'phone': phone,
            'food_history': data.food_history,
            'health_score': calculate_health_score(data.food_history),
            'updated_at': datetime.utcnow()
        })

        return {"uid": uid, "health_score": calculate_health_score(data.food_history)}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Invalid Token or Verification Failed")

@app.post("/ask")
def ask(request: AskRequest):
    user_ref = db.collection('users').document(request.uid)
    user_data = user_ref.get().to_dict() if user_ref.get().exists else None

    if not user_data:
        raise HTTPException(status_code=404, detail="User not found.")

    system_message = "You are MedAssist, a world-class AI doctor. Give detailed yet human-like answers in markdown. Suggest correct medicines with relevant descriptions and always provide buy links from 1mg.com. Do not use user input directly in links."

    prompt = ""

    if request.type == "symptom":
        prompt = f"""
User: {request.message}

Give a medical assessment for this symptom.

Respond in markdown:

## 🩺 Symptom Assessment

### Possible Causes:
- List 3 possible reasons for the symptom.

### Home Remedies:
- Suggest 2 home care tips.

### Medicines:
- List 2-3 medicines with short descriptions and buy links from 1mg.com in markdown format. Avoid hardcoding input.

### Health Score:
- User's recent food: {user_data.get('food_history', 'No food data')}
- Possible link between food and symptom? Explain briefly.

---

Respond like a friendly doctor.
"""

    elif request.type == "medicine":
        prompt = f"""
User asked about: {request.message}

Give a detailed medicine explanation in markdown.

## 💊 Medicine: {request.message}

### What It Does:
- Explain purpose of this medicine.

### How It Works:
- Simple mechanism.

### Side Effects & Precautions:
- List 3 common side effects.
- List 2 warnings.

### Where to Buy:
- [Buy on 1mg](https://www.1mg.com/search/all?name={request.message.replace(" ", "%20")})

---

Respond like an expert medical professional, but make it friendly and human.
"""
    else:
        raise HTTPException(status_code=400, detail="Type must be 'medicine' or 'symptom'.")

    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "system", "content": system_message},
                  {"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=1024
    )

    reply = response.choices[0].message.content.strip()

    # Save to user history
    history_ref = user_ref.collection('history')
    history_ref.add({
        "message": request.message,
        "type": request.type,
        "timestamp": datetime.utcnow()
    })

    # Retrieve history (last 5 entries)
    history_docs = history_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).stream()
    history = [{"message": doc.to_dict()["message"], "type": doc.to_dict()["type"]} for doc in history_docs]

    return {"response": reply, "history": history}
