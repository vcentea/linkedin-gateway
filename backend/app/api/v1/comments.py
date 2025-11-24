"""
API endpoints for handling post comments.

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
    GetCommentersRequest, 
    CommenterDetail, 
    GetCommentersResponse,
    PostCommentRequest,
    ReplyToCommentRequest,
    CommentResponse
)
from app.ws.events import WebSocketEventHandler
from app.db.dependencies import get_db
from app.api.dependencies import get_ws_handler
from app.auth.dependencies import validate_api_key_from_header_or_body
# Import LinkedIn services
from app.linkedin.services.comments import LinkedInCommentsService
from app.linkedin.helpers import get_linkedin_service, proxy_http_request
from app.core.linkedin_rate_limit import apply_pagination_delay

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter()

@router.post("/posts/get-commenters", response_model=GetCommentersResponse, tags=["comments"])
async def get_post_commenters(
    request_body: GetCommentersRequest = Body(...),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Fetch commenters for a specific LinkedIn post using API Key auth.
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False (default): Transparent HTTP proxy via browser extension
    
    Authentication: Provide API key via X-API-Key header OR in request body
    
    Args:
        request_body: Request containing post_url, pagination params, and execution mode
        ws_handler: WebSocket handler for proxy mode
        db: Database session
        
    Returns:
        GetCommentersResponse with list of commenter details
        
    Raises:
        HTTPException 401: If API key is invalid
        HTTPException 404: If user is not connected via WebSocket (proxy mode)
        HTTPException 408: If the client does not respond within timeout (proxy mode)
        HTTPException 500: If server-side execution fails
        HTTPException 502: If proxy returns an error
        HTTPException 503: If WebSocket service is unavailable (proxy mode)
    """
    logger.info(f"[COMMENTERS] Received request for post: {request_body.post_url}")

    # --- Validate API Key from Header or Body --- 
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_body.api_key,
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[COMMENTERS] API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[COMMENTERS] Unexpected error during API key validation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error during authentication")

    user_id_str = str(api_key.user_id)

    # Check WebSocket connection if using proxy mode
    if not request_body.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[COMMENTERS] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    # --- UNIFIED PAGINATION LOGIC ---
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    logger.info(f"[COMMENTERS][{mode}] Executing for user {user_id_str}")
    logger.info(f"[COMMENTERS][{mode}] Parameters - post_url: {request_body.post_url}, count: {request_body.count}")
    
    try:
        # Get service to build URLs and parse responses (uses CSRF/cookies from api_key object)
        comments_service = await get_linkedin_service(db, api_key, LinkedInCommentsService)
        
        # Simple pagination logic: Fetch batches of 10 until we get an empty response
        all_commenters = []
        all_social_details = []  # Collect SocialDetail objects across all pages
        start_index = 0
        pagination_token = None
        max_count = request_body.count
        fetch_all = (max_count == -1)
        include_replies = (request_body.num_replies > 0)
        batch_size = 10  # Always use 10
        actual_post_url = request_body.post_url  # Will be updated with ugcPost URN from first response
        
        logger.info(f"[COMMENTERS][{mode}] Starting simple pagination: max_count={max_count}, batch_size={batch_size}")
        
        while True:
            # Check if we've reached max_count limit (if not fetching all)
            if not fetch_all:
                remaining = max_count - len(all_commenters)
                if remaining <= 0:
                    logger.info(f"[COMMENTERS][{mode}] Reached max_count limit of {max_count}")
                    break
                batch_size = min(10, remaining)
            
            logger.info(f"[COMMENTERS][{mode}] Fetching batch {len(all_commenters)//10 + 1}: start={start_index}, count={batch_size}, has_token={pagination_token is not None}")
            
            # Build the exact LinkedIn URL for this batch
            # Use actual_post_url which may have been updated with ugcPost URN from first response
            url = comments_service._build_commenters_url(
                post_url=actual_post_url,
                start=start_index,
                count=batch_size,
                num_replies=request_body.num_replies,
                pagination_token=pagination_token
            )
            
            # --- EXECUTE REQUEST (proxy or direct) ---
            if request_body.server_call:
                # Direct server-side call
                raw_json_data = await comments_service._make_request(url)
            else:
                # Proxy via browser extension - route to specific instance
                proxy_response = await proxy_http_request(
                    ws_handler=ws_handler,
                    user_id=user_id_str,
                    url=url,
                    method="GET",
                    headers=comments_service.headers,
                    body=None,
                    response_type="json",
                    include_credentials=True,
                    timeout=60.0,
                    instance_id=api_key.instance_id  # Route to specific instance (with fallback)
                )
                
                logger.info(f"[COMMENTERS][{mode}] Received response with status {proxy_response['status_code']}")
                
                # Check for HTTP errors
                if proxy_response['status_code'] >= 400:
                    error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
                    logger.error(f"[COMMENTERS][{mode}] {error_msg}")
                    # If we have some results, return them; otherwise raise error
                    if all_commenters:
                        logger.warning(f"[COMMENTERS][{mode}] Returning {len(all_commenters)} commenters collected before error")
                        break
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=error_msg
                        )
                
                # Parse the raw JSON body from proxy response
                raw_json_data = json.loads(proxy_response['body'])
            
            # --- PARSE RESPONSE (same for both modes) ---
            batch_commenters, next_pagination_token, batch_total, ugc_post_urn, batch_social_details = comments_service._parse_commenters_response(raw_json_data, include_replies)
            
            # Collect SocialDetail objects for relationship building
            all_social_details.extend(batch_social_details)
            
            # On first batch, if we found ugcPost URN, use it for subsequent requests
            if ugc_post_urn and len(all_commenters) == 0:
                logger.info(f"[COMMENTERS][{mode}] ✓ Using ugcPost URN for subsequent requests: {ugc_post_urn}")
                actual_post_url = ugc_post_urn  # Use the ugcPost URN directly
            
            logger.info(f"[COMMENTERS][{mode}] Received {len(batch_commenters)} commenters in this batch")
            
            # SIMPLE STOPPING CONDITION: If we got no results, we've reached the end
            if len(batch_commenters) == 0:
                logger.info(f"[COMMENTERS][{mode}] Empty batch received. Reached end. Total fetched: {len(all_commenters)}")
                break
            
            all_commenters.extend(batch_commenters)
            logger.info(f"[COMMENTERS][{mode}] Total commenters so far: {len(all_commenters)}")
            
            # Move to next page
            start_index += batch_size  # Use batch_size, not actual received count
            pagination_token = next_pagination_token  # May be None, that's ok
            
            # Add configurable delay between requests
            await apply_pagination_delay(
                min_delay=request_body.min_delay,
                max_delay=request_body.max_delay,
                operation_name=f"COMMENTERS-{mode}"
            )
        
        logger.info(f"[COMMENTERS][{mode}] ✓ Completed. Total commenters fetched: {len(all_commenters)}")
        
        # --- BUILD PARENT/CHILD RELATIONSHIPS ---
        logger.info(f"[COMMENTERS][{mode}] Building parent/child relationships from {len(all_social_details)} SocialDetail objects")
        relationships = comments_service._build_comment_relationships(all_commenters, all_social_details)
        
        # Apply relationships to all comments and clean up internal fields
        for commenter in all_commenters:
            comment_urn = commenter.get('commentUrn')
            if comment_urn:
                comment_id = comments_service._extract_comment_id_from_urn(comment_urn)
                if comment_id and comment_id in relationships:
                    rel_data = relationships[comment_id]
                    commenter['parentCommentId'] = rel_data.get('parent')
                    children = rel_data.get('children', [])
                    commenter['childCommentIds'] = children if children else None
                else:
                    # Ensure fields exist even if no relationship found
                    if 'parentCommentId' not in commenter:
                        commenter['parentCommentId'] = None
                    if 'childCommentIds' not in commenter:
                        commenter['childCommentIds'] = None
            
            # Remove internal permalink field (used only for relationship building)
            commenter.pop('permalink', None)
        
        logger.info(f"[COMMENTERS][{mode}] ✓ Applied relationships to {len(all_commenters)} comments")
        
        # Validate/parse the result into Pydantic models
        validated_commenters = [CommenterDetail(**item) for item in all_commenters]
        
        logger.info(f"[COMMENTERS][{mode}] Returning {len(validated_commenters)} validated commenter details")
        return GetCommentersResponse(data=validated_commenters)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[COMMENTERS][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.post("/posts/post-comment", response_model=CommentResponse, tags=["comments"])
async def post_comment_to_post(
    request_data: PostCommentRequest,
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Post a comment to a LinkedIn post using API Key auth.
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False (default): Transparent HTTP proxy via browser extension
    
    Post URL formats supported:
        - Full URL: "https://www.linkedin.com/posts/username_activity-7384096805824937984-wuIW"
        - Feed URL: "https://www.linkedin.com/feed/update/urn:li:activity:7384096805824937984"
        - Post ID: "activity:7384096805824937984" or "ugcPost:7384096805824937984"
    
    Returns:
        {"success": True}
        
    Raises:
        HTTPException 400: If required fields are missing or post URL/ID is invalid
        HTTPException 401: If API key is invalid
        HTTPException 404: If user is not connected via WebSocket (proxy mode)
        HTTPException 408: If the client does not respond within timeout (proxy mode)
        HTTPException 500: If server-side execution fails
        HTTPException 502: If proxy returns an error
        HTTPException 503: If WebSocket service is unavailable (proxy mode)
    """
    logger.info(f"[POST COMMENT] Received request")
    
    # Extract parameters from Pydantic model
    api_key = request_data.api_key
    post_input = request_data.post_url  # Can be URL or ID
    comment_text = request_data.comment_text
    server_call = request_data.server_call
    
    # Normalize post_input to a full URL if it's just an ID
    # If it's "activity:123" or "ugcPost:123", convert to URL format
    if post_input.startswith(('activity:', 'ugcPost:')):
        post_url = f"https://www.linkedin.com/feed/update/urn:li:{post_input}"
        logger.info(f"[POST COMMENT] Converted post ID to URL: {post_url}")
    else:
        post_url = post_input
    
    logger.info(f"[POST COMMENT] Post URL: {post_url}")
    logger.info(f"[POST COMMENT] Comment text: {comment_text[:100]}...")
    
    # --- Validate API Key from Header or Body --- 
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_data.api_key,
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[POST COMMENT] API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[POST COMMENT] Unexpected error during API key validation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error during authentication")

    user_id_str = str(api_key.user_id)

    # Check WebSocket connection if using proxy mode
    if not server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[POST COMMENT] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    mode = "SERVER_CALL" if server_call else "PROXY"
    logger.info(f"[POST COMMENT][{mode}] Executing for user {user_id_str}")
    
    try:
        # Get the comments service to prepare the request (uses CSRF/cookies from api_key object)
        comments_service = await get_linkedin_service(db, api_key, LinkedInCommentsService)
        
        # Prepare URL and payload (handles activity → ugcPost conversion)
        url, payload = await comments_service.prepare_post_comment_request(post_url, comment_text)
        
        logger.info(f"[POST COMMENT][{mode}] URL: {url}")
        logger.info(f"[POST COMMENT][{mode}] Payload: {payload}")
        
        # --- EXECUTE REQUEST (proxy or direct) ---
        if server_call:
            # Direct server-side call
            await comments_service._make_request(
                url=url,
                method='POST',
                json=payload
            )
            logger.info(f"[POST COMMENT][{mode}] Successfully posted comment")
            return {"success": True}
        else:
            # Proxy via browser extension
            # Use separators=(', ', ': ') to match browser format (spaces after commas and colons)
            payload_str = json.dumps(payload, ensure_ascii=False, separators=(', ', ': '))
            logger.info(f"[POST COMMENT][{mode}] Payload size: {len(payload_str)} bytes")
            
            proxy_response = await proxy_http_request(
                ws_handler=ws_handler,
                user_id=user_id_str,
                url=url,
                method="POST",
                headers=comments_service.headers,
                body=payload_str,
                response_type="json",
                include_credentials=True,
                timeout=60.0,
                instance_id=api_key.instance_id  # Route to specific instance
            )

            logger.info(f"[POST COMMENT][{mode}] Received response with status {proxy_response['status_code']}")
            
            # Check for HTTP errors
            if proxy_response['status_code'] >= 400:
                error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
                logger.error(f"[POST COMMENT][{mode}] {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=error_msg
                )
            
            logger.info(f"[POST COMMENT][{mode}] Successfully posted comment")
            return {"success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[POST COMMENT][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.post("/posts/reply-to-comment", response_model=CommentResponse, tags=["comments"])
async def reply_to_comment(
    request_data: ReplyToCommentRequest,
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Reply to a specific comment on a LinkedIn post using API Key auth.
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False (default): Transparent HTTP proxy via browser extension
    
    Comment URN format:
        "urn:li:fsd_comment:(7383266296794161153,urn:li:activity:7383255837701591040)"
        
    This is automatically provided by the get-commenters endpoint in the commentUrn field.
    
    Returns:
        {"success": True}
        
    Raises:
        HTTPException 400: If required fields are missing or comment URN is invalid
        HTTPException 401: If API key is invalid
        HTTPException 404: If user is not connected via WebSocket (proxy mode)
        HTTPException 408: If the client does not respond within timeout (proxy mode)
        HTTPException 500: If server-side execution fails
        HTTPException 502: If proxy returns an error
        HTTPException 503: If WebSocket service is unavailable (proxy mode)
    """
    logger.info(f"[REPLY TO COMMENT] Received request")
    
    # Extract parameters from Pydantic model
    api_key = request_data.api_key
    comment_urn = request_data.comment_urn
    reply_text = request_data.reply_text
    server_call = request_data.server_call
    
    logger.info(f"[REPLY TO COMMENT] Comment URN: {comment_urn}")
    logger.info(f"[REPLY TO COMMENT] Reply text: {reply_text[:100]}...")
    
    # --- Validate API Key from Header or Body --- 
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_data.api_key,
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[REPLY TO COMMENT] API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[REPLY TO COMMENT] Unexpected error during API key validation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error during authentication")

    user_id_str = str(api_key.user_id)

    # Check WebSocket connection if using proxy mode
    if not server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[REPLY TO COMMENT] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    mode = "SERVER_CALL" if server_call else "PROXY"
    logger.info(f"[REPLY TO COMMENT][{mode}] Executing for user {user_id_str}")
    
    try:
        # Get the comments service to prepare the request (uses CSRF/cookies from api_key object)
        comments_service = await get_linkedin_service(db, api_key, LinkedInCommentsService)
        
        # Prepare URL and payload (handles URN parsing and conversion)
        url, payload = await comments_service.prepare_reply_to_comment_request(comment_urn, reply_text)
        
        logger.info(f"[REPLY TO COMMENT][{mode}] URL: {url}")
        logger.info(f"[REPLY TO COMMENT][{mode}] Payload: {payload}")
        
        # --- EXECUTE REQUEST (proxy or direct) ---
        if server_call:
            # Direct server-side call
            await comments_service._make_request(
                url=url,
                method='POST',
                json=payload
            )
            logger.info(f"[REPLY TO COMMENT][{mode}] Successfully posted reply")
            return {"success": True}
        else:
            # Proxy via browser extension
            # Use separators=(', ', ': ') to match browser format (spaces after commas and colons)
            payload_str = json.dumps(payload, ensure_ascii=False, separators=(', ', ': '))
            logger.info(f"[REPLY TO COMMENT][{mode}] Payload size: {len(payload_str)} bytes")
            
            proxy_response = await proxy_http_request(
                ws_handler=ws_handler,
                user_id=user_id_str,
                url=url,
                method="POST",
                headers=comments_service.headers,
                body=payload_str,
                response_type="json",
                include_credentials=True,
                timeout=60.0,
                instance_id=api_key.instance_id  # Route to specific instance
            )

            logger.info(f"[REPLY TO COMMENT][{mode}] Received response with status {proxy_response['status_code']}")
            
            # Check for HTTP errors
            if proxy_response['status_code'] >= 400:
                error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
                logger.error(f"[REPLY TO COMMENT][{mode}] {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=error_msg
                )
            
            logger.info(f"[REPLY TO COMMENT][{mode}] Successfully posted reply")
            return {"success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[REPLY TO COMMENT][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        ) 