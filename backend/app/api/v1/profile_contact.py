"""
API endpoints for profile contact information operations.
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
    ScrapeProfileContactRequest,
    ScrapeProfileContactResponse
)
from app.linkedin.services.profile_contact import LinkedInProfileContactService
from app.linkedin.helpers import get_linkedin_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/profiles",
    tags=["profiles"],
)


@router.post("/contact", response_model=ScrapeProfileContactResponse)
async def scrape_profile_contact(
    request_body: ScrapeProfileContactRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Scrape contact information for a LinkedIn profile.
    
    Returns: email, phone, website, birthday, connected_date
    
    Authentication: Provide API key via X-API-Key header OR in request body
    """
    logger.info(f"[CONTACT] Scrape request received for: {request_body.profile_id}")
    
    # Validate API key from header or body
    api_key = await validate_api_key_from_header_or_body(
        api_key_from_body=request_body.api_key,
        api_key_header=x_api_key,
        db=db
    )
    user_id_str = str(api_key.user_id)
    logger.info(f"[CONTACT] API Key validated for user ID: {user_id_str}")
    
    if not request_body.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        # Check if user has any active WebSocket connections

        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[CONTACT] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    logger.info(f"[CONTACT][{mode}] Executing for user {user_id_str}")
    logger.info(f"[CONTACT][{mode}] Profile ID: {request_body.profile_id}")
    
    try:
        contact_service = await get_linkedin_service(db, api_key, LinkedInProfileContactService)
        
        contact_data = await contact_service.scrape_profile_contact(
            profile_id_or_url=request_body.profile_id
        )
        
        logger.info(f"[CONTACT][{mode}] Successfully scraped contact info")
        
        return ScrapeProfileContactResponse(**contact_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[CONTACT][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )

