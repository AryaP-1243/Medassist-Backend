from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, auth, firestore
from groq import Groq
import os, json
from datetime import datetime

# FastAPI setup
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Firebase Admin setup
firebase_creds = os.getenv("FIREBASE_CREDENTIALS_JSON")
if not firebase_creds:
    raise ValueError("FIREBASE_CREDENTIALS_JSON not found in environment variables.")
creds_dict = json.loads(firebase_creds)
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
firebase_admin.initialize_app(credentials.Certificate(creds_dict))
db = firestore.client()

# Groq LLM setup
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Models
class FoodInput(BaseModel):
    uid: str
    food_history: str

class AskRequest(BaseModel):
    message: str
    type: str
    uid: str

# New model for fetching history
class HistoryRequest(BaseModel):
    uid: str

# New model for fetching user data
class UserDataRequest(BaseModel):
    uid: str


# Routes
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/save-user")
def save_user(data: FoodInput):
    user_ref = db.collection('users').document(data.uid)

    # AI-based health score calculation using Groq
    prompt = f"""You are a health assistant. Rate this food history from 0 to 100 based on healthiness:

Food: {data.food_history}

Respond ONLY with the score (number)."""

    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10
    )
    score = int(''.join(filter(str.isdigit, response.choices[0].message.content.strip())))

    user_ref.set({
        "food_history": data.food_history,
        "health_score": score,
        "updated_at": datetime.utcnow()
    }, merge=True) # Use merge=True to update existing fields without overwriting others

    return {"health_score": score}

@app.post("/ask")
def ask(request: AskRequest):
    user_ref = db.collection('users').document(request.uid)
    user_doc = user_ref.get()

    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")

    user_data = user_doc.to_dict()

    system_message = "You are MedAssist, a world-class AI doctor. Provide answers in markdown with friendliness and expertise."

    if request.type == "symptom":
        prompt = f"""
User reported: {request.message}

## 🩺 Symptom Assessment

### Possible Causes:
List 3 possible reasons.

### Home Remedies:
Suggest 2 remedies.

### Medicines:
List 2-3 medicines with [1mg buy links](https://www.1mg.com/search/all?name=MEDICINE_NAME). Replace MEDICINE_NAME properly.

### Health Score Link:
User's recent food: {user_data.get('food_history', 'No data')}
Any connection between food and this symptom? Briefly explain.
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
        messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=1024
    )

    reply = response.choices[0].message.content.strip()

    # Save history
    history_ref = user_ref.collection('history')
    history_ref.add({
        "message": request.message,
        "type": request.type,
        "timestamp": datetime.utcnow()
    })

    return {"response": reply}

@app.post("/get-history")
def get_history(request: HistoryRequest):
    user_ref = db.collection('users').document(request.uid)
    history_ref = user_ref.collection('history')

    history_docs = history_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).stream()
    history = [{"message": doc.to_dict()["message"], "type": doc.to_dict()["type"]} for doc in history_docs]
    return {"history": history}

@app.post("/get-user-data")
def get_user_data(request: UserDataRequest):
    """
    Retrieves a user's food history and health score from Firestore.
    """
    user_ref = db.collection('users').document(request.uid)
    user_doc = user_ref.get()

    if user_doc.exists:
        user_data = user_doc.to_dict()
        return {
            "food_history": user_data.get("food_history"),
            "health_score": user_data.get("health_score")
        }
    else:
        # User document doesn't exist, return empty data
        return {
            "food_history": None,
            "health_score": None
        }
