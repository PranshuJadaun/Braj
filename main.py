from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import os

app = FastAPI(title="Haiku Relaxing Webapp API")

# CORS for frontend and IoT devices
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client["haiku"]

def get_collection(name):
    return db[name]

# Models
class Task(BaseModel):
    title: str
    description: Optional[str] = None
    deadline: Optional[str] = None  # ISO8601 string

class TaskInDB(Task):
    id: str

class TimetableEntry(BaseModel):
    day: str  # e.g. 'Monday'
    start_time: str  # e.g. '09:00'
    end_time: str  # e.g. '10:00'
    subject: str
    location: Optional[str] = None

class TimetableEntryInDB(TimetableEntry):
    id: str

# --- TASKS ENDPOINTS ---
from bson import ObjectId
from utils import get_collection, analyze_weather_with_groq
from fastapi import Query

@app.get("/tasks", response_model=List[TaskInDB])
async def get_tasks():
    tasks = []
    async for doc in get_collection("tasks").find():
        doc["id"] = str(doc["_id"])
        tasks.append(TaskInDB(**doc))
    return tasks

@app.post("/tasks", response_model=TaskInDB)
async def add_task(task: Task):
    doc = task.dict()
    result = await get_collection("tasks").insert_one(doc)
    doc["id"] = str(result.inserted_id)
    return TaskInDB(**doc)

@app.put("/tasks/{task_id}", response_model=TaskInDB)
async def update_task(task_id: str, task: Task):
    result = await get_collection("tasks").update_one({"_id": ObjectId(task_id)}, {"$set": task.dict()})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    doc = await get_collection("tasks").find_one({"_id": ObjectId(task_id)})
    doc["id"] = str(doc["_id"])
    return TaskInDB(**doc)

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    result = await get_collection("tasks").delete_one({"_id": ObjectId(task_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}

# --- TIMETABLE ENDPOINTS ---
@app.get("/timetable", response_model=List[TimetableEntryInDB])
async def get_timetable():
    entries = []
    async for doc in get_collection("timetable").find():
        doc["id"] = str(doc["_id"])
        entries.append(TimetableEntryInDB(**doc))
    return entries

@app.post("/timetable", response_model=TimetableEntryInDB)
async def add_timetable_entry(entry: TimetableEntry):
    doc = entry.dict()
    result = await get_collection("timetable").insert_one(doc)
    doc["id"] = str(result.inserted_id)
    return TimetableEntryInDB(**doc)

@app.put("/timetable/{entry_id}", response_model=TimetableEntryInDB)
async def update_timetable_entry(entry_id: str, entry: TimetableEntry):
    result = await get_collection("timetable").update_one({"_id": ObjectId(entry_id)}, {"$set": entry.dict()})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Timetable entry not found")
    doc = await get_collection("timetable").find_one({"_id": ObjectId(entry_id)})
    doc["id"] = str(doc["_id"])
    return TimetableEntryInDB(**doc)

@app.delete("/timetable/{entry_id}")
async def delete_timetable_entry(entry_id: str):
    result = await get_collection("timetable").delete_one({"_id": ObjectId(entry_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Timetable entry not found")
    return {"message": "Timetable entry deleted"}

# --- WEATHER ENDPOINT (with Groq AI suggestion) ---

@app.get("/weather/onboard")
async def get_weather_onboard(
    lat: float = Query(23.072190, description="Latitude", alias="lat"),
    lon: float = Query(76.829600, description="Longitude", alias="lon")
):
    import requests
    WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
    if not WEATHER_API_KEY:
        return {"error": "No weather API key configured."}
    url_current = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={lat},{lon}"
    url_forecast = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={lat},{lon}&days=1"
    try:
        resp_current = requests.get(url_current, timeout=10)
        resp_current.raise_for_status()
        weather_data = resp_current.json()
        resp_forecast = requests.get(url_forecast, timeout=10)
        resp_forecast.raise_for_status()
        forecast_data = resp_forecast.json()
        # Get next 6 hours rain probability (max)
        hours = forecast_data["forecast"]["forecastday"][0]["hour"]
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        next6h = [h for h in hours if datetime.strptime(h["time"], "%Y-%m-%d %H:%M") >= now][:6]
        rain_probs = [h.get("chance_of_rain", 0) for h in next6h]
        rain_probability = max(rain_probs) if rain_probs else 0
        # Umbrella recommendation: yes if any rain probability > 50% or totalprecip > 0
        umbrella_recommended = "yes" if rain_probability > 50 or any(h.get("will_it_rain", 0) for h in next6h) else "no"
        # Concise suggestion
        suggestion = analyze_weather_with_groq(weather_data)[:80]  # Truncate for ESP32
        return {
            "temperature": weather_data["current"]["temp_c"],
            "rain_probability_next_6h": rain_probability,
            "umbrella_recommended": umbrella_recommended,
            "suggestion": suggestion
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/weather")
async def get_weather(
    lat: float = Query(23.072190, description="Latitude", alias="lat"),
    lon: float = Query(76.829600, description="Longitude", alias="lon")
):
    import requests
    WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
    if not WEATHER_API_KEY:
        return {"error": "No weather API key configured."}
    # Fetch both current and 1-day forecast
    url_current = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={lat},{lon}"
    url_forecast = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={lat},{lon}&days=1"
    try:
        resp_current = requests.get(url_current, timeout=10)
        resp_current.raise_for_status()
        weather_data = resp_current.json()
        resp_forecast = requests.get(url_forecast, timeout=10)
        resp_forecast.raise_for_status()
        forecast_data = resp_forecast.json()
        # Umbrella recommendation: yes if precipitation probability or total > 0
        umbrella_recommended = "no"
        try:
            forecast_day = forecast_data["forecast"]["forecastday"][0]["day"]
            if (forecast_day.get("daily_will_it_rain", 0) == 1 or forecast_day.get("totalprecip_mm", 0) > 0 or forecast_day.get("daily_chance_of_rain", 0) > 50):
                umbrella_recommended = "yes"
        except Exception:
            pass
        suggestion = analyze_weather_with_groq(weather_data)
        return {
            "weather": weather_data,
            "forecast": forecast_data.get("forecast", {}),
            "suggestion": suggestion,
            "umbrella_recommended": umbrella_recommended
        }
    except Exception as e:
        return {"error": str(e)}
