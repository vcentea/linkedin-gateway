"""
API endpoint for LinkedIn direct messaging operations.

This endpoint supports two execution modes:
1. server_call=True: Execute LinkedIn API call directly from backend
2. proxy=True: Execute via browser extension as transparent HTTP proxy
"""
import logging
import json
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.ws.events import WebSocketEventHandler
from app.api.dependencies import get_ws_handler
from app.auth.dependencies import validate_api_key_from_header_or_body
from app.linkedin.services.messages import LinkedInMessageService
from app.linkedin.helpers import get_linkedin_service, proxy_http_request, refresh_linkedin_session
from app.linkedin.utils.my_profile_id_cache import (
    get_cached_my_profile_id,
    set_cached_my_profile_id,
)
from app.api.v1.server_validation import validate_server_call_permission

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/messages",
    tags=["messages"],
)


# Request/Response models
class SendMessageRequest(BaseModel):
    """Request model for sending direct message."""
    profile_id: str = Field(
        ..., 
        description="LinkedIn profile ID or profile URL (e.g., 'john-doe-123' or 'https://www.linkedin.com/in/john-doe')",
        alias="profile_identifier"
    )
    message_text: str = Field(..., description="Message text to send")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use proxy via extension")
    
    class Config:
        populate_by_name = True  # Allows both profile_id and profile_identifier


class MessageResponse(BaseModel):
    """Response model for message operations."""
    success: bool


# --- New: Get My Own Profile ID ---
class GetMyIdRequest(BaseModel):
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use proxy via extension")


class GetMyIdResponse(BaseModel):
    success: bool
    profile_id: str | None = None


