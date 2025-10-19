"""
Post model for LinkedIn posts.
"""
from sqlalchemy import Column, String, Integer, Text, ForeignKey, Table, DateTime
from sqlalchemy.dialects.postgresql import UUID as PSQL_UUID, JSONB
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin, db_metadata


# User-Post mapping table
user_post_mapping = Table(
    "user_post_mapping",
    db_metadata,
    Column("user_id", PSQL_UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("post_id", Integer, ForeignKey("posts.id"), primary_key=True),
    Column("timestamp", DateTime),
    Column("relevance_score", Integer),
    Column("relevance_data", JSONB)
)


class Post(Base, TimestampMixin):
    """
    LinkedIn Post model for storing post data.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    postid = Column(String(255), unique=True, index=True)
    ugcpostid = Column(String(255))
    url = Column(Text)
    snippet = Column(Text)
    author_id = Column(Integer, ForeignKey("profiles.id"), nullable=False, index=True)
    reactions = Column(Integer, index=True)
    comments = Column(Integer, index=True)
    reposts = Column(Integer)
    engagement = Column(Integer, index=True)
    postcontent = Column(Text)
    timestamp = Column(DateTime, index=True)
    shareurn = Column(String(255))
    post_metadata = Column(JSONB, default={})

    # Relationships
    author = relationship("Profile", back_populates="posts")
    users = relationship("User", secondary=user_post_mapping, back_populates="posts") 