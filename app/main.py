from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, auth, firestore
from groq import Groq
import os, json
from datetime import datetime

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

firebase_creds = os.getenv("FIREBASE_CREDENTIALS_JSON")
if not firebase_creds:
    raise ValueError("FIREBASE_CREDENTIALS_JSON not found in env.")

creds_dict = json.loads(firebase_creds)
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

cred = credentials.Certificate(creds_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class AskRequest(BaseModel):
    message: str
    type: str
    uid: str

class OTPRequest(BaseModel):
    id_token: str
    food_history: str

def calculate_health_score_ai(food):
    system_prompt = "You are a health assessment AI. Given a user's recent food intake, return a health score from 0 to 100. 100 is very healthy, 0 is very unhealthy. Don't explain, just return the number."

    user_prompt = f"Food eaten in last 2-3 days:\n{food}\n\nReturn only the score (number between 0-100)."

    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_prompt}],
        temperature=0,
        max_tokens=10
    )

    output = response.choices[0].message.content.strip()

    try:
        score = int(output)
        return max(0, min(100, score))
    except:
        return 50  # Fallback in case AI returns unexpected text

@app.get("/health")
def health():
    return {"status": "ok"}

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
            'health_score': calculate_health_score_ai(data.food_history),
            'updated_at': datetime.utcnow()
        })

        return {"uid": uid, "health_score": calculate_health_score(data.food_history)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ask")
def ask(request: AskRequest):
    user_ref = db.collection('users').document(request.uid)
    user_doc = user_ref.get()

    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")

    user_data = user_doc.to_dict()

    system_message = "You are MedAssist, a world-class AI doctor. Give detailed yet friendly replies in markdown. Always suggest correct medicines with 1mg.com links."

    prompt = ""
    if request.type == "symptom":
        prompt = f"""
User: {request.message}

## 🩺 Symptom Assessment

### Possible Causes:
List 3 likely reasons.

### Home Remedies:
Suggest 2 remedies.

### Medicines:
List 2-3 medicines with 1mg links.

### Health Score Link:
User's food: {user_data.get('food_history', 'No data')}
Any link between food and symptom? Answer briefly.
"""
    elif request.type == "medicine":
        prompt = f"""
User asked about: {request.message}

## 💊 Medicine: {request.message}

### What It Does:
Purpose.

### How It Works:
Mechanism.

### Side Effects & Precautions:
3 side effects.
2 warnings.

### Where to Buy:
[Buy on 1mg](https://www.1mg.com/search/all?name={request.message.replace(" ", "%20")})
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

    history_ref = user_ref.collection('history')
    history_ref.add({"message": request.message, "type": request.type, "timestamp": datetime.utcnow()})

    history_docs = history_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).stream()
    history = [{"message": doc.to_dict()["message"], "type": doc.to_dict()["type"]} for doc in history_docs]

    return {"response": reply, "history": history}
