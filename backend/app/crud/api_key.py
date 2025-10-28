"""
CRUD operations for API Keys.
"""
import secrets
import string
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.db.models.api_key import APIKey
from app.core.security import get_password_hash # Reusing password hashing

# Constants for API Key Generation
API_KEY_PREFIX = "LKG_" # Standard prefix for visual identification
API_KEY_PREFIX_LENGTH = 16 # Length of the unique, queryable prefix
API_KEY_SECRET_LENGTH = 32 # Length of the secret part
PREFIX_CHARSET = string.ascii_letters + string.digits # Characters allowed in the prefix

def generate_api_key() -> Tuple[str, str, str]:
    """Generates a secure API key components.

    Returns:
        Tuple[str, str, str]: A tuple containing:
            - prefix: The 16-character unique prefix.
            - secret_part: The 32-character secret token.
            - full_key_string: The complete key string (e.g., LKG_prefix_secret).
    """
    prefix = ''.join(secrets.choice(PREFIX_CHARSET) for _ in range(API_KEY_PREFIX_LENGTH))
    secret_part = secrets.token_urlsafe(API_KEY_SECRET_LENGTH)
    full_key_string = f"{API_KEY_PREFIX}{prefix}_{secret_part}"
    return prefix, secret_part, full_key_string

async def get_active_api_key_by_user(db: AsyncSession, user_id: UUID) -> Optional[APIKey]:
    """Get the active API key for a user."""
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == user_id, APIKey.is_active == True)
    )
    return result.scalar_one_or_none()

async def get_api_key_by_prefix(db: AsyncSession, prefix: str) -> Optional[APIKey]:
    """Get an API key by its prefix."""
    result = await db.execute(
        select(APIKey).where(APIKey.prefix == prefix)
    )
    return result.scalar_one_or_none()

async def create_api_key(db: AsyncSession, user_id: UUID, prefix: str, key_hash: str, name: Optional[str] = None, csrf_token: Optional[str] = None, linkedin_cookies: Optional[dict] = None) -> APIKey:
    """Creates and stores a new API key."""
    # Deactivate existing keys for the user first (optional, but good practice)
    existing_keys = await db.execute(select(APIKey).where(APIKey.user_id == user_id))
    for key in existing_keys.scalars().all():
        key.is_active = False
        db.add(key)
    
    db_api_key = APIKey(
        user_id=user_id,
        prefix=prefix,
        key_hash=key_hash,
        name=name,
        csrf_token=csrf_token,
        linkedin_cookies=linkedin_cookies or {},
        is_active=True
    )
    db.add(db_api_key)
    await db.flush()  # Flush to get ID etc. before potential commit
    await db.refresh(db_api_key)
    # Commit is handled by the calling transaction
    return db_api_key

async def update_csrf_token(db: AsyncSession, user_id: UUID, csrf_token: str) -> Optional[APIKey]:
    """Updates the CSRF token for the user's active API key."""
    active_key = await get_active_api_key_by_user(db=db, user_id=user_id)
    if active_key:
        active_key.csrf_token = csrf_token
        db.add(active_key)
        await db.flush()
        await db.refresh(active_key)
        return active_key
    return None

async def get_csrf_token_for_user(db: AsyncSession, user_id: UUID) -> Optional[str]:
    """
    Retrieve the CSRF token for a user's active API key.
    
    Args:
        db: Database session
        user_id: The user's UUID
        
    Returns:
        The CSRF token string or None if no active key or no token stored
    """
    active_key = await get_active_api_key_by_user(db=db, user_id=user_id)
    return active_key.csrf_token if active_key else None

async def update_linkedin_cookies(db: AsyncSession, user_id: UUID, linkedin_cookies: dict) -> Optional[APIKey]:
    """Updates LinkedIn cookies for the user's active API key."""
    active_key = await get_active_api_key_by_user(db=db, user_id=user_id)
    if active_key:
        active_key.linkedin_cookies = linkedin_cookies
        db.add(active_key)
        await db.flush()
        await db.refresh(active_key)
        return active_key
    return None

async def get_linkedin_cookies_for_user(db: AsyncSession, user_id: UUID) -> Optional[dict]:
    """
    Retrieve LinkedIn cookies for a user's active API key.
    """
    active_key = await get_active_api_key_by_user(db=db, user_id=user_id)
    return active_key.linkedin_cookies if active_key and active_key.linkedin_cookies else None

async def deactivate_api_key(db: AsyncSession, user_id: UUID) -> bool:
    """Deactivates the current active API key for a user."""
    active_key = await get_active_api_key_by_user(db=db, user_id=user_id)
    if active_key:
        active_key.is_active = False
        db.add(active_key)
        await db.flush() # Ensure the change is persisted before potential commit
        # Commit is handled by the calling transaction
        return True
    return False # No active key found to deactivate 