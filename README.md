# Haiku Backend

This is the FastAPI backend for the relaxing task/timetable/weather webapp.

## Features
- Task management (CRUD, with optional deadlines)
- College timetable management (CRUD)
- Weather updates and suggestions (Groq integration)
- MongoDB as data store
- All features exposed via REST API (for web frontend and IoT/ESP32)

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and update with your MongoDB URI and Groq API key.
3. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

## API Endpoints
- `/api/tasks` (GET, POST)
- `/api/tasks/{id}` (PUT, DELETE)
- `/api/timetable` (GET, POST)
- `/api/timetable/{id}` (PUT, DELETE)
- `/api/weather` (GET)
