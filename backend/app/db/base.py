"""
Base module for SQLAlchemy models.
"""
import uuid
from datetime import datetime

from sqlalchemy import MetaData, Column, DateTime, String, func
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import registry
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

# Define naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Create metadata with naming convention
db_metadata = MetaData(naming_convention=convention)

# Create base model class
Base = declarative_base(metadata=db_metadata)

# Create registry for mappings
mapper_registry = registry(metadata=db_metadata)

class TimestampMixin:
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @declared_attr
    def updated_at(cls):
        return Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class UUIDMixin:
    @declared_attr
    def id(cls):
        return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4) 