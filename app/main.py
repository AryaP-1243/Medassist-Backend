from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import json, random, os
from groq import Groq
from sendinblue import Sendinblue
from twilio.rest import Client

app = FastAPI()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
twilio_client = Client(os.getenv("TWILIO_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
sendinblue = Sendinblue(os.getenv("SENDINBLUE_API_KEY"))

DATA_FILE = "users_data.json"

class LoginInput(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None

class OTPVerify(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    otp: str
    food_history: str

class UserInput(BaseModel):
    message: str
    type: str
    email_or_phone: str

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Store OTPs temporarily
otps = {}

@app.post("/send-otp")
def send_otp(data: LoginInput):
    otp = str(random.randint(1000, 9999))
    identifier = data.email if data.email else data.phone
    otps[identifier] = otp

    if data.email:
        sendinblue.send_email(to=data.email, subject="Your MedAssist OTP", content=f"Your OTP is {otp}")
    elif data.phone:
        twilio_client.messages.create(
            body=f"Your MedAssist OTP is {otp}",
            from_=os.getenv("TWILIO_PHONE"),
            to=data.phone
        )
    return {"message": "OTP sent successfully"}

@app.post("/verify-otp")
def verify_otp(data: OTPVerify):
    identifier = data.email if data.email else data.phone
    if otps.get(identifier) != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user_data = load_data()
    user_data[identifier] = {
        "food_history": data.food_history,
        "history": [],
        "health_score": random.randint(50, 100)
    }
    save_data(user_data)
    return {"message": "User verified", "health_score": user_data[identifier]["health_score"]}

@app.post("/ask")
def ask(data: UserInput):
    user_data = load_data()
    user = user_data.get(data.email_or_phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prompt = ""
    if data.type == "medicine":
        prompt = f"""
Give detailed, human-like, doctor-style info about {data.message}.
Use markdown, provide a **realistic explanation**, and add:

- What it is
- How it works
- Side effects (realistic)
- Suggested usage
- Add this at the end: 🛒 **[Buy {data.message} on 1mg](https://www.1mg.com/search/all?name={data.message.replace(" ", "%20")})**
"""
    else:
        prompt = f"""
The user says: {data.message}

Provide:

- Possible causes (realistic, not generic)
- Home remedies (real, Indian context if possible)
- Suggested medicines (give correct links)
- Health score impact from food: {user['food_history']}
- Add emoji headers and sound human like a caring doctor.
"""

    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "system", "content": "You are MedAssist, a human-like AI doctor."},
                  {"role": "user", "content": prompt}]
    )

    reply = response.choices[0].message.content.strip()

    user["history"].append({"message": data.message, "type": data.type})
    save_data(user_data)

    return {"response": reply, "history": user["history"]}
