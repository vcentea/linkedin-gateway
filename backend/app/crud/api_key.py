"""
CRUD operations for API Keys.
"""
import secrets
import string
from typing import Optional, Tuple, Dict
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
    """
    Get the active API key for a user.
    
    DEPRECATED: This function is kept for backward compatibility but should not be used
    with multi-key support as it will fail with MultipleResultsFound error.
    Use get_primary_api_key_by_user() instead for legacy endpoints.
    """
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == user_id, APIKey.is_active == True)
    )
    return result.scalar_one_or_none()

async def get_primary_api_key_by_user(db: AsyncSession, user_id: UUID) -> Optional[APIKey]:
    """
    Get the primary (most recently used) active API key for a user.
    
    This function is designed for backward compatibility with legacy single-key endpoints.
    When a user has multiple active keys (v1.1.0+), this returns the most recently used one.
    If last_used_at is NULL for all keys, returns the most recently created one.
    
    Args:
        db: Database session
        user_id: User's UUID
        
    Returns:
        APIKey object or None if no active keys exist
    """
    result = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == user_id, APIKey.is_active == True)
        .order_by(
            APIKey.last_used_at.desc().nulls_last(),  # Most recently used first, NULLs last
            APIKey.created_at.desc()  # If last_used_at is NULL, use most recent creation
        )
        .limit(1)
    )
    return result.scalar_one_or_none()

async def get_api_key_by_prefix(db: AsyncSession, prefix: str) -> Optional[APIKey]:
    """Get an API key by its prefix."""
    result = await db.execute(
        select(APIKey).where(APIKey.prefix == prefix)
    )
    return result.scalar_one_or_none()

async def create_api_key(
    db: AsyncSession, 
    user_id: UUID, 
    prefix: str, 
    key_hash: str, 
    name: Optional[str] = None,
    csrf_token: Optional[str] = None,
    linkedin_cookies: Optional[dict] = None,
    # Multi-key support parameters (v1.1.0)
    instance_id: Optional[str] = None,
    instance_name: Optional[str] = None,
    browser_info: Optional[dict] = None
) -> APIKey:
    """
    Creates a new API key for the user.
    
    Multi-key behavior (v1.1.0):
    - If instance_id provided: Creates/updates key for that instance (keeps other keys active)
    - If instance_id NOT provided: Uses legacy single-key behavior (deactivates all others)
    
    Args:
        db: Database session
        user_id: User's UUID
        prefix: Unique key prefix
        key_hash: Hashed full key
        name: Optional custom name
        csrf_token: Optional CSRF token
        linkedin_cookies: Optional LinkedIn cookies
        instance_id: Optional unique instance identifier
        instance_name: Optional user-friendly instance name
        browser_info: Optional browser metadata
        
    Returns:
        Created or updated APIKey object
    """
    if instance_id:
        # Multi-key mode: Check if key exists for this instance
        existing_key = await get_api_key_by_instance(db, user_id, instance_id)
        
        if existing_key:
            # Update existing key for this instance
            existing_key.prefix = prefix
            existing_key.key_hash = key_hash
            existing_key.name = name
            existing_key.csrf_token = csrf_token
            existing_key.linkedin_cookies = linkedin_cookies or {}
            existing_key.instance_name = instance_name
            existing_key.browser_info = browser_info or {}
            existing_key.is_active = True
            db.add(existing_key)
            await db.flush()
            await db.refresh(existing_key)
            return existing_key
        
        # Create new key for this instance (keep other keys active)
        db_api_key = APIKey(
            user_id=user_id,
            prefix=prefix,
            key_hash=key_hash,
            name=name,
            csrf_token=csrf_token,
            linkedin_cookies=linkedin_cookies or {},
            instance_id=instance_id,
            instance_name=instance_name,
            browser_info=browser_info or {},
            is_active=True
        )
    else:
        # Legacy single-key mode: Deactivate all existing keys
        existing_keys = await db.execute(select(APIKey).where(APIKey.user_id == user_id))
        for key in existing_keys.scalars().all():
            key.is_active = False
            db.add(key)
        
        # Create single new key
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
    await db.flush()
    await db.refresh(db_api_key)
    return db_api_key

