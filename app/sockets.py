"""
Socket.IO event handlers for real-time messaging.
Handles: connect, disconnect, join_room, send_message
"""

import json
import os
import re
from datetime import datetime
from urllib.parse import parse_qs

import google.generativeai as genai
import socketio
from bson import ObjectId
from dotenv import load_dotenv

from app.database import get_database, get_or_create_user

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel("gemini-2.5-flash")


async def get_ai_response(room_name: str, user_message: str) -> str:
    """Call Gemini to get AI response."""
    # Remove @AI from the message
    query = re.sub(r'@AI\s*', '', user_message, flags=re.IGNORECASE).strip()

    prompt = f"""You are a helpful AI assistant in a chat room called "{room_name}".
A user is asking: {query}

Give a concise, helpful response. Keep it brief and to the point."""

    try:
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return "Sorry, I couldn't process that request."


# Create Socket.IO server (async mode for use with FastAPI/ASGI)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"  # For development; tighten in production
)

# In-memory mapping of socket session ID to username
sid_to_username: dict[str, str] = {}


def get_username_from_query(environ: dict) -> str | None:
    """Extract username from Socket.IO connection query string."""
    query_string = environ.get("QUERY_STRING", "")
    params = parse_qs(query_string)
    usernames = params.get("username", [])
    if usernames:
        return usernames[0].strip()
    return None


@sio.event
async def connect(sid, environ, auth=None):
    """
    Handle new Socket.IO connection.
    Expects username in query params: ?username=teja
    """
    username = get_username_from_query(environ)

    if not username:
        # Reject connection if no username provided
        print(f"Connection rejected for {sid}: no username")
        return False

    # Get or create user in database
    await get_or_create_user(username)

    # Store mapping
    sid_to_username[sid] = username
    print(f"User '{username}' connected with sid {sid}")

    return True


@sio.event
async def disconnect(sid):
    """Handle Socket.IO disconnection."""
    username = sid_to_username.pop(sid, None)
    print(f"User '{username}' disconnected (sid {sid})")


@sio.event
async def join_room(sid, data):
    """
    Join a chat room.
    Payload: {"room_id": "..."}
    User must be a participant of the room.
    """

    # Parse JSON string to dict
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {}

    room_id = data.get("room_id") if isinstance(data, dict) else None

    db = get_database()
    username = sid_to_username.get(sid)

    if not username:
        await sio.emit("error", {"message": "Not authenticated"}, to=sid)
        return
    if not room_id:
        await sio.emit("error", {"message": "room_id is required"}, to=sid)
        return

    try:
        room_oid = ObjectId(room_id)
    except Exception:
        await sio.emit("error", {"message": "Invalid room_id format"}, to=sid)
        return

    # Check room exists and user is participant
    room = await db.rooms.find_one({"_id": room_oid})
    if not room:
        await sio.emit("error", {"message": "Room not found"}, to=sid)
        return

    if username not in room["participant_usernames"]:
        await sio.emit("error", {"message": "Not a participant of this room"}, to=sid)
        return

    # Join the Socket.IO room
    await sio.enter_room(sid, room_id)
    print(f"User '{username}' joined room {room_id}")

    # Notify the user they successfully joined
    await sio.emit("joined_room", {"room_id": room_id}, to=sid)


@sio.event
async def leave_room(sid, data):
    """
    Leave a chat room.
    Payload: {"room_id": "..."}
    """
    # Parse JSON string to dict
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {}

    room_id = data.get("room_id") if isinstance(data, dict) else None
    username = sid_to_username.get(sid)

    if not username:
        await sio.emit("error", {"message": "Not authenticated"}, to=sid)
        return
    if not room_id:
        await sio.emit("error", {"message": "room_id is required"}, to=sid)
        return

    # Leave the Socket.IO room
    await sio.leave_room(sid, room_id)
    print(f"User '{username}' left room {room_id}")

    # Notify the user they successfully left
    await sio.emit("left_room", {"room_id": room_id}, to=sid)


@sio.event
async def send_message(sid, data):
    """
    Send a message to a room.
    Payload: '{"room_id": "...", "text": "..."}' as JSON string OR dict
    Creates message in DB and broadcasts to all room participants.
    """
    # Parse JSON string to dict
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {}

    room_id = data.get("room_id") if isinstance(data, dict) else None
    text = (data.get("text", "") if isinstance(data, dict) else "").strip()

    db = get_database()
    username = sid_to_username.get(sid)

    if not username:
        await sio.emit("error", {"message": "Not authenticated"}, to=sid)
        return

    if not room_id:
        await sio.emit("error", {"message": "room_id is required"}, to=sid)
        return

    if not text:
        await sio.emit("error", {"message": "text cannot be empty"}, to=sid)
        return

    try:
        room_oid = ObjectId(room_id)
    except Exception:
        await sio.emit("error", {"message": "Invalid room_id format"}, to=sid)
        return

    # Check room exists and user is participant
    room = await db.rooms.find_one({"_id": room_oid})
    if not room:
        await sio.emit("error", {"message": "Room not found"}, to=sid)
        return

    if username not in room["participant_usernames"]:
        await sio.emit("error", {"message": "Not a participant of this room"}, to=sid)
        return

    # Create message document
    now = datetime.utcnow()
    message_doc = {
        "room_id": room_oid,
        "sender_username": username,
        "text": text,
        "created_at": now
    }

    result = await db.messages.insert_one(message_doc)

    # Prepare response message (with string IDs for JSON serialization)
    message_response = {
        "id": str(result.inserted_id),
        "room_id": room_id,
        "sender_username": username,
        "text": text,
        "created_at": now.isoformat()
    }

    # Broadcast to all users in the room
    await sio.emit("new_message", message_response, room=room_id)
    print(f"Message from '{username}' in room {room_id}: {text[:50]}...")

    # Check if message contains @AI - trigger AI response
    if "@ai" in text.lower():
        room_name = room["name"]
        ai_response_text = await get_ai_response(room_name, text)

        # Save AI message to database
        ai_now = datetime.utcnow()
        ai_message_doc = {
            "room_id": room_oid,
            "sender_username": "AI",
            "text": ai_response_text,
            "created_at": ai_now
        }
        ai_result = await db.messages.insert_one(ai_message_doc)

        # Broadcast AI response to room
        ai_message_response = {
            "id": str(ai_result.inserted_id),
            "room_id": room_id,
            "sender_username": "AI",
            "text": ai_response_text,
            "created_at": ai_now.isoformat()
        }
        await sio.emit("new_message", ai_message_response, room=room_id)
        print(f"AI responded in room {room_id}")
