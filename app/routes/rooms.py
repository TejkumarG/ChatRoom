"""
Room routes - CRUD operations for chat rooms.
All operations use X-Username header for user identification.
"""

from datetime import datetime
from typing import List

from bson import ObjectId
from fastapi import APIRouter, Header, HTTPException

from app.database import get_database, get_or_create_user
from app.models import (
    RoomCreate,
    RoomUpdate,
    RoomResponse,
    room_to_response,
)

router = APIRouter(prefix="/rooms", tags=["rooms"])


def validate_object_id(id_str: str) -> ObjectId:
    """Validate and convert string to ObjectId."""
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid room ID format")


@router.post("", response_model=RoomResponse)
async def create_room(
    room_data: RoomCreate,
    x_username: str = Header(..., alias="X-Username")
):
    """
    Create a new chat room.
    The creator becomes the owner and is automatically added to participants.
    Empty participant list is fine - owner is added automatically.
    """
    db = get_database()
    username = x_username.strip()

    # Ensure owner user exists
    await get_or_create_user(username)

    # Start with owner in participants
    participants = [username]

    # Validate and add other participants if provided
    if room_data.participant_usernames:
        for participant in room_data.participant_usernames:
            participant = participant.strip()
            if participant and participant != username:
                # Check if user exists
                existing = await db.users.find_one({"username": participant})
                if not existing:
                    raise HTTPException(
                        status_code=400,
                        detail=f"User '{participant}' does not exist"
                    )
                if participant not in participants:
                    participants.append(participant)

    room_doc = {
        "name": room_data.name,
        "owner_username": username,
        "participant_usernames": participants,
        "created_at": datetime.utcnow()
    }

    result = await db.rooms.insert_one(room_doc)
    room_doc["_id"] = result.inserted_id

    return room_to_response(room_doc)


@router.get("/my", response_model=List[RoomResponse])
async def get_my_rooms(x_username: str = Header(..., alias="X-Username")):
    """
    Get all rooms where the current user is a participant.
    """
    db = get_database()
    username = x_username.strip()

    await get_or_create_user(username)

    rooms = await db.rooms.find(
        {"participant_usernames": username}
    ).to_list(length=100)

    return [room_to_response(room) for room in rooms]


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: str,
    x_username: str = Header(..., alias="X-Username")
):
    """
    Get a specific room by ID.
    User must be a participant to access the room.
    """
    db = get_database()
    username = x_username.strip()
    oid = validate_object_id(room_id)

    await get_or_create_user(username)

    room = await db.rooms.find_one({"_id": oid})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if username not in room["participant_usernames"]:
        raise HTTPException(status_code=403, detail="Not a participant of this room")

    return room_to_response(room)


@router.patch("/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: str,
    room_update: RoomUpdate,
    x_username: str = Header(..., alias="X-Username")
):
    """
    Update a room (name and/or participants).
    Only the room owner can update.
    """
    db = get_database()
    username = x_username.strip()
    oid = validate_object_id(room_id)

    await get_or_create_user(username)

    room = await db.rooms.find_one({"_id": oid})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room["owner_username"] != username:
        raise HTTPException(status_code=403, detail="Only owner can update room")

    # Build update document
    update_doc = {}
    if room_update.name is not None:
        update_doc["name"] = room_update.name
    if room_update.participant_usernames is not None:
        # Ensure owner stays in participants
        participants = list(set(room_update.participant_usernames))
        if username not in participants:
            participants.append(username)
        # Auto-create new participants
        for participant in participants:
            await get_or_create_user(participant)
        update_doc["participant_usernames"] = participants

    if update_doc:
        await db.rooms.update_one({"_id": oid}, {"$set": update_doc})
        room = await db.rooms.find_one({"_id": oid})

    return room_to_response(room)


@router.delete("/{room_id}")
async def delete_room(
    room_id: str,
    x_username: str = Header(..., alias="X-Username")
):
    """
    Delete a room and all its messages.
    Only the room owner can delete.
    """
    db = get_database()
    username = x_username.strip()
    oid = validate_object_id(room_id)

    await get_or_create_user(username)

    room = await db.rooms.find_one({"_id": oid})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room["owner_username"] != username:
        raise HTTPException(status_code=403, detail="Only owner can delete room")

    # Delete all messages in the room
    await db.messages.delete_many({"room_id": oid})

    # Delete the room
    await db.rooms.delete_one({"_id": oid})

    return {"message": "Room deleted successfully"}


@router.post("/{room_id}/participants/{participant_username}", response_model=RoomResponse)
async def add_participant(
    room_id: str,
    participant_username: str,
    x_username: str = Header(..., alias="X-Username")
):
    """
    Add a participant to a room.
    Only the room owner can add participants.
    The participant user must exist.
    """
    db = get_database()
    username = x_username.strip()
    participant_username = participant_username.strip()
    oid = validate_object_id(room_id)

    await get_or_create_user(username)

    room = await db.rooms.find_one({"_id": oid})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room["owner_username"] != username:
        raise HTTPException(status_code=403, detail="Only owner can add participants")

    # Check participant exists
    existing = await db.users.find_one({"username": participant_username})
    if not existing:
        raise HTTPException(status_code=400, detail=f"User '{participant_username}' does not exist")

    # Add if not already in
    if participant_username not in room["participant_usernames"]:
        await db.rooms.update_one(
            {"_id": oid},
            {"$push": {"participant_usernames": participant_username}}
        )
        room = await db.rooms.find_one({"_id": oid})

    return room_to_response(room)


@router.delete("/{room_id}/participants/{participant_username}", response_model=RoomResponse)
async def remove_participant(
    room_id: str,
    participant_username: str,
    x_username: str = Header(..., alias="X-Username")
):
    """
    Remove a participant from a room.
    Only the room owner can remove participants.
    Owner cannot be removed.
    """
    db = get_database()
    username = x_username.strip()
    participant_username = participant_username.strip()
    oid = validate_object_id(room_id)

    await get_or_create_user(username)

    room = await db.rooms.find_one({"_id": oid})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room["owner_username"] != username:
        raise HTTPException(status_code=403, detail="Only owner can remove participants")

    if participant_username == room["owner_username"]:
        raise HTTPException(status_code=400, detail="Cannot remove owner from room")

    # Remove if present
    if participant_username in room["participant_usernames"]:
        await db.rooms.update_one(
            {"_id": oid},
            {"$pull": {"participant_usernames": participant_username}}
        )
        room = await db.rooms.find_one({"_id": oid})

    return room_to_response(room)
