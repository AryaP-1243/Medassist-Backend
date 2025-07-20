import os
import json
import re
import firebase_admin
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import firestore
from firebase_admin import credentials, initialize_app, auth
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Firebase init
cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
cred_info = json.loads(cred_json)
cred = credentials.Certificate(cred_info)
project_id = cred_info["project_id"]

if not firebase_admin._apps:
    initialize_app(cred, {'projectId': project_id})

db = firestore.Client(credentials=cred.get_credential(), project=project_id)

# Groq init
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# FastAPI setup
app = FastAPI(title="MedAssist API", version="2.0")

origins = [
    "http://localhost:8000",
    "https://aryap-1243.github.io",
    "https://aryap-1243.github.io/Medassist-app/"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Models
class UserProfileRequest(BaseModel):
    uid: str

class FoodHistoryRequest(BaseModel):
    food_history: str

class ChatRequest(BaseModel):
    message: str
    type: str

# Auth Dependency
async def get_current_uid(request: Request):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token.")
    token = token.replace("Bearer ", "")
    try:
        decoded = auth.verify_id_token(token)
        return decoded['uid']
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# Health score
@app.post("/user/food-history")
async def submit_food(req: FoodHistoryRequest, uid: str = Depends(get_current_uid)):
    prompt = f"""
    You are a dietitian. Analyze this food history and respond strictly in this format:

    Score: [0-100]

    Message: [Short health feedback]

    Suggestions:
    - [Tip1]
    - [Tip2]
    - [Tip3]

    Food: {req.food_history}
    """

    res = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": "You are a health AI providing concise health insights."},
            {"role": "user", "content": prompt}
        ]
    )

    ai_output = res.choices[0].message.content

    # Parse response
    score_match = re.search(r'Score:\s*(\d+)', ai_output)
    score = int(score_match.group(1)) if score_match else 50

    message_match = re.search(r'Message:\s*(.+)', ai_output)
    message = message_match.group(1).strip() if message_match else "Could not parse message."

    suggestions = re.findall(r'-\s*(.+)', ai_output)

    user_ref = db.collection('users').document(uid)
    user_ref.set({
        'food_history': req.food_history,
        'health_score': score,
        'message': message,
        'suggestions': suggestions,
        'lastFoodUpdate': firestore.SERVER_TIMESTAMP
    }, merge=True)

    return {
        "health_score": score,
        "message": message,
        "suggestions": suggestions
    }

# User Profile
@app.post("/user/profile", response_model=dict)
async def get_user_profile(user_request: UserProfileRequest, uid: str = Depends(get_current_uid)):
    if user_request.uid != uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="UID mismatch.")

    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()

    if not user_doc.exists:
        user_record = auth.get_user(uid)
        data_to_save = {
            'email': user_record.email,
            'lastLogin': firestore.SERVER_TIMESTAMP,
            'chat_history': [],
            'food_history': None,
            'health_score': None,
            'message': None,
            'suggestions': []
        }
        user_ref.set(data_to_save)
        return data_to_save

    return user_doc.to_dict()
# Chat with AI
@app.post("/ask")
async def ask(req: ChatRequest, uid: str = Depends(get_current_uid)):
    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    data = user_doc.to_dict()
    chat_history = data.get('chat_history', [])

    system_prompt = """
    You are MedAssist, a professional health assistant.

    - If the user asks for medicines, suggest relevant ones (no hardcoding). Use AI reasoning.
    - Provide 1mg.com links for each medicine: https://www.1mg.com/search/all?name=MedicineName
    - Suggest hospitals in Bengaluru: Manipal Hospital, Fortis Bannerghatta, Narayana Health City.
    - Do not make direct diagnoses. Say: "Possible conditions include..."
    - Place this disclaimer at the bottom: "**Disclaimer:** This is not medical advice. Consult a doctor."
    """

    context = []
    for msg in chat_history[-5:]:
        context.append({"role": msg['role'], "content": msg['content']})

    context.append({"role": "user", "content": req.message})

    response = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "system", "content": system_prompt}] + context
    )

    ai_reply = response.choices[0].message.content

    # Append disclaimer at bottom only
    ai_reply += "\n\n**Disclaimer:** This is not medical advice. Consult a doctor."

    # Update history
    chat_history.append({"role": "user", "content": req.message, "type": req.type})
    chat_history.append({"role": "assistant", "content": ai_reply})

    user_ref.update({'chat_history': chat_history})

    return {"response": ai_reply, "chat_history": chat_history}

# Delete chat history
@app.post("/user/chat-history/delete")
async def delete_chat(req: dict, uid: str = Depends(get_current_uid)):
    content = req.get("content")
    user_ref = db.collection('users').document(uid)
    doc = user_ref.get()
    if not doc.exists():
        raise HTTPException(status_code=404, detail="User not found")

    data = doc.to_dict()
    new_history = [msg for msg in data.get('chat_history', []) if msg.get('content') != content]
    user_ref.update({'chat_history': new_history})

    return {"chat_history": new_history}

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}
