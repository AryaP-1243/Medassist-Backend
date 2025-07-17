from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import os
import json

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Database file for simplicity
DB_FILE = "users_data.json"

# Helper to load & save user data
def load_data():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({"users": {}}, f)
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Pydantic models
class UserRegister(BaseModel):
    email: str
    phone: str

class FoodInput(BaseModel):
    email: str
    food_list: list

class UserInput(BaseModel):
    email: str
    message: str
    type: str

# Groq setup
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise Exception("GROQ_API_KEY environment variable not set.")
client = Groq(api_key=api_key)

# Basic food scoring
JUNK = ["pizza", "burger", "coke", "fries", "biryani"]
HEALTHY = ["salad", "dal", "fruits", "vegetable", "nuts", "curd"]

def calculate_score(food_list):
    score = 50  # Base
    for food in food_list:
        item = food.lower()
        if any(j in item for j in JUNK):
            score -= 10
        elif any(h in item for h in HEALTHY):
            score += 10
    return max(0, min(100, score))

# Routes
@app.post("/register")
def register(user: UserRegister):
    data = load_data()
    if user.email in data["users"]:
        return {"message": "User already exists."}
    data["users"][user.email] = {
        "phone": user.phone,
        "food_history": [],
        "symptoms": [],
        "health_score": 50
    }
    save_data(data)
    return {"message": "User registered successfully."}

@app.post("/food-history")
def food_history(input: FoodInput):
    data = load_data()
    if input.email not in data["users"]:
        raise HTTPException(status_code=404, detail="User not found.")

    user = data["users"][input.email]
    user["food_history"].extend(input.food_list)
    user["health_score"] = calculate_score(user["food_history"])
    save_data(data)

    return {
        "message": "Food history updated.",
        "health_score": user["health_score"]
    }

@app.post("/ask")
def ask(input: UserInput):
    try:
        data = load_data()
        if input.email not in data["users"]:
            raise HTTPException(status_code=404, detail="User not found.")

        user = data["users"][input.email]

        if input.type == "symptom":
            user["symptoms"].append(input.message)
            save_data(data)
            prompt = f"""
You are MedAssist, a professional AI healthcare assistant.

Symptom reported: "{input.message}"

Respond in **Markdown**:

## 🔍 Symptom: {input.message}

### Possible Causes
- Provide 3 potential causes.

### Home Remedies
- Give 2-3 simple remedies.

### Medicines
- List 2-3 medicines (do not hardcode).

### ⚠️ Disclaimer
This is not medical advice. Consult a doctor.
"""
        elif input.type == "medicine":
            prompt = f"""
You are MedAssist, a professional AI healthcare assistant.

Provide information about: **{input.message}**

Respond in **Markdown**:

## 💊 Medicine: {input.message}

### Overview
- What is it used for?

### How It Works
- Brief explanation.

### Side Effects
- Mention top 3 side effects.

### Buy Link
- [Buy on 1mg](https://www.1mg.com/search/all?name={input.message.replace(' ', '%20')})

### ⚠️ Disclaimer
This is not medical advice.
"""
        else:
            raise HTTPException(status_code=400, detail="Invalid type.")

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are MedAssist, reply in markdown with professional healthcare guidance."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1024
        )

        return {"response": response.choices[0].message.content.strip()}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")

@app.get("/history/{email}")
def get_history(email: str):
    data = load_data()
    if email not in data["users"]:
        raise HTTPException(status_code=404, detail="User not found.")
    return data["users"][email]
