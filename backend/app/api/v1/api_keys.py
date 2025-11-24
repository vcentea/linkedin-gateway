"""
API Key management endpoints.
Handles generation, listing, updating, and deletion of API keys with multi-key support.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.db.models.user import User
from app.auth.dependencies import get_current_user
from app.core.security import get_password_hash
from app.schemas.api_key import (
    APIKeyInfo,
    APIKeyResponse,
    APIKeyGenerateRequest,
    APIKeyListResponse,
    InstanceNameUpdate,
    CSRFTokenUpdate,
    LinkedInCookiesUpdate,
    WebhookConfigUpdate
)
from app.crud import api_key as crud_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api-keys",
    tags=["api-keys"],
)

# Maximum number of API keys per user
MAX_KEYS_PER_USER = 10


@router.post("/generate", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def generate_api_key(
    request_data: APIKeyGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a new API key for the authenticated user.
    
    Multi-key behavior (v1.1.0):
    - If instance_id provided: Creates/updates key for that instance
    - If instance_id NOT provided: Uses legacy single-key behavior (deactivates all others)
    
    The full API key is only returned once on creation.
    
    Args:
        request_data: Key generation request with optional instance info
        current_user: Authenticated user from JWT token
        db: Database session
        
    Returns:
        APIKeyResponse with full key (only time it's visible)
        
    Raises:
        HTTPException 400: If user has too many active keys
        HTTPException 500: On database errors
    """
    try:
        # Check if user has too many keys (only if creating new instance key)
        if request_data.instance_id:
            existing_keys = await crud_api_key.get_all_api_keys_for_user(
                db, current_user.id, include_inactive=False
            )
            
            # Check if this is an update or new key
            is_update = any(k.instance_id == request_data.instance_id for k in existing_keys)
            
            if not is_update and len(existing_keys) >= MAX_KEYS_PER_USER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Maximum number of API keys ({MAX_KEYS_PER_USER}) reached. Please deactivate an existing key first."
                )
        
        # Generate new API key components
        prefix, secret_part, full_key = crud_api_key.generate_api_key()
        
        # Hash only the secret part for storage (not the full key)
        # The prefix is stored separately, authentication validates secret_part against this hash
        key_hash = get_password_hash(secret_part)
        
        # Create or update the API key in database
        db_api_key = await crud_api_key.create_api_key(
            db=db,
            user_id=current_user.id,
            prefix=prefix,
            key_hash=key_hash,
            name=request_data.name,
            csrf_token=request_data.csrf_token,
            linkedin_cookies=request_data.linkedin_cookies,
            instance_id=request_data.instance_id,
            instance_name=request_data.instance_name,
            browser_info=request_data.browser_info
        )
        
        await db.commit()

        logger.info(
            f"[API_KEYS] Generated new key for user {current_user.id}, "
            f"instance: {request_data.instance_id or 'legacy'}, "
            f"prefix: {prefix}"
        )

        # Return response with full key (only time it's visible)
        # Note: WebSocket does NOT need to be disconnected/reconnected
        # The instance_id is already in the URL and doesn't change
        # Backend will route requests based on the api_key.instance_id
        response = APIKeyResponse.model_validate(db_api_key)
        response.key = full_key

        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_KEYS] Error generating key: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate API key"
        )


@router.get("/list", response_model=APIKeyListResponse)
async def list_api_keys(
    include_inactive: bool = Query(False, description="Include deactivated keys in the list"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all API keys for the authenticated user.
    
    Args:
        include_inactive: If True, includes deactivated keys
        current_user: Authenticated user from JWT token
        db: Database session
        
    Returns:
        APIKeyListResponse with list of keys, total count, and active count
        
    Raises:
        HTTPException 500: On database errors
    """
    try:
        # Get all keys for the user
        keys = await crud_api_key.get_all_api_keys_for_user(
            db, current_user.id, include_inactive=include_inactive
        )
        
        # Calculate stats
        total = len(keys)
        active_count = sum(1 for k in keys if k.is_active)
        
        # Convert to response schemas (no full keys, only prefixes)
        key_infos = [APIKeyInfo.model_validate(k) for k in keys]
        
        logger.info(
            f"[API_KEYS] Listed {total} keys for user {current_user.id} "
            f"({active_count} active, {total - active_count} inactive)"
        )
        
        return APIKeyListResponse(
            keys=key_infos,
            total=total,
            active_count=active_count
        )
        
    except Exception as e:
        logger.error(f"[API_KEYS] Error listing keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys"
        )


@router.get("/{key_id}", response_model=APIKeyInfo)
async def get_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get information about a specific API key.
    
    Args:
        key_id: API key UUID
        current_user: Authenticated user from JWT token
        db: Database session
        
    Returns:
        APIKeyInfo for the requested key (no full key, only prefix)
        
    Raises:
        HTTPException 404: If key not found or doesn't belong to user
        HTTPException 500: On database errors
    """
    try:
        api_key = await crud_api_key.get_api_key_by_id(db, key_id, current_user.id)
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        return APIKeyInfo.model_validate(api_key)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_KEYS] Error getting key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API key"
        )


