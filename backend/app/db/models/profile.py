"""
LinkedIn Profile model.
"""
from sqlalchemy import Column, String, Integer, Text, ForeignKey, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID as PSQL_UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin


class Profile(Base, TimestampMixin):
    """
    LinkedIn Profile model for storing profile data.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    linkedin_id = Column(String(255), unique=True, index=True)
    name = Column(String(255))
    jobtitle = Column(String(255))
    about = Column(Text)
    industry = Column(String(255), index=True)
    company = Column(String(255), index=True)
    location = Column(String(255), index=True)
    skills = Column(Text)
    courses = Column(ARRAY(Text))
    certifications = Column(ARRAY(Text))
    department = Column(String(255))
    level = Column(String(255))
    vanity_name = Column(String(255), index=True)
    areasofinterest = Column(Text)
    positions = Column(JSONB)
    education = Column(JSONB)
    languages = Column(JSONB)
    profile_url = Column(Text)
    profile_score = Column(Float)
    full_info_scraped = Column(Boolean, default=False)
    writing_style = Column(Text)
    personality = Column(Text)
    strengths = Column(Text)
    keywords = Column(ARRAY(Text))
    added_by_userid = Column(PSQL_UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    recommendations = Column(ARRAY(Text))
    last_20_posts = Column(ARRAY(Text))
    last_20_comments = Column(ARRAY(Text))
    highlighted_posts = Column(ARRAY(JSONB))
    commentators_list = Column(ARRAY(Text))
    reactors_list = Column(ARRAY(Text))
    profile_metadata = Column(JSONB, default={})

    # Relationships
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    messages = relationship("MessageHistory", back_populates="profile", cascade="all, delete-orphan")
    connection_requests = relationship("ConnectionRequest", back_populates="profile", cascade="all, delete-orphan") 