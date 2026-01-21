import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/temi_event")
DB_NAME = os.getenv("DB_NAME", "temi_event")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]


registrations = db["registrations"]
feedback = db["feedback"]

async def ensure_indexes():
    await registrations.create_index([("event_id", 1), ("email", 1)])
    await registrations.create_index([("event_id", 1), ("created_at", -1)])
    await feedback.create_index([("event_id", 1), ("created_at", -1)])