@router.delete("/{key_id}")
async def deactivate_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Deactivate a specific API key.
    
    The key is not deleted from the database (audit trail), just marked as inactive.
    
    Args:
        key_id: API key UUID
        current_user: Authenticated user from JWT token
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException 404: If key not found or doesn't belong to user
        HTTPException 500: On database errors
    """
    try:
        success = await crud_api_key.deactivate_api_key_by_id(db, key_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        await db.commit()
        
        logger.info(f"[API_KEYS] Deactivated key {key_id} for user {current_user.id}")
        
        return {
            "success": True,
            "message": "API key deactivated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_KEYS] Error deactivating key {key_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate API key"
        )


@router.patch("/{key_id}/name", response_model=APIKeyInfo)
async def update_instance_name(
    key_id: UUID,
    request_data: InstanceNameUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update the friendly name of an API key instance.
    
    Args:
        key_id: API key UUID
        request_data: New instance name
        current_user: Authenticated user from JWT token
        db: Database session
        
    Returns:
        Updated APIKeyInfo
        
    Raises:
        HTTPException 404: If key not found or doesn't belong to user
        HTTPException 500: On database errors
    """
    try:
        updated_key = await crud_api_key.update_instance_name(
            db, key_id, current_user.id, request_data.instance_name
        )
        
        if not updated_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        await db.commit()
        
        logger.info(
            f"[API_KEYS] Updated instance name for key {key_id}, "
            f"user {current_user.id}: {request_data.instance_name}"
        )
        
        return APIKeyInfo.model_validate(updated_key)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_KEYS] Error updating instance name for key {key_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update instance name"
        )


@router.patch("/{key_id}/csrf", response_model=APIKeyInfo)
async def update_csrf_token(
    key_id: UUID,
    request_data: CSRFTokenUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update the CSRF token for a specific API key.
    
    Args:
        key_id: API key UUID
        request_data: New CSRF token
        current_user: Authenticated user from JWT token
        db: Database session
        
    Returns:
        Updated APIKeyInfo
        
    Raises:
        HTTPException 404: If key not found or doesn't belong to user
        HTTPException 500: On database errors
    """
    try:
        # Get the key and verify ownership
        api_key = await crud_api_key.get_api_key_by_id(db, key_id, current_user.id)
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Update CSRF token
        api_key.csrf_token = request_data.csrf_token
        db.add(api_key)
        await db.flush()
        await db.refresh(api_key)
        await db.commit()
        
        logger.info(f"[API_KEYS] Updated CSRF token for key {key_id}, user {current_user.id}")
        
        return APIKeyInfo.model_validate(api_key)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_KEYS] Error updating CSRF token for key {key_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update CSRF token"
        )


@router.patch("/{key_id}/cookies", response_model=APIKeyInfo)
async def update_linkedin_cookies(
    key_id: UUID,
    request_data: LinkedInCookiesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update LinkedIn session cookies for a specific API key.
    
    Args:
        key_id: API key UUID
        request_data: New LinkedIn cookies
        current_user: Authenticated user from JWT token
        db: Database session
        
    Returns:
        Updated APIKeyInfo
        
    Raises:
        HTTPException 404: If key not found or doesn't belong to user
        HTTPException 500: On database errors
    """
    try:
        # Get the key and verify ownership
        api_key = await crud_api_key.get_api_key_by_id(db, key_id, current_user.id)
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Update LinkedIn cookies
        api_key.linkedin_cookies = request_data.linkedin_cookies
        db.add(api_key)
        await db.flush()
        await db.refresh(api_key)
        await db.commit()
        
        logger.info(f"[API_KEYS] Updated LinkedIn cookies for key {key_id}, user {current_user.id}")
        
        return APIKeyInfo.model_validate(api_key)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_KEYS] Error updating LinkedIn cookies for key {key_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update LinkedIn cookies"
        )


@router.patch("/{key_id}/webhook", response_model=APIKeyInfo)
async def update_api_key_webhook(
    key_id: UUID,
    request_data: WebhookConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update webhook configuration for a specific API key.
    """
    try:
        updated_key = await crud_api_key.update_webhook_for_key(
            db=db,
            key_id=key_id,
            user_id=current_user.id,
            webhook_url=str(request_data.webhook_url),
            webhook_headers=request_data.webhook_headers or {}
        )

        if not updated_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        await db.commit()
        return APIKeyInfo.model_validate(updated_key)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[API_KEYS] Error updating webhook for key {key_id}: {exc}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update webhook configuration"
        )


@router.delete("/{key_id}/webhook", response_model=APIKeyInfo)
async def delete_api_key_webhook(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove webhook configuration for a specific API key.
    """
    try:
        updated_key = await crud_api_key.clear_webhook_for_key(
            db=db,
            key_id=key_id,
            user_id=current_user.id
        )

        if not updated_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        await db.commit()
        return APIKeyInfo.model_validate(updated_key)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[API_KEYS] Error clearing webhook for key {key_id}: {exc}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove webhook configuration"
        )
