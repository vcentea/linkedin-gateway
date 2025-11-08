"""
API endpoints for authentication and user management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging # Add logging import

from app.db.session import get_db
from app.db.models.user import User
from app.auth.dependencies import get_current_user # Using the correct dependency name
from app.crud import api_key as api_key_crud
from app.schemas.api_key import (
    APIKeyResponse,
    APIKeyInfo,
    CSRFTokenUpdate,
    LinkedInCookiesUpdate,
    WebhookConfigUpdate
)
from pydantic import BaseModel
from typing import Optional, Dict
from app.core.security import get_password_hash # Reused for hashing API keys

# Schema for creating API key with optional initial data
class CreateAPIKeyRequest(BaseModel):
    name: Optional[str] = None
    csrf_token: Optional[str] = None
    linkedin_cookies: Optional[Dict[str, str]] = None

router = APIRouter(
    prefix="/users/me",
    tags=["api-keys"],
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_PREFIX_GENERATION_ATTEMPTS = 5 # Added constant for retry limit

# --- API Key Endpoints --- 

@router.get("/api-key", response_model=APIKeyInfo)
async def get_user_api_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve information about the current user's primary (most recently used) active API key.
    
    BACKWARD COMPATIBILITY:
    - If user has one key (legacy): returns that key
    - If user has multiple keys (v1.1.0+): returns the most recently used key
    
    Returns 404 if no active key is found.
    """
    logger.info(f"Executing get_user_api_key for user ID: {current_user.id}")
    primary_key = await api_key_crud.get_primary_api_key_by_user(db=db, user_id=current_user.id)
    if not primary_key:
        logger.warning(f"No active API key found for user ID: {current_user.id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active API key found.")
    logger.info(f"Found primary API key for user ID: {current_user.id} (prefix: {primary_key.prefix})")
    # Ensure the response model includes the prefix now
    return APIKeyInfo.model_validate(primary_key)

