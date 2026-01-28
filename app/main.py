from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone
from app.routes.export_mail import router as export_mail_router
from app.routes.export_all_registrations import router as export_router
import csv
import io
import os

from bson import ObjectId  # ✅ add this
from .schemas import RegistrationIn, FeedbackIn
from .db import registrations, feedback, ensure_indexes
import json

app = FastAPI(title="Temi Event Backend (Mongo)", version="1.0.0")

# Global variable to store visitors
VISITORS_DATA = []

def load_visitors():
    global VISITORS_DATA
    try:
        with open("visitors.json", "r") as f:
            VISITORS_DATA = json.load(f)
        print(f"Loaded {len(VISITORS_DATA)} visitors.")
    except Exception as e:
        print(f"Error loading visitors.json: {e}")

app.include_router(export_mail_router, prefix="/api", tags=["Export Mail"])
app.include_router(export_router, prefix="/api", tags=["Export"])
templates = Jinja2Templates(directory="app/templates")


# ✅ define at module level (NOT inside startup)
def oid_to_str(doc: dict) -> dict:
    d = dict(doc)
    if "_id" in d and isinstance(d["_id"], ObjectId):
        d["_id"] = str(d["_id"])
    return d


@app.on_event("startup")
async def on_startup():
    try:
        await ensure_indexes()
        print("Indexes ensured.")
    except Exception as e:
        print(f"WARNING: Could not connect to MongoDB/ensure indexes: {e}")
        print("Running in limited mode (Visitors API will still work).")
    
    load_visitors()


def now_utc():
    return datetime.now(timezone.utc)


# ---------- JSON APIs (Temi app) ----------
@app.post("/api/events/{event_id}/registrations")
async def api_create_registration(event_id: str, payload: RegistrationIn):
    doc = {
        "event_id": event_id,
        "name": payload.name.strip(),
        "email": str(payload.email).lower(),
        "designation": payload.designation.strip(),
        "created_at": now_utc(),
        "source": "temi_kiosk",
    }
    result = await registrations.insert_one(doc)
    return {
        "ok": True,
        "id": str(result.inserted_id),
        "name": doc["name"],
        "email": doc["email"],
        "designation": doc["designation"],
        "created_at": doc["created_at"],
        "source": doc["source"],
    }


@app.post("/api/events/{event_id}/feedback")
async def api_create_feedback(event_id: str, payload: FeedbackIn):
    doc = {
        "event_id": event_id,
        "rating": payload.rating,
        "comment": payload.comment.strip(),
        "created_at": now_utc(),
        "source": "qr_phone",
    }
    result = await feedback.insert_one(doc)
    return {"ok": True, "id": str(result.inserted_id)}


@app.get("/api/visitors/search")
async def search_visitors(q: str = ""):
    if not q:
        return []
    
    query = q.lower()
    results = [
        v for v in VISITORS_DATA 
        if v.get("Name") and query in v["Name"].lower()
    ]
    # Return top 20 matches
    return results[:20]


# ---------- QR Web Pages (guest phone) ----------
@app.get("/r/{event_id}", response_class=HTMLResponse)
async def page_register(event_id: str, request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "event_id": event_id})


@app.post("/r/{event_id}", response_class=HTMLResponse)
async def submit_register(event_id: str, request: Request, name: str = Form(...), email: str = Form(...)):
    payload = RegistrationIn(name=name, email=email)
    doc = {
        "event_id": event_id,
        "name": payload.name.strip(),
        "email": str(payload.email).lower(),
        "created_at": now_utc(),
        "source": "qr_phone",
    }
    await registrations.insert_one(doc)
    return templates.TemplateResponse("thanks.html", {"request": request, "title": "Registration submitted!"})


@app.get("/f/{event_id}", response_class=HTMLResponse)
async def page_feedback(event_id: str, request: Request):
    return templates.TemplateResponse("feedback.html", {"request": request, "event_id": event_id})


@app.post("/f/{event_id}", response_class=HTMLResponse)
async def submit_feedback(event_id: str, request: Request, rating: int = Form(...), comment: int = Form("")):
    payload = FeedbackIn(rating=rating, comment=comment)
    doc = {
        "event_id": event_id,
        "rating": payload.rating,
        "comment": payload.comment.strip(),
        "created_at": now_utc(),
        "source": "qr_phone",
    }
    await feedback.insert_one(doc)
    return templates.TemplateResponse("thanks.html", {"request": request, "title": "Feedback submitted. Thank you!"})


# ---------- CSV Export (admin) ----------
@app.get("/api/events/{event_id}/export/registrations.csv")
async def export_registrations(event_id: str):
    cursor = registrations.find({"event_id": event_id}).sort("created_at", -1)
    rows = await cursor.to_list(length=100000)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "event_id", "name", "email", "designation", "created_at", "source"])
    for r in rows:
        w.writerow([
            str(r.get("_id")),
            r.get("event_id"),
            r.get("name"),
            r.get("email"),
            r.get("designation", ""),
            r.get("created_at").isoformat() if r.get("created_at") else "",
            r.get("source", ""),
        ])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv")


@app.get("/api/events/{event_id}/export/feedback.csv")
async def export_feedback(event_id: str):
    cursor = feedback.find({"event_id": event_id}).sort("created_at", -1)
    rows = await cursor.to_list(length=100000)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "event_id", "rating", "comment", "created_at", "source"])
    for r in rows:
        w.writerow([
            str(r.get("_id")),
            r.get("event_id"),
            r.get("rating"),
            r.get("comment"),
            r.get("created_at").isoformat() if r.get("created_at") else "",
            r.get("source", ""),
        ])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv")


# ---------- Debug ----------
@app.get("/api/debug/registrations-count")
async def registrations_count():
    count = await registrations.count_documents({})
    sample_raw = await registrations.find({}, {"event_id": 1, "name": 1, "email": 1}).limit(3).to_list(length=3)
    sample = [oid_to_str(x) for x in sample_raw]
    return {
        "MONGO_URI": os.getenv("MONGO_URI"),
        "MONGO_DB": os.getenv("MONGO_DB"),
        "MONGO_COLLECTION": os.getenv("MONGO_COLLECTION"),
        "count": count,
        "sample": sample,
    }
