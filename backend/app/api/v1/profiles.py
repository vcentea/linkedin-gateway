"""
API endpoints for profile-related operations.
"""
import logging
import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.dependencies import get_db
from app.ws.events import WebSocketEventHandler
from app.api.v1.posts import get_ws_handler, PendingRequest, pending_ws_requests
from app.auth.dependencies import get_current_user
from app.auth.dependencies import validate_api_key_from_header_or_body
from app.ws.message_types import MessageSchema

from app.crud import profile as profile_crud
from app.db.models.user import User
from app.schemas.profile import (
    ProfileCreate, 
    ProfileInDB,
    ScrapeProfileRequest,
    ScrapeProfileResponse,
    ScrapeProfileExperiencesRequest,
    ScrapeProfileExperiencesResponse,
    ScrapeProfileRecommendationsRequest,
    ScrapeProfileRecommendationsResponse
)
from app.linkedin.services.profile import LinkedInProfileService
from app.linkedin.helpers import get_linkedin_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/profiles",
    tags=["profiles"],
)

@router.post(
    "/", 
    response_model=ProfileInDB, 
    status_code=status.HTTP_201_CREATED,
    deprecated=True
)
async def create_profile_endpoint(
    profile_data: ProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler)
):
    """
    **DEPRECATED**: This endpoint is for internal use only.
    
    Create a new profile and attempt to fetch vanity name via WebSocket if possible.
    """
    return await profile_crud.create_profile(
        db=db,
        profile_in=profile_data,
        ws_handler=ws_handler,
        user_id=str(current_user.id)
    )

@router.post("/scrape", response_model=ScrapeProfileResponse)
async def scrape_profile(
    request_body: ScrapeProfileRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Scrape a LinkedIn profile by ID or URL.
    
    Supports both server-side execution (server_call=true) and 
    WebSocket execution (server_call=false).
    
    Replicates the exact profile scraping logic from the old project's
    profile_service.js file.
    """
    logger.info(f"Profile scrape request received for: {request_body.profile_id}")
    
    # Validate API key
    api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_body.api_key,
            api_key_header=x_api_key,
            db=db
        )
    user_id_str = str(api_key.user_id)
    logger.info(f"API Key validated for user ID: {user_id_str}")
    
    # Check WebSocket connection if using proxy mode
    if not request_body.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        # Check if user has any active WebSocket connections

        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[PROFILE_SCRAPE] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    logger.info(f"[PROFILE_SCRAPE][{mode}] Executing for user {user_id_str}")
    logger.info(f"[PROFILE_SCRAPE][{mode}] Profile ID: {request_body.profile_id}")
    
    try:
        # Get initialized LinkedIn service (handles CSRF token retrieval and validation)
        profile_service = await get_linkedin_service(db, api_key, LinkedInProfileService)
        
        # Scrape the profile - service makes 5 LinkedIn API calls:
        # 1. Identity Cards (GraphQL) → vanity_name, firstName, lastName, follower_count
        # 2. Contact Info (GraphQL) → email, phone, website, birthday, connected_date
        # 3. HTML Page → headline, location, con_degree
        # 4. About & Skills (GraphQL) → about, skills
        # All use _make_request() which supports both server and proxy modes
        profile_data = await profile_service.scrape_profile(
            profile_id_or_url=request_body.profile_id
        )
        
        logger.info(f"[PROFILE_SCRAPE][{mode}] Successfully scraped profile: {profile_data.get('linkedin_id')}")
        
        # Return validated response
        return ScrapeProfileResponse(**profile_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[PROFILE_SCRAPE][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.post("/experiences", response_model=ScrapeProfileExperiencesResponse)
async def scrape_profile_experiences(
    request_body: ScrapeProfileExperiencesRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Scrape work experiences for a LinkedIn profile by ID or URL.
    
    Supports both server-side execution (server_call=true) and 
    WebSocket execution (server_call=false).
    """
    logger.info(f"[EXPERIENCES] Scrape request received for: {request_body.profile_id}")
    
    # Validate API key
    api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_body.api_key, 
            api_key_header=x_api_key,
            db=db
        )
    user_id_str = str(api_key.user_id)
    logger.info(f"[EXPERIENCES] API Key validated for user ID: {user_id_str}")
    
    # Check WebSocket connection if using proxy mode
    if not request_body.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[EXPERIENCES] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    logger.info(f"[EXPERIENCES][{mode}] Executing for user {user_id_str}")
    logger.info(f"[EXPERIENCES][{mode}] Profile ID: {request_body.profile_id}")
    
    try:
        # Get initialized LinkedIn service
        profile_service = await get_linkedin_service(db, api_key, LinkedInProfileService)
        
        # Scrape the experiences - uses _make_request() which supports both modes
        experiences = await profile_service.scrape_profile_experiences(
            profile_id_or_url=request_body.profile_id
        )
        
        logger.info(f"[EXPERIENCES][{mode}] Successfully scraped {len(experiences)} experiences")
        
        # Return validated response
        return ScrapeProfileExperiencesResponse(experiences=experiences)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[EXPERIENCES][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.post("/recommendations", response_model=ScrapeProfileRecommendationsResponse)
async def scrape_profile_recommendations(
    request_body: ScrapeProfileRecommendationsRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Scrape recommendations for a LinkedIn profile by ID or URL.
    
    Supports both server-side execution (server_call=true) and 
    WebSocket execution (server_call=false).
    """
    logger.info(f"[RECOMMENDATIONS] Scrape request received for: {request_body.profile_id}")
    
    # Validate API key
    api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_body.api_key, 
            api_key_header=x_api_key,
            db=db
        )
    user_id_str = str(api_key.user_id)
    logger.info(f"[RECOMMENDATIONS] API Key validated for user ID: {user_id_str}")
    
    # Check WebSocket connection if using proxy mode
    if not request_body.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[RECOMMENDATIONS] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    logger.info(f"[RECOMMENDATIONS][{mode}] Executing for user {user_id_str}")
    logger.info(f"[RECOMMENDATIONS][{mode}] Profile ID: {request_body.profile_id}")
    
    try:
        # Get initialized LinkedIn service
        profile_service = await get_linkedin_service(db, api_key, LinkedInProfileService)
        
        # Scrape the recommendations - uses _make_request() which supports both modes
        recommendations = await profile_service.scrape_profile_recommendations(
            profile_id_or_url=request_body.profile_id
        )
        
        logger.info(f"[RECOMMENDATIONS][{mode}] Successfully scraped {len(recommendations)} recommendations")
        
        # Return validated response
        return ScrapeProfileRecommendationsResponse(recommendations=recommendations)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[RECOMMENDATIONS][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        ) 