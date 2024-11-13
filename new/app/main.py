from fastapi import FastAPI, HTTPException, Form, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
import openai
import os
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

# FastAPI setup
app = FastAPI()

# Templates and static files setup
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Load API key from .env file or environment variable
load_dotenv()  # Memuat variabel lingkungan dari file .env
openai.api_key = os.getenv("OPENAI_API_KEY")

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")  # Default jika tidak ada variabel lingkungan
client = AsyncIOMotorClient(MONGO_URI)
db = client["iot_app"]  # Database name
users_collection = db["users"]  # Collection for users

# Sesi user aktif
current_user = {"name": None}

# Kelas untuk menerima input dari pengguna
class Message(BaseModel):
    user_message: str

# Menyimpan konteks percakapan
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
]


@app.get("/", response_class=HTMLResponse)
async def login_register_page(request: Request):
    """Halaman login dan register."""
    return templates.TemplateResponse("login_register.html", {"request": request, "message": ""})


@app.post("/register", response_class=HTMLResponse)
async def register_user(request: Request, username: str = Form(...), password: str = Form(...)):
    """Register user baru."""
    # Periksa apakah user sudah ada
    existing_user = await users_collection.find_one({"username": username})
    if existing_user:
        return templates.TemplateResponse("login_register.html", {"request": request, "message": "User already exists!"})

    # Simpan user ke MongoDB
    new_user = {"username": username, "password": password}
    await users_collection.insert_one(new_user)
    return templates.TemplateResponse("login_register.html", {"request": request, "message": "Registered successfully. Please login."})


@app.post("/login", response_class=HTMLResponse)
async def login_user(request: Request, username: str = Form(...), password: str = Form(...)):
    # """Login user."""
    # # Periksa kredensial user
    # user = await users_collection.find_one({"username": username})
    # if not user or user["password"] != password:
    #     return templates.TemplateResponse("login_register.html", {"request": request, "message": "Invalid username or password."})

    # # Set sesi user aktif
    current_user["name"] = username
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Halaman dashboard."""
    if not current_user["name"]:
        return RedirectResponse(url="/", status_code=303)

    # Data IoT dummy
    iot_data = {
        "heart_rate": 75,
        "temperature": 36.6,
        "oxygen_level": 98,
        "bmi": 22.5,
    }
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": current_user["name"], "data": iot_data})

@app.post("/chat")
async def chat_with_openai(message: Message):
    try:
        # Menambahkan pesan pengguna ke dalam konteks
        messages.append({"role": "user", "content": message.user_message})

        # Meminta OpenAI untuk melanjutkan percakapan
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )

        # Mendapatkan respons dari model dan menambahkannya ke dalam pesan
        chat_message = response['choices'][0]['message']['content']
        messages.append({"role": "assistant", "content": chat_message})

        return {"ai_response": chat_message}
    except openai.error.OpenAIError as e:
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")