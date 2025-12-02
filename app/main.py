"""
Main FastAPI application with Socket.IO integration.
Run with: uvicorn app.main:app --reload
"""

import socketio
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import connect_to_mongo, close_mongo_connection
from app.routes import users, rooms, messages
from app.sockets import sio


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - manage MongoDB connection."""
    # Startup
    await connect_to_mongo()
    print("Connected to MongoDB")
    yield
    # Shutdown
    await close_mongo_connection()
    print("Disconnected from MongoDB")


# Create FastAPI app
app = FastAPI(
    title="Chat Room API",
    description="Simple chat backend with FastAPI + Socket.IO + MongoDB",
    version="1.0.0",
    lifespan=lifespan
)

# Include HTTP routers
app.include_router(users.router)
app.include_router(rooms.router)
app.include_router(messages.router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}


# Wrap FastAPI app with Socket.IO ASGI app
# This allows both HTTP and WebSocket traffic on the same server
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# The ASGI app to run is socket_app, but we expose 'app' for the router
# When running with uvicorn, use: uvicorn app.main:socket_app --reload
# Or use 'app' if you want HTTP only (no Socket.IO)

# For convenience, let's make 'app' be the combined ASGI app
app = socket_app
