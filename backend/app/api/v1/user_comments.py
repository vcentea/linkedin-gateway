"""
API endpoints for handling user profile comments.

Fetches comments made by a specific user with full context including posts and parent comments.

This endpoint supports two execution modes:
1. server_call=True: Execute LinkedIn API call directly from backend
2. server_call=False (default): Execute via browser extension as transparent HTTP proxy
"""

import logging
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.post import (
    GetUserCommentsRequest,
    GetUserCommentsResponse,
    UserCommentDetail
)
from app.ws.events import WebSocketEventHandler
from app.db.dependencies import get_db
from app.api.dependencies import get_ws_handler
from app.auth.dependencies import validate_api_key_from_header_or_body
from app.linkedin.services.user_comments import LinkedInUserCommentsService
from app.linkedin.helpers import get_linkedin_service, proxy_http_request
from app.core.linkedin_rate_limit import apply_pagination_delay

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_USER_COMMENTS = 200

@router.post("/profile/comments", response_model=GetUserCommentsResponse, tags=["profile"])
async def get_user_comments(
    request_body: GetUserCommentsRequest = Body(...),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Fetch comments made by a specific user profile with full context.
    
    Returns:
    - User's comment text
    - Post text and URL the comment was on
    - Parent comment (if reply) with text and ID
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False (default): Transparent HTTP proxy via browser extension
    
    Authentication: Provide API key via X-API-Key header OR in request body
    
    Args:
        request_body: Request containing profile_id, pagination params, and execution mode
        ws_handler: WebSocket handler for proxy mode
        db: Database session
        
    Returns:
        GetUserCommentsResponse with list of user comment details
        
    Raises:
        HTTPException 401: If API key is invalid
        HTTPException 404: If user is not connected via WebSocket (proxy mode)
        HTTPException 408: If the client does not respond within timeout (proxy mode)
        HTTPException 500: If server-side execution fails
        HTTPException 502: If proxy returns an error
        HTTPException 503: If WebSocket service is unavailable (proxy mode)
    """
    logger.info(f"[USER_COMMENTS] Received request for profile: {request_body.profile_id}")

    # --- Validate API Key from Header or Body --- 
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_body.api_key,
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[USER_COMMENTS] API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[USER_COMMENTS] Unexpected error during API key validation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error during authentication")

    user_id_str = str(api_key.user_id)

    if request_body.count != -1 and request_body.count <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="count must be a positive integer or -1"
        )

    # Check WebSocket connection if using proxy mode
    if not request_body.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        # Check if user has any active WebSocket connections
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[USER_COMMENTS] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    # --- UNIFIED PAGINATION LOGIC ---
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    logger.info(f"[USER_COMMENTS][{mode}] Executing for user {user_id_str}")
    logger.info(f"[USER_COMMENTS][{mode}] Parameters - profile_id: {request_body.profile_id}, count: {request_body.count}")
    
    try:
        # Get service (uses CSRF/cookies from api_key object)
        service = await get_linkedin_service(db, api_key, LinkedInUserCommentsService)
        
        # Extract profile ID from URL if needed (same as other profile endpoints)
        from app.linkedin.utils.profile_id_extractor import extract_profile_id
        logger.info(f"[USER_COMMENTS][{mode}] Extracting profile ID from: {request_body.profile_id}")
        profile_id = await extract_profile_id(
            profile_input=request_body.profile_id,
            headers=service.headers,
            timeout=service.TIMEOUT
        )
        logger.info(f"[USER_COMMENTS][{mode}] Extracted profile ID: {profile_id}")
        
        # Pagination setup
        all_comments = []
        start_index = 0
        pagination_token = None
        requested_count = request_body.count
        if requested_count == -1:
            max_count = MAX_USER_COMMENTS
        else:
            max_count = min(requested_count, MAX_USER_COMMENTS)
        fetch_all = (requested_count == -1)
        batch_size = 20  # LinkedIn's default
        
        if requested_count > MAX_USER_COMMENTS or requested_count == -1:
            logger.info(f"[USER_COMMENTS][{mode}] Applying hard cap of {MAX_USER_COMMENTS} comments")
        
        logger.info(f"[USER_COMMENTS][{mode}] Starting pagination: max_count={max_count}, batch_size={batch_size}")
        
        while True:
            # Check if we've reached max_count limit
            if not fetch_all:
                remaining = max_count - len(all_comments)
                if remaining <= 0:
                    logger.info(f"[USER_COMMENTS][{mode}] Reached max_count limit of {max_count}")
                    break
                batch_size = min(20, remaining)
            
            logger.info(f"[USER_COMMENTS][{mode}] Fetching batch {len(all_comments)//20 + 1}: start={start_index}, count={batch_size}, has_token={pagination_token is not None}")
            
            # Build URL (now using extracted profile_id)
            url = service._build_user_comments_url(
                profile_id=profile_id,
                start=start_index,
                count=batch_size,
                pagination_token=pagination_token
            )
            
            # --- EXECUTE REQUEST (proxy or direct) ---
            if request_body.server_call:
                # Direct server-side call
                raw_json_data = await service._make_request(url)
            else:
                # Proxy via browser extension (route to specific instance)
                proxy_response = await proxy_http_request(
                    ws_handler=ws_handler,
                    user_id=user_id_str,
                    url=url,
                    method="GET",
                    headers=service.headers,
                    body=None,
                    response_type="json",
                    include_credentials=True,
                    timeout=60.0,
                    instance_id=api_key.instance_id  # Route to specific instance
                )
                
                logger.info(f"[USER_COMMENTS][{mode}] Received response with status {proxy_response['status_code']}")
                
                # Check for HTTP errors
                if proxy_response['status_code'] >= 400:
                    error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
                    logger.error(f"[USER_COMMENTS][{mode}] {error_msg}")
                    if all_comments:
                        logger.warning(f"[USER_COMMENTS][{mode}] Returning {len(all_comments)} comments collected before error")
                        break
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=error_msg
                        )
                
                # Parse JSON from proxy response
                raw_json_data = json.loads(proxy_response['body'])
            
            # --- PARSE RESPONSE (unified) ---
            comments, pagination_token, total = service._parse_user_comments_response(raw_json_data)
            
            if not comments:
                logger.info(f"[USER_COMMENTS][{mode}] Empty batch received, stopping pagination")
                break
            
            logger.info(f"[USER_COMMENTS][{mode}] Batch contained {len(comments)} comments")
            all_comments.extend(comments)

            if len(all_comments) >= max_count:
                if fetch_all and len(all_comments) > max_count:
                    all_comments = all_comments[:max_count]
                logger.info(f"[USER_COMMENTS][{mode}] Reached hard cap of {max_count} comments")
                break
            
            # Check if we've fetched all available comments
            if not pagination_token:
                logger.info(f"[USER_COMMENTS][{mode}] No more pagination token, finished fetching")
                break
            
            # Increment start index for next batch
            start_index += batch_size
            
            # Add configurable delay between requests
            await apply_pagination_delay(
                min_delay=request_body.min_delay,
                max_delay=request_body.max_delay,
                operation_name=f"USER_COMMENTS-{mode}"
            )
        
        logger.info(f"[USER_COMMENTS][{mode}] Successfully fetched total of {len(all_comments)} user comments")
        
        # Convert to response models
        comment_models = [UserCommentDetail(**comment) for comment in all_comments]
        
        return GetUserCommentsResponse(data=comment_models)
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[USER_COMMENTS][{mode}] Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"[USER_COMMENTS][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user comments: {str(e)}"
        )

