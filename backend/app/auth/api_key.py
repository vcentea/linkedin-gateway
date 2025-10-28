"""
Shared API key validation utilities.
"""
import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import api_key as api_key_crud
from app.core import security
from app.crud.api_key import API_KEY_PREFIX, API_KEY_PREFIX_LENGTH

logger = logging.getLogger(__name__)

async def validate_api_key_string(api_key_string: str, db: AsyncSession) -> UUID:
    """
    Validates an API key string (prefix + secret).
    
    Args:
        api_key_string: The full API key string (LKG_prefix_secret)
        db: Database session

    Raises:
        HTTPException: If validation fails
        
    Returns:
        UUID: The user_id on success
    """
    if not api_key_string:
        logger.warning("API key validation failed: Empty key string provided.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key is missing or empty")

    if not api_key_string.startswith(API_KEY_PREFIX) or '_' not in api_key_string[len(API_KEY_PREFIX):]:
        logger.warning(f"API key validation failed: Invalid format for key starting with '{api_key_string[:20]}...'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key format")

    try:
        prefix_plus_secret = api_key_string[len(API_KEY_PREFIX):]
        prefix, secret_part = prefix_plus_secret.split('_', 1)
        
        if len(prefix) != API_KEY_PREFIX_LENGTH:
            logger.warning(f"API key validation failed: Incorrect prefix length for key starting with '{api_key_string[:20]}...'")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key format (prefix length)")

    except ValueError:
        logger.warning(f"API key validation failed: Value error parsing key starting with '{api_key_string[:20]}...'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key format (parsing error)")

    db_api_key = await api_key_crud.get_api_key_by_prefix(db, prefix=prefix)

    if not db_api_key:
        logger.warning(f"API key validation failed: No key found for prefix '{prefix}'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

    if not db_api_key.is_active:
        logger.warning(f"API key authentication failed: Key with prefix '{prefix}' is inactive for user {db_api_key.user_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key is inactive")

    if not security.verify_password(secret_part, db_api_key.key_hash):
        logger.warning(f"API key authentication failed: Invalid secret for prefix '{prefix}' (user {db_api_key.user_id})")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

    logger.info(f"API key validation successful for prefix '{prefix}', user ID: {db_api_key.user_id}")
    return db_api_key.user_id 