async def update_csrf_token(db: AsyncSession, user_id: UUID, csrf_token: str) -> Optional[APIKey]:
    """
    Updates the CSRF token for the user's primary (most recently used) API key.
    
    BACKWARD COMPATIBILITY: Uses primary key for legacy single-key endpoints.
    """
    primary_key = await get_primary_api_key_by_user(db=db, user_id=user_id)
    if primary_key:
        primary_key.csrf_token = csrf_token
        db.add(primary_key)
        await db.flush()
        await db.refresh(primary_key)
        return primary_key
    return None

async def get_csrf_token_for_user(db: AsyncSession, user_id: UUID) -> Optional[str]:
    """
    Retrieve the CSRF token for a user's primary (most recently used) API key.
    
    BACKWARD COMPATIBILITY: Uses primary key for legacy behavior.
    
    Args:
        db: Database session
        user_id: The user's UUID
        
    Returns:
        The CSRF token string or None if no active key or no token stored
    """
    primary_key = await get_primary_api_key_by_user(db=db, user_id=user_id)
    return primary_key.csrf_token if primary_key else None

async def update_linkedin_cookies(db: AsyncSession, user_id: UUID, linkedin_cookies: dict) -> Optional[APIKey]:
    """
    Updates LinkedIn cookies for the user's primary (most recently used) API key.
    
    BACKWARD COMPATIBILITY: Uses primary key for legacy single-key endpoints.
    """
    primary_key = await get_primary_api_key_by_user(db=db, user_id=user_id)
    if primary_key:
        primary_key.linkedin_cookies = linkedin_cookies
        db.add(primary_key)
        await db.flush()
        await db.refresh(primary_key)
        return primary_key
    return None

async def get_linkedin_cookies_for_user(db: AsyncSession, user_id: UUID) -> Optional[dict]:
    """
    Retrieve LinkedIn cookies for a user's primary (most recently used) API key.
    
    BACKWARD COMPATIBILITY: Uses primary key for legacy behavior.
    """
    primary_key = await get_primary_api_key_by_user(db=db, user_id=user_id)
    return primary_key.linkedin_cookies if primary_key and primary_key.linkedin_cookies else None

async def deactivate_api_key(db: AsyncSession, user_id: UUID) -> bool:
    """
    Deactivates the current primary (most recently used) API key for a user.
    
    BACKWARD COMPATIBILITY: For legacy single-key deletion endpoint.
    Note: For multi-key support, use deactivate_api_key_by_id() instead.
    """
    primary_key = await get_primary_api_key_by_user(db=db, user_id=user_id)
    if primary_key:
        primary_key.is_active = False
        db.add(primary_key)
        await db.flush() # Ensure the change is persisted before potential commit
        # Commit is handled by the calling transaction
        return True
    return False # No active key found to deactivate 

# ============================================================================
# Multi-key support functions (v1.1.0)
# ============================================================================

async def get_all_api_keys_for_user(
    db: AsyncSession, 
    user_id: UUID,
    include_inactive: bool = False
) -> list[APIKey]:
    """
    Get all API keys for a user.
    
    Args:
        db: Database session
        user_id: User's UUID
        include_inactive: If True, includes deactivated keys
        
    Returns:
        List of APIKey objects sorted by last_used_at DESC (most recently used first)
    """
    query = select(APIKey).where(APIKey.user_id == user_id)
    
    if not include_inactive:
        query = query.where(APIKey.is_active == True)
    
    # Sort by last_used_at DESC, with NULL values last
    query = query.order_by(APIKey.last_used_at.desc().nullslast())
    
    result = await db.execute(query)
    return list(result.scalars().all())

async def get_api_key_by_instance(
    db: AsyncSession,
    user_id: UUID,
    instance_id: str
) -> Optional[APIKey]:
    """
    Get API key for specific user instance.
    
    Args:
        db: Database session
        user_id: User's UUID
        instance_id: Unique instance identifier
        
    Returns:
        APIKey object or None if not found
    """
    result = await db.execute(
        select(APIKey).where(
            APIKey.user_id == user_id,
            APIKey.instance_id == instance_id
        )
    )
    return result.scalar_one_or_none()

