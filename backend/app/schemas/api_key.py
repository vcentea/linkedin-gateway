"""
Pydantic schemas for API Keys.
"""
import re
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, AnyHttpUrl, field_validator
from uuid import UUID
from datetime import datetime

# Schema for displaying key info (prefix only for existing keys)
class APIKeyInfo(BaseModel):
    id: UUID
    prefix: str # Added prefix for identification
    name: Optional[str] = None
    csrf_token: Optional[str] = None
    linkedin_cookies: Optional[Dict[str, str]] = None
    # Multi-key support fields (v1.1.0)
    instance_id: Optional[str] = Field(None, description="Unique instance identifier (e.g., chrome_1699123456789_a9b8c7d6)")
    instance_name: Optional[str] = Field(None, description="User-friendly instance name (e.g., 'Chrome - Windows')")
    browser_info: Optional[Dict[str, Any]] = Field(None, description="Browser metadata: {browser, version, os, platform}")
    webhook_url: Optional[AnyHttpUrl] = Field(None, description="Optional webhook URL triggered for this API key")
    webhook_headers: Optional[Dict[str, str]] = Field(None, description="Optional headers sent with webhook requests")
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

# Schema for generating a new API key (v1.1.0)
class APIKeyGenerateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Optional custom name for the API key")
    # Multi-key support fields
    instance_id: Optional[str] = Field(None, description="Unique instance identifier from extension")
    instance_name: Optional[str] = Field(None, description="User-friendly instance name")
    browser_info: Optional[Dict[str, Any]] = Field(None, description="Browser metadata")
    # Credentials (can be provided during generation)
    csrf_token: Optional[str] = Field(None, description="LinkedIn CSRF token for this key")
    linkedin_cookies: Optional[Dict[str, str]] = Field(None, description="LinkedIn session cookies for this key")

# Schema for listing API keys (v1.1.0)
class APIKeyListResponse(BaseModel):
    keys: List[APIKeyInfo] = Field(..., description="List of API keys for the user")
    total: int = Field(..., description="Total number of keys")
    active_count: int = Field(..., description="Number of active keys")

# Schema for updating instance name (v1.1.0)
class InstanceNameUpdate(BaseModel):
    instance_name: str = Field(..., description="New user-friendly name for the instance")


class WebhookConfigUpdate(BaseModel):
    webhook_url: AnyHttpUrl = Field(..., description="Destination URL for webhook notifications")
    webhook_headers: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Optional HTTP headers to include when invoking the webhook"
    )

    @field_validator('webhook_headers')
    @classmethod
    def validate_headers(cls, headers: Optional[Dict[str, str]]):
        if headers is None:
            return {}

        cleaned_headers: Dict[str, str] = {}
        for raw_name, raw_value in headers.items():
            name = (raw_name or '').strip()
            value = (raw_value or '').strip()

            if not name:
                raise ValueError("Header names cannot be empty.")
            if len(name) > 128:
                raise ValueError(f"Header name '{name}' exceeds 128 characters.")
            if not re.match(r"^[A-Za-z0-9-]+$", name):
                raise ValueError(
                    f"Header name '{name}' may only contain letters, numbers, and hyphens."
                )
            if len(value) > 1024:
                raise ValueError(f"Header value for '{name}' exceeds 1024 characters.")

            cleaned_headers[name] = value

        return cleaned_headers
