import os
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

client = AsyncIOMotorClient(MONGO_URI)
db = client["haiku"]

def get_collection(name):
    return db[name]

def analyze_weather_with_groq(weather_data: dict) -> str:
    """Send weather data to Gemini and get a relaxing, actionable suggestion."""
    import requests
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyBjjqwWneWG-ijoep-Smg31lPLxdx5Z4s4")
    if not GEMINI_API_KEY:
        return "No Gemini API key configured."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = (
        "Given the following weather data in JSON, provide a relaxing, actionable suggestion for the user. "
        "Be concise and gentle.\n\nWeather Data:\n" + str(weather_data)
    )
    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        # Gemini returns suggestions in candidates[0].content.parts[0].text
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"Gemini analysis failed: {e}"
