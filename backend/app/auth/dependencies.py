"""
Authentication dependencies for FastAPI.
"""
from fastapi import Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Union
from datetime import datetime, timezone
from uuid import UUID
import logging

from app.db.session import get_db
from app.db.models.user import User, UserSession
from app.db.models.api_key import APIKey
from app.crud import api_key as api_key_crud
from app.core import security
from app.crud.api_key import API_KEY_PREFIX, API_KEY_PREFIX_LENGTH

# Configure logging
logger = logging.getLogger(__name__)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/token",
    # Make token optional for certain endpoints that don't require authentication
    auto_error=False
)

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Validate the access token and return the current user.
    Uses the session token stored in the UserSession table.
    
    Args:
        token: The JWT access token
        db: Database session
        
    Returns:
        User: The current authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # If no token is provided, raise exception
    if not token:
        raise credentials_exception
    
    try:
        # Get current time in UTC without timezone info
        current_time = datetime.utcnow()
        
        # Find the session with this token that hasn't expired
        result = await db.execute(
            select(UserSession).where(
                UserSession.session_token == token,
                UserSession.expires_at > current_time
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            raise credentials_exception
            
        # Update last activity time
        session.last_activity = current_time
        # We don't necessarily need to await commit here, depends on transaction management
        # await db.commit()
            
        # Get the user associated with this session
        result = await db.execute(
            select(User).where(User.id == session.user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise credentials_exception
            
        return user
        
    except Exception as e:
        # Use logger for errors
        logger.exception(f"Error authenticating user via session token: {e}")
        raise credentials_exception


async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Similar to get_current_user but returns None instead of raising an exception
    if no valid token is provided.
    
    Args:
        token: The JWT access token
        db: Database session
        
    Returns:
        Optional[User]: The current authenticated user or None
    """
    if not token:
        return None
        
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Validate that the current user is an admin.
    
    Args:
        current_user: The current authenticated user
        
    Returns:
        User: The current admin user
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user 


# --- API Key Authentication Dependency ---

API_KEY_HEADER_NAME = "X-API-Key"
api_key_header_scheme = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)

async def get_requesting_user_from_api_key(
    api_key_header: Optional[str] = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db)
) -> APIKey:
    """
    Validates an API key provided in the X-API-Key header.

    Multi-key support (v1.1.0): Returns the full APIKey object instead of just user_id.
    This allows endpoints to access CSRF token and cookies specific to the key that
    authenticated the request.

    - Extracts prefix and secret from the key.
    - Finds the key record by prefix.
    - Verifies the secret part against the stored hash.
    - Returns the validated API key object.

    Raises:
        HTTPException 403: If header is missing or format is invalid.
        HTTPException 401: If key is invalid, inactive, or verification fails.
    """
    if not api_key_header:
        logger.warning("API key authentication failed: Missing X-API-Key header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated: Missing API Key header"
        )

    # Expected format: LKG_prefix_secret
    if not api_key_header.startswith(API_KEY_PREFIX) or '_' not in api_key_header[len(API_KEY_PREFIX):]:
        logger.warning(f"API key authentication failed: Invalid format for key starting with '{api_key_header[:20]}...'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key format"
        )

    try:
        prefix_plus_secret = api_key_header[len(API_KEY_PREFIX):]
        prefix, secret_part = prefix_plus_secret.split('_', 1)
        
        if len(prefix) != API_KEY_PREFIX_LENGTH:
             logger.warning(f"API key authentication failed: Incorrect prefix length for key starting with '{api_key_header[:20]}...'")
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key format (prefix length)")

    except ValueError:
        logger.warning(f"API key authentication failed: Value error parsing key starting with '{api_key_header[:20]}...'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key format (parsing error)"
        )

    # Find the key by prefix
    db_api_key = await api_key_crud.get_api_key_by_prefix(db, prefix=prefix)

    if not db_api_key:
        logger.warning(f"API key authentication failed: No key found for prefix '{prefix}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    if not db_api_key.is_active:
        logger.warning(f"API key authentication failed: Key with prefix '{prefix}' is inactive for user {db_api_key.user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is inactive"
        )

    # Verify the secret part
    if not security.verify_password(secret_part, db_api_key.key_hash):
        logger.warning(f"API key authentication failed: Invalid secret for prefix '{prefix}' (user {db_api_key.user_id})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    # Update last_used_at timestamp (v1.1.0)
    db_api_key.last_used_at = datetime.utcnow()
    db.add(db_api_key)
    await db.flush()

    logger.info(f"API key authentication successful for prefix '{prefix}', user ID: {db_api_key.user_id}")
    # Return full APIKey object (v1.1.0) - contains CSRF token and cookies for this specific key
    return db_api_key


async def validate_api_key_from_header_or_body(
    api_key_from_body: Optional[str] = None,
    api_key_header: Optional[str] = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db)
) -> APIKey:
    """
    Validates an API key from either X-API-Key header OR request body.
    Header takes precedence over body.
    
    Multi-key support (v1.1.0): Returns the full APIKey object instead of just user_id.
    This allows endpoints to access CSRF token and cookies specific to the key that
    authenticated the request.
    
    Args:
        api_key_from_body: API key from request body (optional)
        api_key_header: API key from X-API-Key header (optional)
        db: Database session
        
    Returns:
        APIKey: The validated API key object with all credentials
        
    Raises:
        HTTPException 403: If neither header nor body contains a valid API key
        HTTPException 401: If key is invalid, inactive, or verification fails
    """
    # Check header first (takes precedence)
    api_key_to_validate = api_key_header if api_key_header else api_key_from_body
    
    if not api_key_to_validate:
        logger.warning("API key authentication failed: No API key provided in header or body")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated: API Key required (provide via X-API-Key header or request body)"
        )
    
    # Log which source was used
    source = "header (X-API-Key)" if api_key_header else "request body (api_key)"
    logger.info(f"✓ API key received from {source}, validating...")
    
    # Expected format: LKG_prefix_secret
    if not api_key_to_validate.startswith(API_KEY_PREFIX) or '_' not in api_key_to_validate[len(API_KEY_PREFIX):]:
        logger.warning(f"API key authentication failed: Invalid format for key from {source}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key format"
        )
    
    try:
        prefix_plus_secret = api_key_to_validate[len(API_KEY_PREFIX):]
        prefix, secret_part = prefix_plus_secret.split('_', 1)
        
        if len(prefix) != API_KEY_PREFIX_LENGTH:
            logger.warning(f"API key authentication failed: Incorrect prefix length from {source}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key format (prefix length)")
    
    except ValueError:
        logger.warning(f"API key authentication failed: Value error parsing key from {source}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key format (parsing error)"
        )
    
    # Find the key by prefix
    db_api_key = await api_key_crud.get_api_key_by_prefix(db, prefix=prefix)
    
    if not db_api_key:
        logger.warning(f"API key authentication failed: No key found for prefix '{prefix}' from {source}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    
    if not db_api_key.is_active:
        logger.warning(f"API key authentication failed: Key with prefix '{prefix}' is inactive (from {source})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is inactive"
        )
    
    # Verify the secret part
    if not security.verify_password(secret_part, db_api_key.key_hash):
        logger.warning(f"API key authentication failed: Invalid secret for prefix '{prefix}' from {source}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    
    # Update last_used_at timestamp (v1.1.0)
    db_api_key.last_used_at = datetime.utcnow()
    db.add(db_api_key)
    await db.flush()
    
    logger.info(f"API key authentication successful for prefix '{prefix}' from {source}, user ID: {db_api_key.user_id}")
    # Return full APIKey object (v1.1.0) - contains CSRF token and cookies for this specific key
    return db_api_key


def get_api_key_validator(request_body_field: str = "api_key"):
    """
    Factory function to create an API key validator dependency for a specific request schema.
    
    Multi-key support (v1.1.0): Returns APIKey object instead of UUID.
    
    Args:
        request_body_field: The field name in the request body containing the API key (default: "api_key")
        
    Returns:
        A dependency function that validates API key from header or body
    """
    async def validate_key(
        request_body: dict = Body(...),
        api_key_header: Optional[str] = Depends(api_key_header_scheme),
        db: AsyncSession = Depends(get_db)
    ) -> APIKey:
        api_key_from_body = request_body.get(request_body_field) if isinstance(request_body, dict) else getattr(request_body, request_body_field, None)
        return await validate_api_key_from_header_or_body(
            api_key_from_body=api_key_from_body,
            api_key_header=api_key_header,
            db=db
        )
    
    return validate_key 