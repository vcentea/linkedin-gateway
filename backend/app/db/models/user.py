"""
User model for authentication and user management.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, ForeignKey, TEXT
)
from sqlalchemy.dialects.postgresql import UUID as PSQL_UUID, JSONB
from sqlalchemy.orm import relationship

from ..base import Base, UUIDMixin, TimestampMixin


class User(Base, UUIDMixin, TimestampMixin):
    """
    User model for authentication and user management.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "users"

    # Authentication fields
    linkedin_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, index=True)
    name = Column(String(255))
    profile_picture_url = Column(String)
    
    # Local authentication (email/password)
    password_hash = Column(String(255), nullable=True)  # Only for local users, NULL for LinkedIn OAuth users

    # OAuth tokens
    access_token = Column(String(512))
    refresh_token = Column(String(512))
    token_expires_at = Column(DateTime)

    # Subscription info
    subscription_type = Column(String(100))
    subscription_start = Column(DateTime)
    subscription_end = Column(DateTime)
    billing_tier_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("billing_tiers.id"), index=True)

    # Usage tracking
    last_activity = Column(DateTime, index=True)
    last_login = Column(DateTime)
    api_calls_today = Column(Integer, default=0)
    api_calls_monthly = Column(Integer, default=0)
    last_api_reset = Column(DateTime)

    # Status info
    is_active = Column(Boolean, default=True, index=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)
    role = Column(String(50))

    # Additional data
    user_metadata = Column(JSONB, default={})
    # Cached own LinkedIn fsd_profile ID (to avoid repeated calls)
    my_linkedin_profile_id = Column(String(255), index=True)

    # Relationships
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("UserSubscription", back_populates="user")
    posts = relationship("Post", secondary="user_post_mapping", back_populates="users")
    messages = relationship("MessageHistory", back_populates="user", cascade="all, delete-orphan")
    connection_requests = relationship("ConnectionRequest", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base, UUIDMixin, TimestampMixin):
    """
    User session model for tracking active sessions.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "user_sessions"

    user_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    session_token = Column(TEXT, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    last_activity = Column(DateTime, index=True)
    device_info = Column(JSONB)
    ip_address = Column(String(45))

    # Relationships
    user = relationship("User", back_populates="sessions") 