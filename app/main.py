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

# --- Initialization with Error Handling ---
try:
    firebase_credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if not firebase_credentials_json: raise ValueError("FIREBASE_CREDENTIALS_JSON not set.")
    parsed_credentials_info = json.loads(firebase_credentials_json)
    cred = credentials.Certificate(parsed_credentials_info)
    project_id = parsed_credentials_info.get("project_id")
    if not project_id: raise ValueError("project_id missing in FIREBASE_CREDENTIALS_JSON.")
    if not firebase_admin._apps:
        initialize_app(cred, {'projectId': project_id})
    db = firestore.Client(credentials=cred.get_credential(), project=project_id)
except Exception as e:
    raise RuntimeError(f"FATAL: Firebase initialization failed: {e}")

try:
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key: raise ValueError("GROQ_API_KEY not set.")
    groq_client = Groq(api_key=groq_api_key)
except Exception as e:
    raise RuntimeError(f"FATAL: Groq initialization failed: {e}")

# --- FastAPI App ---
app = FastAPI(title="MedAssist API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aryap-1243.github.io/Medassist-app/", "https://aryap-1243.github.io", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class UserProfileRequest(BaseModel): uid: str
class FoodHistoryRequest(BaseModel): food_history: str
class HealthScoreResponse(BaseModel): health_score: int; message: str; suggestions: list[str]
class ChatRequest(BaseModel): message: str; type: str
class DeleteChatRequest(BaseModel): content: str
class ChatMessage(BaseModel): role: str; content: str; type: str = None
class ChatResponse(BaseModel): response: str; chat_history: list[ChatMessage]

# --- Auth Dependency ---
async def get_current_uid(request: Request) -> str:
    authorization: str = request.headers.get("Authorization")
    if not authorization or "Bearer " not in authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth token missing or invalid.")
    token = authorization.split("Bearer ")[1]
    try:
        return auth.verify_id_token(token)['uid']
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid auth token: {e}")

# --- API Endpoints ---
@app.post("/user/profile", response_model=dict)
async def get_user_profile(user_request: UserProfileRequest, uid: str = Depends(get_current_uid)):
    if user_request.uid != uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="UID mismatch")
    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        user_record = auth.get_user(uid)
        data_to_save = {'email': user_record.email, 'lastLogin': firestore.SERVER_TIMESTAMP, 'chat_history': []}
        user_ref.set(data_to_save)
        data_to_return = {'email': user_record.email, 'lastLogin': None, 'chat_history': [], 'health_score': None}
        return data_to_return
    return user_doc.to_dict()

@app.post("/user/food-history", response_model=HealthScoreResponse)
async def submit_food_history(request: FoodHistoryRequest, uid: str = Depends(get_current_uid)):
    try:
        prompt = f"Analyze this food history. Respond in this exact format:\nScore: [0-100]\nMessage: [Brief comment]\nSuggestions:\n- [Tip 1]\n- [Tip 2]\nFood History: {request.food_history}"
        completion = groq_client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama3-8b-8192")
        response = completion.choices[0].message.content
        score_match = re.search(r'Score:\s*(\d+)', response)
        health_score = int(score_match.group(1)) if score_match else 50
        message_match = re.search(r'Message:\s*(.*?)(?=\nSuggestions:|\Z)', response, re.DOTALL | re.IGNORECASE)
        message = message_match.group(1).strip() if message_match else "AI response could not be parsed."
        suggestions = [s for s in re.findall(r'^[ \t]*[\*\-]+\s*(.*)', response, re.MULTILINE) if s]
        update_data = {'food_history': request.food_history, 'health_score': health_score, 'message': message, 'suggestions': suggestions, 'lastFoodUpdate': firestore.SERVER_TIMESTAMP}
        db.collection('users').document(uid).set(update_data, merge=True)
        return HealthScoreResponse(health_score=health_score, message=message, suggestions=suggestions)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/ask", response_model=ChatResponse)
async def ask_medassist(request: ChatRequest, uid: str = Depends(get_current_uid)):
    try:
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        if not user_doc.exists: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        chat_history = user_doc.to_dict().get('chat_history', [])
        system_prompt = """You are MedAssist, a knowledgeable AI health guide. Your tone is professional and supportive. CRITICAL INSTRUCTIONS: 1. Disclaimer: ALWAYS start with: "**Disclaimer:** This is for educational purposes. Consult a medical professional for diagnosis." 2. Medicine Links: When you mention a medicine, you MUST format it as a markdown link for 1mg. Example: `[Paracetamol](https://www.1mg.com/search/all?name=Paracetamol)`. 3. Hospital Recommendations: If symptoms may require a doctor, recommend these Bengaluru hospitals: Manipal Hospital (Old Airport Road), Fortis Hospital (Bannerghatta Road), and Narayana Health City."""
        context_messages = [{"role": m['role'], "content": m['content']} for m in chat_history[-10:]]
        llm_messages = [{"role": "system", "content": system_prompt}] + context_messages + [{"role": "user", "content": request.message}]
        completion = groq_client.chat.completions.create(messages=llm_messages, model="llama3-8b-8192")
        assistant_response = completion.choices[0].message.content
        chat_history.append({"role": "user", "content": request.message, "type": request.type})
        chat_history.append({"role": "assistant", "content": assistant_response})
        user_ref.update({"chat_history": chat_history})
        return ChatResponse(response=assistant_response, chat_history=chat_history)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/user/chat-history/delete", response_model=ChatResponse)
async def delete_chat_item(request: DeleteChatRequest, uid: str = Depends(get_current_uid)):
    try:
        user_ref = db.collection('users').document(uid)
        doc = user_ref.get()
        if not doc.exists: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        chat_history = doc.to_dict().get('chat_history', [])
        index_to_delete = next((i for i, msg in enumerate(chat_history) if msg.get('role') == 'user' and msg.get('content') == request.content), -1)
        if index_to_delete != -1:
            if index_to_delete + 1 < len(chat_history) and chat_history[index_to_delete + 1].get('role') == 'assistant':
                del chat_history[index_to_delete : index_to_delete + 2]
            else:
                del chat_history[index_to_delete]
            user_ref.update({"chat_history": chat_history})
        last_response = next((m['content'] for m in reversed(chat_history) if m['role'] == 'assistant'), "History updated.")
        return ChatResponse(response=last_response, chat_history=chat_history)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