@router.post("/my-id", response_model=GetMyIdResponse, summary="Get authenticated user's LinkedIn profile ID")
async def get_my_profile_id(
    request_data: GetMyIdRequest,
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    logger.info("[MESSAGES][MY_ID] Request received to fetch authenticated user's profile ID")

    # Validate API key from header or body
    requesting_user_id = await validate_api_key_from_header_or_body(
        api_key_from_body=request_data.api_key, 
        api_key_header=x_api_key,
        db=db
    )
    user_id_str = str(requesting_user_id)

    mode = "SERVER_CALL" if request_data.server_call else "PROXY"
    logger.info(f"[MESSAGES][MY_ID][{mode}] Executing for user {user_id_str}")

    # Ensure websocket connection for proxy mode
    if not request_data.server_call:
        if not ws_handler or user_id_str not in ws_handler.connection_manager.active_connections or \
           not ws_handler.connection_manager.active_connections[user_id_str]:
            logger.warning(f"[MESSAGES][MY_ID][{mode}] WebSocket not connected for user {user_id_str}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id_str} WebSocket connection not found")

    # Initialize service
    message_service = await get_linkedin_service(db, requesting_user_id, LinkedInMessageService)

    # First: try cache
    cached_id = await get_cached_my_profile_id(db, requesting_user_id)
    if cached_id:
        logger.info(f"[MESSAGES][MY_ID][{mode}] ✓ Method 1: Returning cached profile ID: {cached_id}")
        return GetMyIdResponse(success=True, profile_id=cached_id)

    logger.info(f"[MESSAGES][MY_ID][{mode}] No cached profile ID, attempting to fetch from LinkedIn...")
    
    # Method 2: Try voyagerFeedDashGlobalNavs GraphQL endpoint
    graphql_url = (
        f"{message_service.GRAPHQL_BASE_URL}"
        f"?includeWebMetadata=true&variables=()"
        f"&queryId=voyagerFeedDashGlobalNavs.998834f8daa4cbca25417843e04f16b1"
    )
    logger.info(f"[MESSAGES][MY_ID][{mode}] Method 2: Trying voyagerFeedDashGlobalNavs endpoint: {graphql_url}")

    try:
        for attempt in range(2):
            if request_data.server_call:
                headers = {
                    **message_service.headers,
                    'Referer': 'https://www.linkedin.com/feed/',
                    'x-li-lang': 'en_US',
                    'x-li-track': '{"clientVersion":"1.13.0"}',
                }
                logger.info(f"[MESSAGES][MY_ID][{mode}] Headers count: {len(headers)}")
                response_data = await message_service._make_request(
                    url=graphql_url,
                    method='GET',
                    headers=headers
                )
            else:
                headers = {
                    **message_service.headers,
                    'Referer': 'https://www.linkedin.com/feed/',
                    'x-li-lang': 'en_US',
                    'x-li-track': '{"clientVersion":"1.13.0"}',
                }
                headers.pop('cookie', None)
                logger.info(f"[MESSAGES][MY_ID][{mode}] Proxy Headers count: {len(headers)}")
                proxy_response = await proxy_http_request(
                    ws_handler=ws_handler,
                    user_id=user_id_str,
                    url=graphql_url,
                    method="GET",
                    headers=headers,
                    response_type="json",
                    include_credentials=True,
                    timeout=60.0
                )
                logger.info(f"[MESSAGES][MY_ID][{mode}] Proxy status: {proxy_response['status_code']}")
                if proxy_response['status_code'] >= 400:
                    if proxy_response['status_code'] in (401, 403, 302) and attempt == 0:
                        logger.warning(f"[MESSAGES][MY_ID][{mode}] {proxy_response['status_code']} -> refreshing session and retrying")
                        await refresh_linkedin_session(ws_handler, db, requesting_user_id)
                        message_service = await get_linkedin_service(db, requesting_user_id, LinkedInMessageService)
                        continue
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LinkedIn API returned status {proxy_response['status_code']}")
                response_data = json.loads(proxy_response['body'])

            # Recursively search for Profile type and extract entityUrn
            def find_profile_urn(obj, depth=0):
                """Recursively search for com.linkedin.voyager.dash.identity.profile.Profile type"""
                if depth > 20:  # Prevent infinite recursion
                    return None
                    
                if isinstance(obj, dict):
                    # Check if this object is a Profile type
                    obj_type = obj.get('_type') or obj.get('$type')
                    if obj_type in ['com.linkedin.voyager.dash.identity.profile.Profile', 
                                   'com.linkedin.voyager.identity.profile.Profile']:
                        entity_urn = obj.get('entityUrn')
                        if entity_urn:
                            logger.debug(f"[MESSAGES][MY_ID][{mode}] Found Profile type at depth {depth} with entityUrn: {entity_urn}")
                            return entity_urn
                    
                    # Recursively search all dict values
                    for key, value in obj.items():
                        result = find_profile_urn(value, depth + 1)
                        if result:
                            return result
                            
                elif isinstance(obj, list):
                    # Recursively search all list items
                    for item in obj:
                        result = find_profile_urn(item, depth + 1)
                        if result:
                            return result
                
                return None
            
            try:
                logger.debug(f"[MESSAGES][MY_ID][{mode}] Recursively searching for Profile type in entire response...")
                entity_urn = find_profile_urn(response_data)
                
                if entity_urn:
                    import re as _re
                    m = _re.search(r'urn:li:fsd_profile:([A-Za-z0-9_-]+)', entity_urn)
                    if m:
                        profile_id = m.group(1)
                        logger.info(f"[MESSAGES][MY_ID][{mode}] ✓ Method 2 SUCCESS: Found Profile type and extracted ID: {profile_id}")
                        # Save to cache
                        await set_cached_my_profile_id(db, requesting_user_id, profile_id)
                        return GetMyIdResponse(success=True, profile_id=profile_id)
                    else:
                        logger.warning(f"[MESSAGES][MY_ID][{mode}] Found entityUrn but regex match failed: {entity_urn}")
                else:
                    logger.warning(f"[MESSAGES][MY_ID][{mode}] Method 2 failed: No Profile type found in entire response structure")
                
            except Exception as parse_err:
                logger.error(f"[MESSAGES][MY_ID][{mode}] Method 2 parse error: {parse_err}", exc_info=True)

        # Method 3: Try voyagerIdentityDashProfiles endpoint (fallback)
        logger.info(f"[MESSAGES][MY_ID][{mode}] Method 3: Trying voyagerIdentityDashProfiles endpoint...")
        try:
            identity_url = (
                f"{message_service.GRAPHQL_BASE_URL}"
                f"?variables=(count:1)"
                f"&queryId=voyagerIdentityDashProfiles.4d88ce24d04a54f7dd0542ea529a69d0"
            )
            logger.info(f"[MESSAGES][MY_ID][{mode}] Method 3 URL: {identity_url}")
            
            if request_data.server_call:
                headers = {**message_service.headers, 'Referer': 'https://www.linkedin.com/feed/'}
                identity_response = await message_service._make_request(url=identity_url, method='GET', headers=headers)
            else:
                headers = {**message_service.headers, 'Referer': 'https://www.linkedin.com/feed/'}
                headers.pop('cookie', None)
                proxy_resp = await proxy_http_request(
                    ws_handler=ws_handler, user_id=user_id_str, url=identity_url, method="GET",
                    headers=headers, response_type="json", include_credentials=True, timeout=60.0
                )
                if proxy_resp['status_code'] >= 400:
                    logger.warning(f"[MESSAGES][MY_ID][{mode}] Method 3: Proxy returned {proxy_resp['status_code']}")
                else:
                    identity_response = json.loads(proxy_resp['body'])
            
            # Try to extract profile ID from identity response using same recursive approach
            if identity_response:
                logger.debug(f"[MESSAGES][MY_ID][{mode}] Method 3: Recursively searching for Profile type...")
                entity_urn = find_profile_urn(identity_response)
                
                if entity_urn:
                    import re as _re
                    m = _re.search(r'urn:li:fsd_profile:([A-Za-z0-9_-]+)', entity_urn)
                    if m:
                        profile_id = m.group(1)
                        logger.info(f"[MESSAGES][MY_ID][{mode}] ✓ Method 3 SUCCESS: Found Profile type and extracted ID: {profile_id}")
                        await set_cached_my_profile_id(db, requesting_user_id, profile_id)
                        return GetMyIdResponse(success=True, profile_id=profile_id)
                    else:
                        logger.warning(f"[MESSAGES][MY_ID][{mode}] Method 3: Entity URN found but regex failed: {entity_urn}")
                else:
                    logger.warning(f"[MESSAGES][MY_ID][{mode}] Method 3: No Profile type found in identity response")
        except Exception as identity_err:
            logger.error(f"[MESSAGES][MY_ID][{mode}] Method 3 error: {identity_err}", exc_info=True)

        logger.error(f"[MESSAGES][MY_ID][{mode}] ✗ All methods failed to retrieve profile ID")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not retrieve profile ID. Please ensure LinkedIn session is valid and try again.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[MESSAGES][MY_ID][{mode}] Unexpected error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Execution failed: {str(e)}")


# Endpoint
@router.post("/send", response_model=MessageResponse, summary="Send Direct Message")
async def send_direct_message(
    request_data: SendMessageRequest,
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Send a direct message to a LinkedIn profile.
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False: Transparent HTTP proxy via browser extension
    
    The endpoint automatically handles both new and existing conversations:
    - If an existing conversation is found, it uses the conversation URN
    - If no conversation exists, it creates a new one using hostRecipientUrns
    
    Args:
        request_data: Request parameters including profile_id, message_text, api_key, server_call.
        ws_handler: WebSocket event handler instance.
        db: Database session.
        
    Returns:
        MessageResponse with success status and data.
        
    Raises:
        HTTPException: On authentication failure, timeout, or processing errors.
    """
    # Validate API key from header or body
    try:
        requesting_user_id = await validate_api_key_from_header_or_body(
            api_key_from_body=request_data.api_key, 
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[MESSAGES] API Key validated for user ID: {requesting_user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[MESSAGES] Unexpected error during API key validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during authentication"
        )
    
    # Validate server_call permission
    await validate_server_call_permission(request_data.server_call)
    
    user_id_str = str(requesting_user_id)
    profile_identifier = request_data.profile_id  # Works with both profile_id and profile_identifier
    message_text = request_data.message_text
    
    # Check WebSocket connection if using proxy mode
    if not request_data.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if user_id_str not in ws_handler.connection_manager.active_connections or \
           not ws_handler.connection_manager.active_connections[user_id_str]:
            logger.warning(f"[MESSAGES] User {user_id_str} not connected via WebSocket")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id_str} WebSocket connection not found"
            )
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_data.server_call else "PROXY"
    logger.info(f"[MESSAGES][{mode}] Sending direct message")
    logger.info(f"[MESSAGES][{mode}] Target profile: {profile_identifier}")
    
    try:
        # Get message service
        message_service = await get_linkedin_service(db, requesting_user_id, LinkedInMessageService)
        
        # Try to get cached my profile id to avoid LinkedIn call in service
        cached_my_id = await get_cached_my_profile_id(db, requesting_user_id)
        # Build request details using service (same for both modes)
        # Returns: (url, payload_json, li_mc_cookie)
        url, payload_json, li_mc_cookie = await message_service.prepare_send_message_request(
            profile_identifier,
            message_text,
            my_profile_id=cached_my_id,
        )
        
        # Log if we got li_mc cookie from LinkedIn
        if li_mc_cookie:
            logger.info(f"[MESSAGES][{mode}] Got li_mc cookie from LinkedIn (messaging context)")
        
        # COMMENTED OUT FOR TESTING - Show what would be sent
        logger.info(f"[MESSAGES][{mode}] ========== UNIFIED REQUEST DETAILS ==========")
        logger.info(f"[MESSAGES][{mode}] Target Profile: {profile_identifier}")
        logger.info(f"[MESSAGES][{mode}] Message Text: '{message_text[:100]}{'...' if len(message_text) > 100 else ''}'")
        logger.info(f"[MESSAGES][{mode}] Target URL: {url}")
        logger.info(f"[MESSAGES][{mode}] Method: POST")
        logger.info(f"[MESSAGES][{mode}] Service Headers count: {len(message_service.headers)}")
        logger.info(f"[MESSAGES][{mode}] Payload size: {len(json.dumps(payload_json, ensure_ascii=False))} bytes")
        
        # --- EXECUTE REQUEST (proxy or direct) ---
        if request_data.server_call:
            # Direct server-side call
            try:
                response_data = await message_service._make_request(url, method='POST', json=payload_json)
                logger.info(f"[MESSAGES][{mode}] SERVER CALL completed successfully")
                
            except ValueError as e:
                # Check if it's a profile ID extraction error (likely due to expired LinkedIn session)
                if "extract profile ID" in str(e).lower() or "could not extract" in str(e).lower():
                    logger.error(f"[MESSAGES][{mode}] LinkedIn authentication likely expired: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="LinkedIn session expired or invalid. Please refresh your LinkedIn cookies and try again."
                    )
                raise  # Re-raise if it's a different ValueError
            except Exception as e:
                # Check if it's an HTTP error from LinkedIn
                import httpx
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (302, 403):
                    logger.warning(f"[MESSAGES][{mode}] Detected {e.response.status_code} from LinkedIn. Refreshing session via extension...")
                    await refresh_linkedin_session(ws_handler, db, requesting_user_id)
                    message_service = await get_linkedin_service(db, requesting_user_id, LinkedInMessageService)
                    response_data = await message_service._make_request(url, method='POST', json=payload_json)
                else:
                    raise  # Re-raise other exceptions
        else:
            # Proxy via browser extension (same URL and payload, different execution)
            headers = {
                **message_service.headers,
            }
            # Remove cookie header in proxy mode; browser will attach cookies
            headers.pop("cookie", None)
            
            # Avoid ASCII escaping to match browser behavior for trackingId bytes
            # Use compact JSON format (no spaces) like the test script
            payload_str = json.dumps(payload_json, ensure_ascii=False, separators=(',', ':'))
            logger.info(f"[MESSAGES][{mode}] Payload size: {len(payload_str)} bytes")
            
            # Proxy via browser extension
            proxy_response = await proxy_http_request(
                ws_handler=ws_handler,
                user_id=user_id_str,
                url=url,
                method="POST",
                headers=headers,
                body=payload_str,
                response_type="json",
                include_credentials=True,
                timeout=60.0
            )
            
            logger.info(f"[MESSAGES][{mode}] Received response with status {proxy_response['status_code']}")
            
            # Check for HTTP errors
            if proxy_response['status_code'] >= 400:
                # If unauthorized/redirect, refresh session via extension and retry once
                if proxy_response['status_code'] in (401, 403, 302):
                    logger.warning(f"[MESSAGES][{mode}] Status {proxy_response['status_code']} -> refreshing session and retrying")
                    await refresh_linkedin_session(ws_handler, db, requesting_user_id)
                    # Rebuild service and headers
                    message_service = await get_linkedin_service(db, requesting_user_id, LinkedInMessageService)
                    retry_headers = { **message_service.headers, "Content-Type": "application/json" }
                    retry_headers.pop("cookie", None)
                    payload_str = json.dumps(payload_json, ensure_ascii=False)
                    
                    logger.info(f"[MESSAGES][{mode}] ========== RETRY PROXY REQUEST DETAILS ==========")
                    logger.info(f"[MESSAGES][{mode}] RETRY after session refresh")
                    logger.info(f"[MESSAGES][{mode}] Target URL: {url}")
                    logger.info(f"[MESSAGES][{mode}] Method: POST")
                    logger.info(f"[MESSAGES][{mode}] Retry Headers count: {len(retry_headers)}")
                    logger.info(f"[MESSAGES][{mode}] Retry Payload size: {len(json.dumps(payload_json, ensure_ascii=False))} bytes")
                    logger.info(f"[MESSAGES][{mode}] ================================================")
                    
                    # Retry proxy request
                    proxy_response = await proxy_http_request(
                        ws_handler=ws_handler,
                        user_id=user_id_str,
                        url=url,
                        method="POST",
                        headers=retry_headers,
                        body=payload_str,
                        response_type="json",
                        include_credentials=True,
                        timeout=60.0
                    )
                    logger.info(f"[MESSAGES][{mode}] Retry response status {proxy_response['status_code']}")
                    if proxy_response['status_code'] < 400:
                        # proceed to parse below
                        pass
                    else:
                        error_msg = f"LinkedIn API returned status {proxy_response['status_code']} after refresh"
                        logger.error(f"[MESSAGES][{mode}] {error_msg}")
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=error_msg
                        )
                else:
                    error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
                    logger.error(f"[MESSAGES][{mode}] {error_msg}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=error_msg
                    )
            
            # Parse response body as JSON
            try:
                response_data = json.loads(proxy_response['body'])
            except json.JSONDecodeError as e:
                logger.error(f"[MESSAGES][{mode}] Failed to parse response JSON: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid JSON response from LinkedIn API"
                )
        
        logger.info(f"[MESSAGES][{mode}] Successfully sent direct message")
        return MessageResponse(success=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[MESSAGES][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )

