"""
Pydantic models for request/response validation.
Keeping it simple - minimal models that match the MongoDB schema.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# --- User Models ---

class UserResponse(BaseModel):
    id: str
    username: str


# --- Room Models ---

class RoomCreate(BaseModel):
    name: str
    participant_usernames: List[str] = Field(default_factory=list)


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    participant_usernames: Optional[List[str]] = None


class RoomResponse(BaseModel):
    id: str
    name: str
    owner_username: str
    participant_usernames: List[str]
    created_at: datetime


# --- Message Models ---

class MessageResponse(BaseModel):
    id: str
    room_id: str
    sender_username: str
    text: str
    created_at: datetime


# --- Helper functions to convert MongoDB documents ---

def user_to_response(user: dict) -> UserResponse:
    """Convert MongoDB user document to response model."""
    return UserResponse(
        id=str(user["_id"]),
        username=user["username"]
    )


def room_to_response(room: dict) -> RoomResponse:
    """Convert MongoDB room document to response model."""
    return RoomResponse(
        id=str(room["_id"]),
        name=room["name"],
        owner_username=room["owner_username"],
        participant_usernames=room["participant_usernames"],
        created_at=room["created_at"]
    )


def message_to_response(message: dict) -> MessageResponse:
    """Convert MongoDB message document to response model."""
    return MessageResponse(
        id=str(message["_id"]),
        room_id=str(message["room_id"]),
        sender_username=message["sender_username"],
        text=message["text"],
        created_at=message["created_at"]
    )
