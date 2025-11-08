from fastapi import APIRouter, Depends, HTTPException, status

from ..db.models.user import User
from ..core.security import get_current_active_user
from .schemas import UserRead # Import the schema

router = APIRouter()

@router.get("/me", response_model=UserRead, tags=["Users"])
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Retrieve the details of the currently authenticated user."""
    # No need for the explicit None check, as the dependency handles it
    # if current_user is None:
    #     raise HTTPException(...)
    return current_user 