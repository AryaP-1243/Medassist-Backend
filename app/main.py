import os, json, re
import firebase_admin
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import firestore
from firebase_admin import credentials, initialize_app, auth
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# --- Firebase & Groq Initialization ---
try:
    creds_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if not creds_json: raise ValueError("FIREBASE_CREDENTIALS_JSON missing.")
    creds_dict = json.loads(creds_json)
    cred = credentials.Certificate(creds_dict)
    project_id = creds_dict.get("project_id")
    if not project_id: raise ValueError("project_id missing.")
    if not firebase_admin._apps:
        initialize_app(cred, {'projectId': project_id})
    db = firestore.Client(credentials=cred.get_credential(), project=project_id)
except Exception as e:
    raise RuntimeError(f"Firebase Init Failed: {e}")

try:
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
except Exception as e:
    raise RuntimeError(f"Groq Init Failed: {e}")

app = FastAPI(title="MedAssist API", version="1.0.1")
app.add_middleware(CORSMiddleware,
    allow_origins=["https://aryap-1243.github.io", "http://localhost:8080"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Models ---
class UserProfileRequest(BaseModel): uid: str
class FoodHistoryRequest(BaseModel): food_history: str
class HealthScoreResponse(BaseModel): health_score: int; message: str; suggestions: list[str]
class ChatRequest(BaseModel): message: str; type: str
class DeleteChatRequest(BaseModel): content: str
class ChatMessage(BaseModel): role: str; content: str; type: str = None
class ChatResponse(BaseModel): response: str; chat_history: list[ChatMessage]

# --- Auth ---
async def get_current_uid(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or "Bearer " not in auth_header:
        raise HTTPException(status_code=401, detail="Missing or invalid token.")
    token = auth_header.split("Bearer ")[1]
    return auth.verify_id_token(token)['uid']

# --- Endpoints ---

@app.post("/user/profile", response_model=dict)
async def get_profile(user_request: UserProfileRequest, uid: str = Depends(get_current_uid)):
    if user_request.uid != uid:
        raise HTTPException(403, detail="UID mismatch")
    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        user_record = auth.get_user(uid)
        data = {
            'email': user_record.email,
            'lastLogin': firestore.SERVER_TIMESTAMP,
            'chat_history': [],
            'health_score': None,
            'message': None,
            'suggestions': []
        }
        user_ref.set(data)
        return data
    profile = user_doc.to_dict()
    profile.setdefault('message', None)
    profile.setdefault('suggestions', [])
    profile.setdefault('chat_history', [])
    return profile

@app.post("/user/food-history", response_model=HealthScoreResponse)
async def submit_food_history(req: FoodHistoryRequest, uid: str = Depends(get_current_uid)):
    prompt = f"""Analyze this food history and return:
Score: [0-100]
Message: [brief comment]
Suggestions:
- Tip 1
- Tip 2
Food History: {req.food_history}"""
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192"
        )
        response = completion.choices[0].message.content
        score = int(re.search(r'Score:\s*(\d+)', response).group(1)) if re.search(r'Score:\s*(\d+)', response) else 50
        message = re.search(r'Message:\s*(.*?)(?=\nSuggestions:|\Z)', response, re.DOTALL).group(1).strip()
        suggestions = re.findall(r'^[\*\-]+\s*(.*)', response, re.MULTILINE)
        if not suggestions: suggestions = ["Consider adding more balanced meals."]
        update_data = {
            'food_history': req.food_history,
            'health_score': score,
            'message': message,
            'suggestions': suggestions,
            'lastFoodUpdate': firestore.SERVER_TIMESTAMP
        }
        db.collection('users').document(uid).set(update_data, merge=True)
        return HealthScoreResponse(health_score=score, message=message, suggestions=suggestions)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/ask", response_model=ChatResponse)
async def ask(req: ChatRequest, uid: str = Depends(get_current_uid)):
    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists: raise HTTPException(404, detail="User not found.")
    chat_history = user_doc.to_dict().get('chat_history', [])
    if not isinstance(chat_history, list): chat_history = []
    system_prompt = """You are MedAssist, an AI health guide.
Always respond with:
**Disclaimer:** This is for educational purposes. Consult a doctor for diagnosis.
If you mention medicines, link them like: [Paracetamol](https://www.1mg.com/search/all?name=Paracetamol)
Recommend hospitals if serious symptoms: Manipal Hospital, Fortis, Narayana Health City."""
    llm_messages = [{"role": "system", "content": system_prompt}] + \
                   [{"role": m['role'], "content": m['content']} for m in chat_history[-10:]] + \
                   [{"role": "user", "content": req.message}]
    completion = groq_client.chat.completions.create(
        messages=llm_messages, model="llama3-8b-8192"
    )
    reply = completion.choices[0].message.content
    chat_history.append({"role": "user", "content": req.message, "type": req.type})
    chat_history.append({"role": "assistant", "content": reply})
    user_ref.update({"chat_history": chat_history})
    return ChatResponse(response=reply, chat_history=chat_history)

@app.post("/user/chat-history/delete", response_model=ChatResponse)
async def delete(req: DeleteChatRequest, uid: str = Depends(get_current_uid)):
    user_ref = db.collection('users').document(uid)
    doc = user_ref.get()
    if not doc.exists: raise HTTPException(404, detail="User not found.")
    chat_history = doc.to_dict().get('chat_history', [])
    idx = next((i for i, m in enumerate(chat_history) if m['role'] == 'user' and m['content'] == req.content), -1)
    if idx != -1:
        del chat_history[idx:idx+2] if idx+1 < len(chat_history) and chat_history[idx+1]['role']=='assistant' else chat_history.pop(idx)
        user_ref.update({"chat_history": chat_history})
    last_response = next((m['content'] for m in reversed(chat_history) if m['role']=='assistant'), "History updated.")
    return ChatResponse(response=last_response, chat_history=chat_history)
