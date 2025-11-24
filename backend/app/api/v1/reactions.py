"""
API endpoints for handling post reactions.

This endpoint supports two execution modes:
1. server_call=True: Execute LinkedIn API call directly from backend
2. server_call=False (default): Execute via browser extension as transparent HTTP proxy
"""

import logging
import json
import random
import asyncio
from typing import List, Dict, Any
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Body, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.models.user import User
from app.schemas.post import (
    GetReactionsRequest,
    ReactorDetail,
    GetReactionsResponse
)
from app.ws.events import WebSocketEventHandler
from app.db.dependencies import get_db
from app.api.dependencies import get_ws_handler
from app.auth.dependencies import validate_api_key_from_header_or_body
# Import LinkedIn services
from app.linkedin.services.reactions import LinkedInReactionsService
from app.linkedin.helpers import get_linkedin_service, proxy_http_request
from app.core.linkedin_rate_limit import apply_pagination_delay

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter()

@router.post("/posts/get-reactions", response_model=GetReactionsResponse, tags=["reactions"])
async def get_post_reactions(
    request_body: GetReactionsRequest = Body(...),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Fetch reactions for a specific LinkedIn post using API Key auth.
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False (default): Transparent HTTP proxy via browser extension
    
    Authentication: Provide API key via X-API-Key header OR in request body
    
    Args:
        request_body: Request containing post_url, pagination params, and execution mode
        ws_handler: WebSocket handler for proxy mode
        db: Database session
        
    Returns:
        GetReactionsResponse with list of reactor details
        
    Raises:
        HTTPException 401: If API key is invalid
        HTTPException 404: If user is not connected via WebSocket (proxy mode)
        HTTPException 408: If the client does not respond within timeout (proxy mode)
        HTTPException 500: If server-side execution fails
        HTTPException 502: If proxy returns an error
        HTTPException 503: If WebSocket service is unavailable (proxy mode)
    """
    logger.info(f"[REACTIONS] Received request for post: {request_body.post_url}")

    # --- Validate API Key from Header or Body --- 
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_body.api_key,
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[REACTIONS] API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[REACTIONS] Unexpected error during API key validation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error during authentication")

    user_id_str = str(api_key.user_id)

    # Check WebSocket connection if using proxy mode
    if not request_body.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        # Check if user has any active WebSocket connections
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[REACTIONS] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    # --- UNIFIED PAGINATION LOGIC ---
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    logger.info(f"[REACTIONS][{mode}] Executing for user {user_id_str}")
    logger.info(f"[REACTIONS][{mode}] Parameters - post_url: {request_body.post_url}, count: {request_body.count}")
    
    try:
        # Get service to build URLs and parse responses (uses CSRF/cookies from api_key object)
        reactions_service = await get_linkedin_service(db, api_key, LinkedInReactionsService)
        
        # Simple pagination logic: Fetch batches of 10 until we get an empty response
        all_reactors = []
        start_index = 0
        pagination_token = None
        max_count = request_body.count
        fetch_all = (max_count == -1)
        batch_size = 10  # Always use 10
        actual_post_url = request_body.post_url
        
        logger.info(f"[REACTIONS][{mode}] Starting pagination: max_count={max_count}, batch_size={batch_size}")
        
        while True:
            # Check if we've reached max_count limit (if not fetching all)
            if not fetch_all:
                remaining = max_count - len(all_reactors)
                if remaining <= 0:
                    logger.info(f"[REACTIONS][{mode}] Reached max_count limit of {max_count}")
                    break
                batch_size = min(10, remaining)
            
            logger.info(f"[REACTIONS][{mode}] Fetching batch {len(all_reactors)//10 + 1}: start={start_index}, count={batch_size}, has_token={pagination_token is not None}")
            
            # Build the exact LinkedIn URL for this batch (await since it may convert activity to ugcPost)
            url = await reactions_service._build_reactions_url(
                post_url=actual_post_url,
                start=start_index,
                count=batch_size,
                pagination_token=pagination_token
            )
            
            # --- EXECUTE REQUEST (proxy or direct) ---
            if request_body.server_call:
                # Direct server-side call
                raw_json_data = await reactions_service._make_request(url)
            else:
                # Proxy via browser extension (route to specific instance)
                proxy_response = await proxy_http_request(
                    ws_handler=ws_handler,
                    user_id=user_id_str,
                    url=url,
                    method="GET",
                    headers=reactions_service.headers,
                    body=None,
                    response_type="json",
                    include_credentials=True,
                    timeout=60.0,
                    instance_id=api_key.instance_id  # Route to specific instance
                )
                
                logger.info(f"[REACTIONS][{mode}] Received response with status {proxy_response['status_code']}")
                
                # Check for HTTP errors
                if proxy_response['status_code'] >= 400:
                    error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
                    logger.error(f"[REACTIONS][{mode}] {error_msg}")
                    # If we have some results, return them; otherwise raise error
                    if all_reactors:
                        logger.warning(f"[REACTIONS][{mode}] Returning {len(all_reactors)} reactors collected before error")
                        break
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=error_msg
                        )
                
                # Parse the raw JSON body from proxy response
                raw_json_data = json.loads(proxy_response['body'])
            
            # --- PARSE RESPONSE (unified) ---
            reactors, pagination_token, total_reactions = reactions_service._parse_reactions_response(raw_json_data)
            
            if not reactors:
                logger.info(f"[REACTIONS][{mode}] Empty batch received, stopping pagination")
                break
            
            logger.info(f"[REACTIONS][{mode}] Batch contained {len(reactors)} reactors")
            all_reactors.extend(reactors)
            
            # Check if we've fetched all available reactions
            if not pagination_token:
                logger.info(f"[REACTIONS][{mode}] No more pagination token, finished fetching")
                break
            
            # Increment start index for next batch
            start_index += batch_size
            
            # Add configurable delay between requests
            await apply_pagination_delay(
                min_delay=request_body.min_delay,
                max_delay=request_body.max_delay,
                operation_name=f"REACTIONS-{mode}"
            )
        
        logger.info(f"[REACTIONS][{mode}] Successfully fetched total of {len(all_reactors)} reactors")
        
        # Convert to response models
        reactor_models = [ReactorDetail(**reactor) for reactor in all_reactors]
        
        return GetReactionsResponse(data=reactor_models)
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[REACTIONS][{mode}] Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"[REACTIONS][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch reactions: {str(e)}"
        )

