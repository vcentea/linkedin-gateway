"""
Helper functions for server-side LinkedIn API calls.

Provides common functionality to reduce code duplication
across API endpoints that support server_call mode.
"""
import logging
from typing import Optional, TypeVar, Type
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.crud.api_key import get_csrf_token_for_user, get_linkedin_cookies_for_user
from app.linkedin.services.base import LinkedInServiceBase

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=LinkedInServiceBase)


async def get_linkedin_service(
    db: AsyncSession,
    user_id: UUID,
    service_class: Type[T]
) -> T:
    """
    Get an initialized LinkedIn service instance for server-side calls.
    
    This helper function:
    1. Retrieves the CSRF token from the database
    2. Validates the token exists
    3. Initializes and returns the service instance
    4. Provides consistent logging
    
    Args:
        db: Database session
        user_id: User ID to get CSRF token for
        service_class: The service class to instantiate (e.g., LinkedInFeedService)
        
    Returns:
        Initialized service instance
        
    Raises:
        HTTPException: If no CSRF token is found for the user
    """
    user_id_str = str(user_id)
    
    # Get CSRF token from database
    csrf_token = await get_csrf_token_for_user(db, user_id)
    
    if not csrf_token:
        logger.error(f"[SERVER_CALL] No CSRF token found for user {user_id_str}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No CSRF token found. Please ensure you are logged into LinkedIn in the extension."
        )
    
    # Get LinkedIn cookies from database
    linkedin_cookies = await get_linkedin_cookies_for_user(db, user_id)
    
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

