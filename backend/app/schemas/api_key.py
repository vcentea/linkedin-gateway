"""
Pydantic schemas for API Keys.
"""
from typing import Optional, Dict
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

# Schema for displaying key info (prefix only for existing keys)
class APIKeyInfo(BaseModel):
    id: UUID
    prefix: str # Added prefix for identification
    name: Optional[str] = None
    csrf_token: Optional[str] = None
    linkedin_cookies: Optional[Dict[str, str]] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    is_active: bool

    class Config:
        from_attributes = True

# Schema for the response when a key is generated/retrieved
# Inherits from the updated APIKeyInfo
class APIKeyResponse(APIKeyInfo):
    key: Optional[str] = Field(None, description="The full API key. Only returned on creation.")

# Schema for updating CSRF token
class CSRFTokenUpdate(BaseModel):
    csrf_token: str = Field(..., description="The CSRF token to update")

# Schema for updating LinkedIn cookies
class LinkedInCookiesUpdate(BaseModel):
    linkedin_cookies: Dict[str, str] = Field(..., description="All LinkedIn session cookies")
