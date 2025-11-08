"""
Billing models for subscription management.
"""
from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID as PSQL_UUID, JSONB
from sqlalchemy.orm import relationship

from ..base import Base, UUIDMixin, TimestampMixin


class BillingTier(Base, UUIDMixin, TimestampMixin):
    """
    Billing Tier model for subscription levels.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "billing_tiers"

    name = Column(String(255), nullable=False)
    description = Column(String)
    monthly_price = Column(Numeric(10, 2), index=True)
    api_calls_limit = Column(String(255))
    features = Column(JSONB, default={})
    is_active = Column(Boolean, default=True, index=True)
    tier_metadata = Column(JSONB, default={})

    # Relationships
    users = relationship("User", backref="billing_tier")
    subscriptions = relationship("UserSubscription", back_populates="billing_tier")


class UserSubscription(Base, UUIDMixin, TimestampMixin):
    """
    User Subscription model for tracking subscriptions.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "user_subscriptions"

    user_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    billing_tier_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("billing_tiers.id"), nullable=False, index=True)
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)
    payment_method_id = Column(String(255))
    auto_renew = Column(Boolean, default=True)
    subscription_metadata = Column(JSONB, default={})

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    billing_tier = relationship("BillingTier", back_populates="subscriptions")
    billing_history = relationship("BillingHistory", back_populates="subscription", cascade="all, delete-orphan")


class BillingHistory(Base, UUIDMixin, TimestampMixin):
    """
    Billing History model for tracking transactions.
    Based on structure from DATABASE_STRUCTURE.md
    """
    __tablename__ = "billing_history"

    user_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    subscription_id = Column(PSQL_UUID(as_uuid=True), ForeignKey("user_subscriptions.id"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String(50), nullable=False, index=True)
    payment_method = Column(String(50))
    transaction_id = Column(String(255), index=True)
    billing_metadata = Column(JSONB, default={})

    # Relationships
    subscription = relationship("UserSubscription", back_populates="billing_history") 