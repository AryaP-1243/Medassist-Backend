from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import os, random, time
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Load API keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
if not GROQ_API_KEY or not SENDGRID_API_KEY:
    raise Exception("Missing API Keys in Environment Variables")

client = Groq(api_key=GROQ_API_KEY)

# Simple storage for OTPs and user data
otps = {}
users_file = "users_data.json"

if not os.path.exists(users_file):
    with open(users_file, "w") as f:
        json.dump({}, f)

def load_users():
    with open(users_file, "r") as f:
        return json.load(f)

def save_users(data):
    with open(users_file, "w") as f:
        json.dump(data, f, indent=4)

class OTPRequest(BaseModel):
    email: str

class OTPVerify(BaseModel):
    email: str
    otp: str

class AskRequest(BaseModel):
    message: str
    type: str  # "medicine" or "symptom"
    token: str  # Email or Phone

@app.post("/send-email-otp")
def send_email_otp(req: OTPRequest):
    otp = str(random.randint(100000, 999999))
    otps[req.email] = {"otp": otp, "timestamp": time.time()}
    
    message = Mail(
        from_email='your_email@domain.com',  # Set your verified sender
        to_emails=req.email,
        subject='Your MedAssist OTP',
        plain_text_content=f'Your OTP is {otp}. It is valid for 5 minutes.'
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        return {"message": "OTP sent to email."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify-email-otp")
def verify_email_otp(req: OTPVerify):
    record = otps.get(req.email)
    if not record or record["otp"] != req.otp or time.time() - record["timestamp"] > 300:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    # Save user if not exists
    users = load_users()
    if req.email not in users:
        users[req.email] = {"history": [], "food_history": "", "health_score": random.randint(50, 90)}
    save_users(users)

    return {"message": "OTP verified", "token": req.email, "health_score": users[req.email]["health_score"]}

@app.post("/health-score")
def health_score(phone_data: dict):
    phone = phone_data.get("phone")
    users = load_users()
    if phone not in users:
        users[phone] = {"history": [], "food_history": "", "health_score": random.randint(50, 90)}
    save_users(users)
    return {"health_score": users[phone]["health_score"]}

@app.post("/ask")
def ask(req: AskRequest):
    users = load_users()
    user = users.get(req.token)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    prompt = ""
    if req.type == "symptom":
        prompt = f"""
You are a world-class AI health assistant named MedAssist.

User says: "{req.message}"

Give a professional, humanized doctor-like reply in **Markdown**:

## 🩺 Symptom Analysis

### Possible Causes:
List top 3 causes for "{req.message}" in natural language.

### Home Remedies:
Suggest 2-3 effective home remedies.

### Recommended Medicines:
Suggest 2-3 OTC medicines if applicable. Provide their purpose.

### 🛒 Where to Buy:
Provide relevant **1mg links only for the medicine names, not the symptom**.
Format: 
[Buy {medicine_name} on 1mg](https://www.1mg.com/search/all?name={medicine_name})

### Health Score Impact:
Current food history: {user.get('food_history', 'N/A')}
Explain if this food could affect the symptom.

---

**Disclaimer:** This is general information. Consult a healthcare professional.
"""
    elif req.type == "medicine":
        med_name = req.message.strip().replace("Tell me about", "").strip()
        prompt = f"""
You are MedAssist, a professional AI pharmacist.

Give a detailed answer about **{med_name}** in **Markdown**:

## 💊 Medicine: {med_name}

### What It Does:
Explain usage of {med_name}.

### How It Works:
Brief mechanism of action.

### Side Effects:
List 3 common side effects.

### 🛒 Where to Buy:
[Buy {med_name} on 1mg](https://www.1mg.com/search/all?name={med_name})

---

**Disclaimer:** Always consult a doctor before taking medicines.
"""
    else:
        raise HTTPException(status_code=400, detail="Invalid type")

    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are MedAssist, respond like a caring doctor in Markdown."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1024
        )
        reply = response.choices[0].message.content.strip()

        # Save history
        user["history"].append({
            "message": req.message,
            "type": req.type,
            "timestamp": time.time()
        })
        users[req.token] = user
        save_users(users)

        return {"response": reply, "history": user["history"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error.")

@app.get("/")
def root():
    return {"message": "MedAssist Backend Active"}
