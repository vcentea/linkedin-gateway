from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime

class UserRead(BaseModel):
    """Schema for reading user details."""
    id: UUID
    email: EmailStr
    name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Add other fields you want to expose, e.g., subscription info
    # subscription_type: Optional[str] = None 

    class Config:
        from_attributes = True 