@router.post("/api-key", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_user_api_key(
    request_data: CreateAPIKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new API key for the current user.

    - Deactivates any existing active API key for the user.
    - Generates a new key with a unique prefix.
    - Stores the prefix and the hash of the secret part.
    - Optionally stores initial CSRF token and LinkedIn cookies if provided.
    - Returns the **full key string** along with other info.
      **The full key is only returned ONCE upon creation.**
    """
    logger.info(f"Attempting to create new API key for user ID: {current_user.id}")
    
    name = request_data.name
    csrf_token = request_data.csrf_token
    linkedin_cookies = request_data.linkedin_cookies

    prefix = None
    secret_part = None
    full_key_string = None

    for attempt in range(MAX_PREFIX_GENERATION_ATTEMPTS):
        logger.debug(f"Generating API key components (Attempt {attempt + 1})")
        prefix_candidate, secret_part_candidate, full_key_string_candidate = api_key_crud.generate_api_key()
        
        logger.debug(f"Checking uniqueness of prefix: {prefix_candidate}")
        existing_key_with_prefix = await api_key_crud.get_api_key_by_prefix(db, prefix=prefix_candidate)
        
        if not existing_key_with_prefix:
            prefix = prefix_candidate
            secret_part = secret_part_candidate
            full_key_string = full_key_string_candidate
            logger.info(f"Unique prefix found: {prefix}")
            break # Found a unique prefix
        else:
            logger.warning(f"Prefix collision detected: {prefix_candidate}. Retrying...")
    
    if prefix is None or secret_part is None or full_key_string is None:
        logger.error(f"Failed to generate a unique API key prefix after {MAX_PREFIX_GENERATION_ATTEMPTS} attempts for user ID: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to generate unique API key prefix. Please try again later."
        )

    # Hash only the secret part
    secret_hash = get_password_hash(secret_part)
    logger.debug("Secret part hashed successfully.")

    # Create the key (this also deactivates old ones)
    try:
        logger.debug(f"Calling CRUD create_api_key with prefix: {prefix}")
        created_key_model = await api_key_crud.create_api_key(
            db=db,
            user_id=current_user.id,
            prefix=prefix,
            key_hash=secret_hash,
            name=name,
            csrf_token=csrf_token,
            linkedin_cookies=linkedin_cookies
        )
        logger.info(f"API Key created in DB: ID={created_key_model.id}, Prefix={created_key_model.prefix}, IsActive={created_key_model.is_active}")
    except Exception as e:
        logger.exception(f"Database error during API key creation for user {current_user.id}: {e}")
        # Consider specific exception handling if needed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to save API key to the database."
        )

    # Return the new key info *including* the raw key string this one time
    # Note: WebSocket does NOT need to be disconnected/reconnected
    # The WebSocket represents the browser instance and stays connected
    response_data = APIKeyResponse.model_validate(created_key_model)
    response_data.key = full_key_string # Add the raw key to the response
    logger.info(f"Successfully generated and created API key for user ID: {current_user.id}")
    return response_data

@router.patch("/api-key/csrf-token", response_model=APIKeyInfo)
async def update_csrf_token(
    csrf_data: CSRFTokenUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the CSRF token for the current user's active API key.
    Returns the updated API key info.
    """
    logger.info(f"Updating CSRF token for user ID: {current_user.id}")
    updated_key = await api_key_crud.update_csrf_token(
        db=db, 
        user_id=current_user.id, 
        csrf_token=csrf_data.csrf_token
    )
    if not updated_key:
        logger.warning(f"No active API key found to update CSRF token for user ID: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="No active API key found to update."
        )
    logger.info(f"CSRF token updated successfully for user ID: {current_user.id}")
    return APIKeyInfo.model_validate(updated_key)

@router.patch("/api-key/linkedin-cookies", response_model=APIKeyInfo)
async def update_linkedin_cookies_endpoint(
    cookies_data: LinkedInCookiesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update LinkedIn cookies for the current user's active API key.
    Returns the updated API key info.
    """
    logger.info(f"Updating LinkedIn cookies for user ID: {current_user.id}")
    updated_key = await api_key_crud.update_linkedin_cookies(
        db=db, 
        user_id=current_user.id, 
        linkedin_cookies=cookies_data.linkedin_cookies
    )
    if not updated_key:
        logger.warning(f"No active API key found to update LinkedIn cookies for user ID: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="No active API key found to update."
        )
    logger.info(f"LinkedIn cookies updated successfully for user ID: {current_user.id}")
    return APIKeyInfo.model_validate(updated_key)

@router.delete("/api-key", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_api_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deactivate the current user's active API key.
    Returns 204 No Content on success or if no key exists.
    """
    deactivated = await api_key_crud.deactivate_api_key(db=db, user_id=current_user.id)
    # We return 204 regardless of whether a key was found and deactivated or not.
    # The goal is idempotent: ensure no active key exists after the call.
    return None # Return None for 204 status code 


@router.patch("/api-key/webhook", response_model=APIKeyInfo)
async def update_primary_webhook(
    webhook_data: WebhookConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update webhook configuration for the user's primary API key (legacy compatibility).
    """
    try:
        updated_key = await api_key_crud.update_webhook_for_primary(
            db=db,
            user_id=current_user.id,
            webhook_url=str(webhook_data.webhook_url),
            webhook_headers=webhook_data.webhook_headers or {}
        )

        if not updated_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active API key found to update."
            )

        await db.commit()
        return APIKeyInfo.model_validate(updated_key)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[API_KEYS] Error updating webhook for user {current_user.id}: {exc}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update webhook configuration."
        )


@router.delete("/api-key/webhook", response_model=APIKeyInfo)
async def delete_primary_webhook(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove webhook configuration for the user's primary API key (legacy compatibility).
    """
    try:
        updated_key = await api_key_crud.clear_webhook_for_primary(
            db=db,
            user_id=current_user.id
        )

        if not updated_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active API key found to update."
            )

        await db.commit()
        return APIKeyInfo.model_validate(updated_key)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[API_KEYS] Error clearing webhook for user {current_user.id}: {exc}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove webhook configuration."
        )
