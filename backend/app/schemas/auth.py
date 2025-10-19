"""
Authentication schemas for local (email/password) authentication.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class EmailLoginRequest(BaseModel):
    """Request model for email/password login."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")  # Min 1 since validation is client-side


class EmailRegisterRequest(BaseModel):
    """Request model for email/password registration."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")  # Min 1 since validation is client-side
    name: Optional[str] = Field(None, description="User display name")


class AuthResponse(BaseModel):
    """Response model for successful authentication."""
    status: str = Field(default="success", description="Status of the operation")
    accessToken: str = Field(..., description="Access token for authenticated requests")
    id: str = Field(..., description="User ID")
    name: Optional[str] = Field(None, description="User display name")
    email: str = Field(..., description="User email address")
    profile_picture_url: Optional[str] = Field(None, description="Profile picture URL")
    existing_user: bool = Field(..., description="Whether this was an existing user")
    token_expires_at: str = Field(..., description="Token expiration timestamp")


class PasswordResetResponse(BaseModel):
    """Response model for password reset requests."""
    message: str = Field(..., description="Reset instructions message")
    contact: Optional[str] = Field(None, description="Administrator contact email")


class ErrorResponse(BaseModel):
    """Error response model."""
    status: str = Field(default="error", description="Status of the operation")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")

