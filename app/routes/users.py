"""
User routes - simple endpoint to get current user info.
Authentication is just X-Username header, auto-creates users.
"""

from typing import List

from fastapi import APIRouter, Header, HTTPException

from app.database import get_database, get_or_create_user
from app.models import UserResponse, user_to_response

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[UserResponse])
async def get_users():
    """
    Get all users in the system.
    """
    db = get_database()
    users = await db.users.find().to_list(length=1000)
    return [user_to_response(user) for user in users]


@router.get("/me", response_model=UserResponse)
async def get_me(x_username: str = Header(..., alias="X-Username")):
    """
    Get the current user's info.
    Creates the user if they don't exist yet.
    """
    if not x_username or not x_username.strip():
        raise HTTPException(status_code=400, detail="Username cannot be empty")

    user = await get_or_create_user(x_username.strip())
    return user_to_response(user)
