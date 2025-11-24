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

    # Validate API key from header or body (returns APIKey object v1.1.0)
    api_key = await validate_api_key_from_header_or_body(
        api_key_from_body=request_data.api_key, 
        api_key_header=x_api_key,
        db=db
    )
    user_id_str = str(api_key.user_id)

    mode = "SERVER_CALL" if request_data.server_call else "PROXY"
    logger.info(f"[MESSAGES][MY_ID][{mode}] Executing for user {user_id_str}")

    # Ensure websocket connection for proxy mode
    if not request_data.server_call:
        if not ws_handler or not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[MESSAGES][MY_ID][{mode}] Instance {api_key.instance_id} not connected")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")

    # Initialize service (uses CSRF/cookies from api_key object)
    message_service = await get_linkedin_service(db, api_key, LinkedInMessageService)

    # Use the robust utility function (extracted from this endpoint's original logic)
    from app.linkedin.utils.my_profile_id import get_my_profile_id_with_fallbacks
    try:
        profile_id = await get_my_profile_id_with_fallbacks(
            db=db,
            user_id=api_key.user_id,
            service=message_service,
            ws_handler=ws_handler if not request_data.server_call else None,
            use_proxy=not request_data.server_call
        )
        return GetMyIdResponse(success=True, profile_id=profile_id)

    except ValueError as e:
        logger.error(f"[MESSAGES][MY_ID][{mode}] Could not retrieve profile ID: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
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
    # Validate API key from header or body (returns APIKey object v1.1.0)
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_data.api_key, 
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[MESSAGES] API Key validated for user ID: {api_key.user_id}")
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
    
    user_id_str = str(api_key.user_id)
    profile_identifier = request_data.profile_id  # Works with both profile_id and profile_identifier
    message_text = request_data.message_text
    
    # Check WebSocket connection if using proxy mode
    if not request_data.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        # Check if user has any active WebSocket connections

        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[MESSAGES] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Browser instance not connected. Please check your extension."
            )
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_data.server_call else "PROXY"
    logger.info(f"[MESSAGES][{mode}] Sending direct message")
    logger.info(f"[MESSAGES][{mode}] Target profile: {profile_identifier}")
    
    try:
        # Get message service (uses CSRF/cookies from api_key object)
        message_service = await get_linkedin_service(db, api_key, LinkedInMessageService)

        # Extract TARGET profile ID using the SAME robust method as /utils/extract-profile-id endpoint
        logger.info(f"[MESSAGES][{mode}] Extracting target profile ID from: {profile_identifier}")
        from app.api.v1.utils import _extract_vanity_name_from_url, _extract_profile_id_from_html_content
        import httpx

        vanity_name = await _extract_vanity_name_from_url(profile_identifier)
        profile_url = f"https://www.linkedin.com/in/{vanity_name}/"

        logger.info(f"[MESSAGES][{mode}] Fetching profile HTML for: {profile_url}")
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(profile_url, headers=message_service.headers)
            response.raise_for_status()
            html = response.text

        target_profile_id = await _extract_profile_id_from_html_content(html, vanity_name)
        logger.info(f"[MESSAGES][{mode}] ✓ Extracted target profile ID: {target_profile_id}")

        # Get my profile ID using the robust utility (same as /my-id endpoint)
        from app.linkedin.utils.my_profile_id import get_my_profile_id_with_fallbacks
        my_profile_id = await get_my_profile_id_with_fallbacks(
            db=db,
            user_id=api_key.user_id,
            service=message_service,
            ws_handler=ws_handler if not request_data.server_call else None,
            use_proxy=not request_data.server_call
        )

        # Build request details using service (same for both modes)
        # Returns: (url, payload_json, li_mc_cookie)
        # Pass the already-extracted target_profile_id instead of profile_identifier URL
        url, payload_json, li_mc_cookie = await message_service.prepare_send_message_request(
            target_profile_id,  # Pass extracted ID, not URL
            message_text,
            my_profile_id=my_profile_id,
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
                    await refresh_linkedin_session(ws_handler, db, api_key)
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
                timeout=60.0,
                instance_id=api_key.instance_id  # Route to specific instance
            )
            
            logger.info(f"[MESSAGES][{mode}] Received response with status {proxy_response['status_code']}")
            
            # Check for HTTP errors
            if proxy_response['status_code'] >= 400:
                # If unauthorized/redirect, refresh session via extension and retry once
                if proxy_response['status_code'] in (401, 403, 302):
                    logger.warning(f"[MESSAGES][{mode}] Status {proxy_response['status_code']} -> refreshing session and retrying")
                    await refresh_linkedin_session(ws_handler, db, api_key)
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
                        timeout=60.0,
                        instance_id=api_key.instance_id  # Route to specific instance
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