async def get_api_key_by_id(
    db: AsyncSession,
    key_id: UUID,
    user_id: Optional[UUID] = None
) -> Optional[APIKey]:
    """
    Get API key by its ID, optionally filtered by user.
    
    Args:
        db: Database session
        key_id: API key UUID
        user_id: Optional user UUID for ownership verification
        
    Returns:
        APIKey object or None if not found
    """
    query = select(APIKey).where(APIKey.id == key_id)
    
    if user_id:
        query = query.where(APIKey.user_id == user_id)
    
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def deactivate_api_key_by_id(
    db: AsyncSession,
    key_id: UUID,
    user_id: UUID
) -> bool:
    """
    Deactivate a specific API key by its ID.
    Verifies the key belongs to the user.
    
    Args:
        db: Database session
        key_id: API key UUID
        user_id: User UUID for ownership verification
        
    Returns:
        True if key was deactivated, False if not found or doesn't belong to user
    """
    api_key = await get_api_key_by_id(db, key_id, user_id)
    
    if api_key:
        api_key.is_active = False
        db.add(api_key)
        await db.flush()
        return True
    
    return False

async def deactivate_api_key_by_instance(
    db: AsyncSession,
    user_id: UUID,
    instance_id: str
) -> bool:
    """
    Deactivate a specific instance's API key.
    Allows selective key deletion while keeping others active.
    
    Args:
        db: Database session
        user_id: User UUID
        instance_id: Instance identifier
        
    Returns:
        True if key was deactivated, False if not found
    """
    api_key = await get_api_key_by_instance(db, user_id, instance_id)
    
    if api_key:
        api_key.is_active = False
        db.add(api_key)
        await db.flush()
        return True
    
    return False

async def update_instance_name(
    db: AsyncSession,
    key_id: UUID,
    user_id: UUID,
    new_name: str
) -> Optional[APIKey]:
    """
    Update the friendly name of an instance.
    Verifies the key belongs to the user.
    
    Args:
        db: Database session
        key_id: API key UUID
        user_id: User UUID for ownership verification
        new_name: New instance name
        
    Returns:
        Updated APIKey or None if not found or doesn't belong to user
    """
    api_key = await get_api_key_by_id(db, key_id, user_id)
    
    if api_key:
        api_key.instance_name = new_name
        db.add(api_key)
        await db.flush()
        await db.refresh(api_key)
        return api_key
    
    return None


# ============================================================================
# Webhook management helpers
# ============================================================================

async def update_webhook_for_key(
    db: AsyncSession,
    key_id: UUID,
    user_id: UUID,
    webhook_url: str,
    webhook_headers: Optional[Dict[str, str]] = None
) -> Optional[APIKey]:
    """
    Update webhook configuration for a specific API key.
    """
    api_key = await get_api_key_by_id(db, key_id, user_id)

    if not api_key:
        return None

    api_key.webhook_url = webhook_url
    api_key.webhook_headers = webhook_headers or {}
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)
    return api_key


async def clear_webhook_for_key(
    db: AsyncSession,
    key_id: UUID,
    user_id: UUID
) -> Optional[APIKey]:
    """
    Remove webhook configuration for a specific API key.
    """
    api_key = await get_api_key_by_id(db, key_id, user_id)

    if not api_key:
        return None

    api_key.webhook_url = None
    api_key.webhook_headers = {}
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)
    return api_key


async def update_webhook_for_primary(
    db: AsyncSession,
    user_id: UUID,
    webhook_url: str,
    webhook_headers: Optional[Dict[str, str]] = None
) -> Optional[APIKey]:
    """
    Update webhook configuration for the user's primary API key (legacy mode).
    """
    primary_key = await get_primary_api_key_by_user(db=db, user_id=user_id)

    if not primary_key:
        return None

    primary_key.webhook_url = webhook_url
    primary_key.webhook_headers = webhook_headers or {}
    db.add(primary_key)
    await db.flush()
    await db.refresh(primary_key)
    return primary_key


async def clear_webhook_for_primary(
    db: AsyncSession,
    user_id: UUID
) -> Optional[APIKey]:
    """
    Remove webhook configuration for the user's primary API key (legacy mode).
    """
    primary_key = await get_primary_api_key_by_user(db=db, user_id=user_id)

    if not primary_key:
        return None

    primary_key.webhook_url = None
    primary_key.webhook_headers = {}
    db.add(primary_key)
    await db.flush()
    await db.refresh(primary_key)
    return primary_key
