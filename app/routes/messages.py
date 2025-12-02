"""
Message routes - HTTP endpoints for reading and deleting messages.
Message creation happens via Socket.IO (see sockets.py).
"""

from typing import List

from bson import ObjectId
from fastapi import APIRouter, Header, HTTPException, Query

from app.database import get_database, get_or_create_user
from app.models import MessageResponse, message_to_response

router = APIRouter(prefix="/rooms", tags=["messages"])


def validate_object_id(id_str: str, field_name: str = "ID") -> ObjectId:
    """Validate and convert string to ObjectId."""
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")


@router.get("/{room_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    room_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    x_username: str = Header(..., alias="X-Username")
):
    """
    Get messages in a room.
    User must be a participant to read messages.
    Returns messages sorted by created_at ascending (oldest first).
    """
    db = get_database()
    username = x_username.strip()
    room_oid = validate_object_id(room_id, "room ID")

    await get_or_create_user(username)

    # Check room exists and user is participant
    room = await db.rooms.find_one({"_id": room_oid})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if username not in room["participant_usernames"]:
        raise HTTPException(status_code=403, detail="Not a participant of this room")

    # Fetch messages sorted by time
    messages = await db.messages.find(
        {"room_id": room_oid}
    ).sort("created_at", 1).limit(limit).to_list(length=limit)

    return [message_to_response(msg) for msg in messages]


@router.delete("/{room_id}/messages/{message_id}")
async def delete_message(
    room_id: str,
    message_id: str,
    x_username: str = Header(..., alias="X-Username")
):
    """
    Delete a message.
    Only the message sender or room owner can delete.
    """
    db = get_database()
    username = x_username.strip()
    room_oid = validate_object_id(room_id, "room ID")
    msg_oid = validate_object_id(message_id, "message ID")

    await get_or_create_user(username)

    # Check room exists
    room = await db.rooms.find_one({"_id": room_oid})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Check message exists and belongs to this room
    message = await db.messages.find_one({"_id": msg_oid, "room_id": room_oid})
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Check permission: sender or room owner
    is_sender = message["sender_username"] == username
    is_owner = room["owner_username"] == username

    if not is_sender and not is_owner:
        raise HTTPException(
            status_code=403,
            detail="Only message sender or room owner can delete"
        )

    await db.messages.delete_one({"_id": msg_oid})

    return {"message": "Message deleted successfully"}
