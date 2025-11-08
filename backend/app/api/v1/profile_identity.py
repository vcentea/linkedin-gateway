"""
API endpoints for profile identity operations.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.dependencies import get_db
from app.ws.events import WebSocketEventHandler
from app.api.v1.posts import get_ws_handler
from app.auth.dependencies import get_current_user, validate_api_key_from_header_or_body

from app.schemas.profile import (
    ScrapeProfileIdentityRequest,
    ScrapeProfileIdentityResponse
)
from app.linkedin.services.profile_identity import LinkedInProfileIdentityService
from app.linkedin.helpers import get_linkedin_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/profiles",
    tags=["profiles"],
)


@router.post("/identity", response_model=ScrapeProfileIdentityResponse)
async def scrape_profile_identity(
    request_body: ScrapeProfileIdentityRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Scrape identity data for a LinkedIn profile (identity cards + HTML data).
    
    Returns: vanity_name, first/last name, headline, location, connection degree, follower count
    
    Authentication: Provide API key via X-API-Key header OR in request body
    """
    logger.info(f"[IDENTITY] Scrape request received for: {request_body.profile_id}")
    
    # Validate API key from header or body
    api_key = await validate_api_key_from_header_or_body(
        api_key_from_body=request_body.api_key,
        api_key_header=x_api_key,
        db=db
    )
    user_id_str = str(api_key.user_id)
    logger.info(f"[IDENTITY] API Key validated for user ID: {user_id_str}")
    
    if not request_body.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        # Check if user has any active WebSocket connections

        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[IDENTITY] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    logger.info(f"[IDENTITY][{mode}] Executing for user {user_id_str}")
    logger.info(f"[IDENTITY][{mode}] Profile ID: {request_body.profile_id}")
    
    try:
        identity_service = await get_linkedin_service(db, api_key, LinkedInProfileIdentityService)
        
        identity_data = await identity_service.scrape_profile_identity(
            profile_id_or_url=request_body.profile_id
        )
        
        logger.info(f"[IDENTITY][{mode}] Successfully scraped identity: {identity_data.get('linkedin_id')}")
        
        return ScrapeProfileIdentityResponse(**identity_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[IDENTITY][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )

