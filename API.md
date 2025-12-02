# Chat Room API Documentation

Base URL: `http://localhost:8001`

## Authentication

All requests use `X-Username` header for user identification. Users are auto-created on first request.

```
X-Username: your_username
```

---

## HTTP Endpoints

### Users

#### GET /users
Get all users.

**Response:**
```json
[
  {"id": "...", "username": "alice"},
  {"id": "...", "username": "bob"}
]
```

#### GET /users/me
Get current user info (creates user if not exists).

**Headers:** `X-Username: your_username`

**Response:**
```json
{"id": "...", "username": "your_username"}
```

---

### Rooms

#### POST /rooms
Create a new room.

**Headers:** `X-Username: owner_username`

**Body:**
```json
{
  "name": "General",
  "participant_usernames": ["alice", "bob"]  // optional, can be empty
}
```

**Response:**
```json
{
  "id": "...",
  "name": "General",
  "owner_username": "owner_username",
  "participant_usernames": ["owner_username", "alice", "bob"],
  "created_at": "2025-12-02T10:00:00"
}
```

#### GET /rooms/my
Get all rooms where current user is a participant.

**Headers:** `X-Username: your_username`

#### GET /rooms/{room_id}
Get a specific room. User must be a participant.

**Headers:** `X-Username: your_username`

#### PATCH /rooms/{room_id}
Update room name or participants. Owner only.

**Headers:** `X-Username: owner_username`

**Body:**
```json
{
  "name": "New Name",
  "participant_usernames": ["alice", "bob", "charlie"]
}
```

#### DELETE /rooms/{room_id}
Delete room and all its messages. Owner only.

**Headers:** `X-Username: owner_username`

---

### Room Participants

#### POST /rooms/{room_id}/participants/{username}
Add a participant to room. Owner only. User must exist.

**Headers:** `X-Username: owner_username`

#### DELETE /rooms/{room_id}/participants/{username}
Remove a participant from room. Owner only. Cannot remove owner.

**Headers:** `X-Username: owner_username`

---

### Messages

#### GET /rooms/{room_id}/messages
Get messages in a room. User must be a participant.

**Headers:** `X-Username: your_username`

**Query Params:** `limit` (default: 50, max: 200)

**Response:**
```json
[
  {
    "id": "...",
    "room_id": "...",
    "sender_username": "alice",
    "text": "Hello!",
    "created_at": "2025-12-02T10:00:00"
  }
]
```

#### DELETE /rooms/{room_id}/messages/{message_id}
Delete a message. Sender or room owner only.

**Headers:** `X-Username: your_username`

---

## Socket.IO (Real-time)

Connect to: `http://localhost:8001?username=your_username`

### Events to Emit (Client → Server)

#### join_room
Join a room to receive messages.

```json
{"room_id": "..."}
```

#### send_message
Send a message to a room.

```json
{"room_id": "...", "text": "Hello!"}
```

### @AI Feature

Include `@AI` in your message to trigger an AI response. The AI uses Gemini 2.5 Flash and responds in the same room.

**Example:**
```json
{"room_id": "...", "text": "@AI What is the capital of France?"}
```

**Response:** AI will respond as `sender_username: "AI"` with the answer, visible to all room participants.

---

### Events to Listen (Server → Client)

#### joined_room
Received after successfully joining a room.

```json
{"room_id": "..."}
```

#### new_message
Received when any user sends a message to a joined room.

```json
{
  "id": "...",
  "room_id": "...",
  "sender_username": "alice",
  "text": "Hello!",
  "created_at": "2025-12-02T10:00:00.000000"
}
```

#### error
Received on any error.

```json
{"message": "Error description"}
```

---

## Python Client Example

```python
import socketio

sio = socketio.Client()

@sio.on('new_message')
def on_message(data):
    print(f"Message from {data['sender_username']}: {data['text']}")

@sio.on('joined_room')
def on_joined(data):
    print(f"Joined room: {data['room_id']}")

# Connect
sio.connect('http://localhost:8001?username=alice')

# Join room
sio.emit('join_room', {'room_id': 'your_room_id'})

# Send message
sio.emit('send_message', {'room_id': 'your_room_id', 'text': 'Hello!'})
```

---

## JavaScript Client Example

```javascript
const socket = io('http://localhost:8001', {
  query: { username: 'alice' }
});

socket.on('joined_room', (data) => {
  console.log('Joined room:', data.room_id);
});

socket.on('new_message', (data) => {
  console.log(`${data.sender_username}: ${data.text}`);
});

// Join room
socket.emit('join_room', { room_id: 'your_room_id' });

// Send message
socket.emit('send_message', { room_id: 'your_room_id', text: 'Hello!' });
```
