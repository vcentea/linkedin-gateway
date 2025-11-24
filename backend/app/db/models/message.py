"""
LinkedIn Message and Connection Request models.
"""
from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID as PSQL_UUID, JSONB
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin


class MessageHistory(Base, TimestampMixin):
    """
    Message History model for tracking message history.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "message_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False, index=True)
    user_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    message = Column(Text)
    message_type = Column(String(50), index=True)
    timestamp = Column(DateTime, index=True)
    status = Column(String(50), nullable=False, index=True)
    message_metadata = Column(JSONB, default={})

    # Relationships
    profile = relationship("Profile", back_populates="messages")
    user = relationship("User", back_populates="messages")


class ConnectionRequest(Base, TimestampMixin):
    """
    Connection Request model for tracking connection requests.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "connection_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False, index=True)
    connection_message = Column(Text)
    timestamp = Column(DateTime, index=True)
    status = Column(String(50), nullable=False, index=True)
    connection_metadata = Column(JSONB, default={})

    # Relationships
    profile = relationship("Profile", back_populates="connection_requests")
    user = relationship("User", back_populates="connection_requests") 