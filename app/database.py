"""
MongoDB connection module using motor async driver.
"""

import os

import certifi
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional

load_dotenv()

# MongoDB connection settings from env
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGO_DB", "chat-room")

# Global client and database references
client: Optional[AsyncIOMotorClient] = None
db = None


async def connect_to_mongo():
    """Initialize MongoDB connection."""
    global client, db
    # Use certifi for SSL certificates (required for MongoDB Atlas on some platforms)
    client = AsyncIOMotorClient(MONGO_URL, tlsCAFile=certifi.where())
    db = client[DATABASE_NAME]

    # Create indexes for better query performance
    await db.users.create_index("username", unique=True)
    await db.rooms.create_index("participant_usernames")
    await db.messages.create_index("room_id")
    await db.messages.create_index("created_at")


async def close_mongo_connection():
    """Close MongoDB connection."""
    global client
    if client:
        client.close()


def get_database():
    """Get the database instance."""
    return db


async def get_or_create_user(username: str) -> dict:
    """
    Get user by username, or create if not exists.
    This is the core user identification mechanism - no auth tokens needed.
    """
    user = await db.users.find_one({"username": username})
    if user is None:
        result = await db.users.insert_one({"username": username})
        user = {"_id": result.inserted_id, "username": username}
    return user
