"""
API Key model for external API access management.
"""
from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID as PSQL_UUID, JSONB
from sqlalchemy.orm import relationship

from ..base import Base, UUIDMixin, TimestampMixin


class APIKey(Base, UUIDMixin, TimestampMixin):
    """
    API Key model for external API access.
    Based on structure from DATABASE_STRUCTURE.md
    
    Multi-key support (v1.1.0):
    - instance_id: Unique identifier for extension instance
    - instance_name: User-friendly name for the instance
    - browser_info: JSON metadata about the browser
    """
    __tablename__ = "api_keys"

    user_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    prefix = Column(String(16), unique=True, nullable=False, index=True)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    description = Column(String)
    csrf_token = Column(String(255))
    linkedin_cookies = Column(JSONB, default={})
    last_used_at = Column(DateTime)
    is_active = Column(Boolean, default=True, index=True)
    rate_limit_config = Column(JSONB, default={})
    permissions = Column(JSONB, default={})
    api_metadata = Column(JSONB, default={})
    webhook_url = Column(String(1024), nullable=True)
    webhook_headers = Column(JSONB, default={}, nullable=False)
    
    # Multi-key support fields (v1.1.0)
    instance_id = Column(String(255), nullable=True, index=True)
    instance_name = Column(String(255), nullable=True)
    browser_info = Column(JSONB, default={})

    # Relationships
    user = relationship("User", back_populates="api_keys")
    rate_limits = relationship("RateLimit", back_populates="api_key", cascade="all, delete-orphan")
    usage_logs = relationship("APIUsageLog", back_populates="api_key", cascade="all, delete-orphan")


class RateLimit(Base, UUIDMixin, TimestampMixin):
    """
    Rate Limit model for API rate limiting.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "rate_limits"

    api_key_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False, index=True)
    endpoint = Column(String(255), nullable=False, index=True)
    max_requests = Column(String(255), nullable=False)
    time_window = Column(String(255), nullable=False)  # Time window in seconds
    current_requests = Column(String(255), default=0)
    last_reset = Column(DateTime, index=True)
    rate_limit_metadata = Column(JSONB, default={})

    # Relationships
    api_key = relationship("APIKey", back_populates="rate_limits")


class APIUsageLog(Base, UUIDMixin, TimestampMixin):
    """
    API Usage Log model for tracking API usage.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "api_usage_logs"

    api_key_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False, index=True)
    user_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    status_code = Column(String(255), index=True)
    response_time = Column(String(255))
    request_metadata = Column(JSONB, default={})
    response_metadata = Column(JSONB, default={})

    # Relationships
    api_key = relationship("APIKey", back_populates="usage_logs") 
