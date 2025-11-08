"""
Helper functions for server-side LinkedIn API calls.

Provides common functionality to reduce code duplication
across API endpoints that support server_call mode.
"""
import logging
from typing import Optional, TypeVar, Type, Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.db.models.api_key import APIKey
from app.crud.api_key import get_csrf_token_for_user, get_linkedin_cookies_for_user
from app.linkedin.services.base import LinkedInServiceBase

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=LinkedInServiceBase)


async def get_linkedin_service(
    db: AsyncSession,
    api_key_or_user_id: Union[APIKey, UUID],
    service_class: Type[T]
) -> T:
    """
    Get an initialized LinkedIn service instance for server-side calls.
    
    Multi-key support (v1.1.0): Accepts either an APIKey object or UUID for backward compatibility.
    - If APIKey object: Uses CSRF token and cookies from that specific key (multi-key mode)
    - If UUID: Queries database for primary key's credentials (legacy single-key mode)
    
    This helper function:
    1. Retrieves the CSRF token and LinkedIn cookies
    2. Validates the token exists
    3. Initializes and returns the service instance
    4. Provides consistent logging
    
    Args:
        db: Database session
        api_key_or_user_id: Either an APIKey object (multi-key) or user UUID (legacy)
        service_class: The service class to instantiate (e.g., LinkedInFeedService)
        
    Returns:
        Initialized service instance
        
    Raises:
        HTTPException: If no CSRF token is found
    """
    # Multi-key mode vs legacy mode detection
    if isinstance(api_key_or_user_id, APIKey):
        # ✅ Multi-key mode: Extract credentials directly from the API key object
        # This ensures we use the correct CSRF/cookies for the specific browser that made the request
        api_key = api_key_or_user_id
        csrf_token = api_key.csrf_token
        linkedin_cookies = api_key.linkedin_cookies
        user_id_str = str(api_key.user_id)
        
        logger.info(f"[SERVER_CALL][MULTI-KEY] Using credentials from API key {api_key.id} (prefix: {api_key.prefix})")
        logger.info(f"[SERVER_CALL][MULTI-KEY] Instance: {api_key.instance_name or api_key.instance_id or 'N/A'}")
    else:
        # ✅ Legacy mode: Query database for primary key's credentials (backward compatibility)
        user_id = api_key_or_user_id
        user_id_str = str(user_id)
        csrf_token = await get_csrf_token_for_user(db, user_id)
        linkedin_cookies = await get_linkedin_cookies_for_user(db, user_id)
        
        logger.info(f"[SERVER_CALL][LEGACY] Using primary key credentials for user {user_id_str}")
    
    # Validate CSRF token exists
    if not csrf_token:
        logger.error(f"[SERVER_CALL] No CSRF token found for user {user_id_str}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No CSRF token found. Please ensure you are logged into LinkedIn in the extension."
        )
    
    # Log token and cookies details for debugging
    logger.info(f"[SERVER_CALL] Retrieved CSRF token for user {user_id_str}")
    logger.info(f"[SERVER_CALL] CSRF token value: {csrf_token[:20]}... (length: {len(csrf_token)})")
    has_quotes = csrf_token.startswith('"') or csrf_token.endswith('"')
    logger.info(f"[SERVER_CALL] CSRF token has quotes: {has_quotes}")
    
    if linkedin_cookies:
        logger.info(f"[SERVER_CALL] Retrieved {len(linkedin_cookies)} LinkedIn cookies")
        logger.debug(f"[SERVER_CALL] Cookie names: {', '.join(linkedin_cookies.keys())}")
    else:
        logger.warning(f"[SERVER_CALL] No LinkedIn cookies found - using CSRF token only (may fail)")
    
    # Initialize and return service with cookies
    service = service_class(csrf_token, linkedin_cookies)
    logger.info(f"[SERVER_CALL] Initialized {service_class.__name__} for user {user_id_str}")
    
    return service

