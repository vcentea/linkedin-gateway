"""
Utilities for caching the authenticated user's LinkedIn profile ID in the database.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


async def get_cached_my_profile_id(db: AsyncSession, user_id: UUID) -> Optional[str]:
    """
    Return cached my_linkedin_profile_id for the user, if present.
    """
    result = await db.execute(select(User.my_linkedin_profile_id).where(User.id == user_id))
    return result.scalar_one_or_none()


async def set_cached_my_profile_id(db: AsyncSession, user_id: UUID, profile_id: str) -> None:
    """
    Persist my_linkedin_profile_id for the user.
    """
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(my_linkedin_profile_id=profile_id)
    )
    await db.commit()


