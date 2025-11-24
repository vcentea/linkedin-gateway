"""
API endpoint for LinkedIn connection request operations.

This endpoint supports two execution modes:
1. server_call=True: Execute LinkedIn API call directly from backend
2. proxy=True: Execute via browser extension as transparent HTTP proxy
"""
import logging
import json
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.ws.events import WebSocketEventHandler
from app.api.dependencies import get_ws_handler
from app.auth.dependencies import validate_api_key_from_header_or_body
from app.linkedin.services.connections import LinkedInConnectionService
from app.linkedin.helpers import get_linkedin_service, proxy_http_request, refresh_linkedin_session
from app.api.v1.server_validation import validate_server_call_permission
from app.schemas.connection import GetConnectionsRequest, GetConnectionsResponse, ConnectionDetail

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/connections",
    tags=["connections"],
)


# Request/Response models
class SimpleConnectionRequest(BaseModel):
    """Request model for simple connection request."""
    profile_id: str = Field(
        ..., 
        description="LinkedIn profile ID or profile URL (e.g., 'john-doe-123' or 'https://www.linkedin.com/in/john-doe')",
        alias="profile_identifier"
    )
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use proxy via extension")
    
    class Config:
        populate_by_name = True  # Allows both profile_id and profile_identifier


class ConnectionWithMessageRequest(BaseModel):
    """Request model for connection request with message."""
    profile_id: str = Field(
        ..., 
        description="LinkedIn profile ID or profile URL (e.g., 'john-doe-123' or 'https://www.linkedin.com/in/john-doe')",
        alias="profile_identifier"
    )
    message: str = Field(..., description="Custom message to include with connection request")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use proxy via extension")
    
    class Config:
        populate_by_name = True  # Allows both profile_id and profile_identifier


class ConnectionResponse(BaseModel):
    """Response model for connection request operations."""
    success: bool


# Endpoints
@router.post("/simple", response_model=ConnectionResponse, summary="Send Simple Connection Request")
async def send_simple_connection_request(
    request_data: SimpleConnectionRequest,
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Send a simple connection request without a message.
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False: Transparent HTTP proxy via browser extension
    
    Args:
        request_data: Request parameters including profile_id, api_key, server_call.
        ws_handler: WebSocket event handler instance.
        db: Database session.
        
    Returns:
        ConnectionResponse with success status and data.
        
    Raises:
        HTTPException: On authentication failure, timeout, or processing errors.
    """
    # Validate API key (returns APIKey object v1.1.0)
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_data.api_key, 
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[CONNECTIONS] API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[CONNECTIONS] Unexpected error during API key validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during authentication"
        )
    
    # Validate server_call permission
    await validate_server_call_permission(request_data.server_call)
    
    user_id_str = str(api_key.user_id)
    profile_identifier = request_data.profile_id  # Works with both profile_id and profile_identifier
    
    # Check WebSocket connection if using proxy mode
    if not request_data.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        # Check if user has any active WebSocket connections

        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[CONNECTIONS] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Browser instance not connected. Please check your extension."
            )
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_data.server_call else "PROXY"
    logger.info(f"[CONNECTIONS][{mode}] Sending simple connection request")
    logger.info(f"[CONNECTIONS][{mode}] Target profile: {profile_identifier}")
    
    try:
        # Get connection service (uses CSRF/cookies from api_key object)
        connection_service = await get_linkedin_service(db, api_key, LinkedInConnectionService)
        
        # --- EXECUTE REQUEST (proxy or direct) ---
        if request_data.server_call:
            # Direct server-side call
            try:
                response_data = await connection_service.send_simple_connection_request(profile_identifier)
            except ValueError as e:
                # Check if it's a profile ID extraction error (likely due to expired LinkedIn session)
                if "extract profile ID" in str(e).lower() or "could not extract" in str(e).lower():
                    logger.error(f"[CONNECTIONS][{mode}] LinkedIn authentication likely expired: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="LinkedIn session expired or invalid. Please refresh your LinkedIn cookies and try again."
                    )
                raise  # Re-raise if it's a different ValueError
            except Exception as e:
                # Check if it's an HTTP error from LinkedIn
                import httpx
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 400:
                    try:
                        error_data = e.response.json()
                        error_code = error_data.get('data', {}).get('code', '')
                        if error_code == 'CANT_RESEND_YET':
                            logger.warning(f"[CONNECTIONS][{mode}] Connection request already sent to this profile")
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail="Connection request already sent to this profile. Please wait before sending again."
                            )
                    except (ValueError, KeyError, AttributeError):
                        pass
                # Handle 302/403 as session invalid -> trigger refresh and retry once
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (302, 403):
                    logger.warning(f"[CONNECTIONS][{mode}] Detected {e.response.status_code} from LinkedIn. Refreshing session via extension...")
                    # Request extension to refresh cookies + csrf, persist, and rebuild service
                    await refresh_linkedin_session(ws_handler, db, api_key)
                    connection_service = await get_linkedin_service(db, requesting_user_id, LinkedInConnectionService)
                    # Retry once
                    response_data = await connection_service.send_simple_connection_request(profile_identifier)
                    # If successful, continue
                else:
                    raise  # Re-raise other exceptions
        else:
            # For proxy mode, we need to extract profile ID first
            from app.linkedin.utils.profile_id_extractor import extract_profile_id
            profile_id = await extract_profile_id(
                profile_input=profile_identifier,
                headers=connection_service.headers,
                timeout=connection_service.TIMEOUT
            )
            
            # Build URL and payload for proxy
            url = (
                f"{connection_service.VOYAGER_BASE_URL}/voyagerRelationshipsDashMemberRelationships"
                f"?action=verifyQuotaAndCreateV2"
                f"&decorationId=com.linkedin.voyager.dash.deco.relationships.InvitationCreationResultWithInvitee-2"
            )
            
            payload = {
                "invitee": {
                    "inviteeUnion": {
                        "memberProfile": f"urn:li:fsd_profile:{profile_id}"
                    }
                }
            }
            
            headers = {
                **connection_service.headers,
                "Content-Type": "application/json",
            }
            
            # Proxy via browser extension
            proxy_response = await proxy_http_request(
                ws_handler=ws_handler,
                user_id=user_id_str,
                url=url,
                method="POST",
                headers=headers,
                body=json.dumps(payload),
                response_type="json",
                include_credentials=True,
                timeout=60.0,
                instance_id=api_key.instance_id  # Route to specific instance
            )
            
            logger.info(f"[CONNECTIONS][{mode}] Received response with status {proxy_response['status_code']}")
            
            # Check for HTTP errors
            if proxy_response['status_code'] >= 400:
                # Try to parse error response for specific LinkedIn errors
                try:
                    error_data = json.loads(proxy_response['body'])
                    error_code = error_data.get('data', {}).get('code', '')
                    
                    # Handle specific LinkedIn error codes
                    if error_code == 'CANT_RESEND_YET':
                        logger.warning(f"[CONNECTIONS][{mode}] Connection request already sent to this profile")
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Connection request already sent to this profile. Please wait before sending again."
                        )
                except (json.JSONDecodeError, KeyError):
                    pass  # If we can't parse the error, use generic message below
                
                error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
                logger.error(f"[CONNECTIONS][{mode}] {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=error_msg
                )
            
            # Parse response body as JSON
            try:
                response_data = json.loads(proxy_response['body'])
            except json.JSONDecodeError as e:
                logger.error(f"[CONNECTIONS][{mode}] Failed to parse response JSON: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid JSON response from LinkedIn API"
                )
        
        logger.info(f"[CONNECTIONS][{mode}] Successfully sent simple connection request")
        return ConnectionResponse(success=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[CONNECTIONS][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.post("/with-message", response_model=ConnectionResponse, summary="Send Connection Request With Message")
async def send_connection_request_with_message(
    request_data: ConnectionWithMessageRequest,
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Send a connection request with a custom message.
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False: Transparent HTTP proxy via browser extension
    
    Args:
        request_data: Request parameters including profile_id, message, api_key, server_call.
        ws_handler: WebSocket event handler instance.
        db: Database session.
        
    Returns:
        ConnectionResponse with success status and data.
        
    Raises:
        HTTPException: On authentication failure, timeout, or processing errors.
    """
    # Validate API key (returns APIKey object v1.1.0)
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_data.api_key, 
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[CONNECTIONS] API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[CONNECTIONS] Unexpected error during API key validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during authentication"
        )
    
    # Validate server_call permission
    await validate_server_call_permission(request_data.server_call)
    
    user_id_str = str(api_key.user_id)
    profile_identifier = request_data.profile_id  # Works with both profile_id and profile_identifier
    message = request_data.message
    
    # Check WebSocket connection if using proxy mode
    if not request_data.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[CONNECTIONS] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Browser instance not connected. Please check your extension."
            )
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_data.server_call else "PROXY"
    logger.info(f"[CONNECTIONS][{mode}] Sending connection request with message")
    logger.info(f"[CONNECTIONS][{mode}] Target profile: {profile_identifier}")
    
    try:
        # Get connection service (uses CSRF/cookies from api_key object)
        connection_service = await get_linkedin_service(db, api_key, LinkedInConnectionService)
        
        # --- EXECUTE REQUEST (proxy or direct) ---
        if request_data.server_call:
            # Direct server-side call
            try:
                response_data = await connection_service.send_connection_request_with_message(profile_identifier, message)
            except ValueError as e:
                # Check if it's a profile ID extraction error (likely due to expired LinkedIn session)
                if "extract profile ID" in str(e).lower() or "could not extract" in str(e).lower():
                    logger.error(f"[CONNECTIONS][{mode}] LinkedIn authentication likely expired: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="LinkedIn session expired or invalid. Please refresh your LinkedIn cookies and try again."
                    )
                raise  # Re-raise if it's a different ValueError
            except Exception as e:
                # Check if it's an HTTP error from LinkedIn
                import httpx
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 400:
                    try:
                        error_data = e.response.json()
                        error_code = error_data.get('data', {}).get('code', '')
                        if error_code == 'CANT_RESEND_YET':
                            logger.warning(f"[CONNECTIONS][{mode}] Connection request already sent to this profile")
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail="Connection request already sent to this profile. Please wait before sending again."
                            )
                    except (ValueError, KeyError, AttributeError):
                        pass
                # Handle 302/403 as session invalid -> trigger refresh and retry once
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (302, 403):
                    logger.warning(f"[CONNECTIONS][{mode}] Detected {e.response.status_code} from LinkedIn. Refreshing session via extension...")
                    await refresh_linkedin_session(ws_handler, db, api_key)
                    connection_service = await get_linkedin_service(db, requesting_user_id, LinkedInConnectionService)
                    response_data = await connection_service.send_connection_request_with_message(profile_identifier, message)
                else:
                    raise  # Re-raise other exceptions
        else:
            # For proxy mode, we need to extract profile ID first
            from app.linkedin.utils.profile_id_extractor import extract_profile_id
            profile_id = await extract_profile_id(
                profile_input=profile_identifier,
                headers=connection_service.headers,
                timeout=connection_service.TIMEOUT
            )
            
            # Build URL and payload for proxy
            url = (
                f"{connection_service.VOYAGER_BASE_URL}/voyagerRelationshipsDashMemberRelationships"
                f"?action=verifyQuotaAndCreateV2"
                f"&decorationId=com.linkedin.voyager.dash.deco.relationships.InvitationCreationResultWithInvitee-2"
            )
            
            payload = {
                "invitee": {
                    "inviteeUnion": {
                        "memberProfile": f"urn:li:fsd_profile:{profile_id}"
                    }
                },
                "customMessage": message
            }
            
            headers = {
                **connection_service.headers,
                "Content-Type": "application/json",
            }
            
            # Proxy via browser extension
            proxy_response = await proxy_http_request(
                ws_handler=ws_handler,
                user_id=user_id_str,
                url=url,
                method="POST",
                headers=headers,
                body=json.dumps(payload),
                response_type="json",
                include_credentials=True,
                timeout=60.0,
                instance_id=api_key.instance_id  # Route to specific instance
            )
            
            logger.info(f"[CONNECTIONS][{mode}] Received response with status {proxy_response['status_code']}")
            
            # Check for HTTP errors
            if proxy_response['status_code'] >= 400:
                # Try to parse error response for specific LinkedIn errors
                try:
                    error_data = json.loads(proxy_response['body'])
                    error_code = error_data.get('data', {}).get('code', '')
                    
                    # Handle specific LinkedIn error codes
                    if error_code == 'CANT_RESEND_YET':
                        logger.warning(f"[CONNECTIONS][{mode}] Connection request already sent to this profile")
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Connection request already sent to this profile. Please wait before sending again."
                        )
                except (json.JSONDecodeError, KeyError):
                    pass  # If we can't parse the error, use generic message below
                
                error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
                logger.error(f"[CONNECTIONS][{mode}] {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=error_msg
                )
            
            # Parse response body as JSON
            try:
                response_data = json.loads(proxy_response['body'])
            except json.JSONDecodeError as e:
                logger.error(f"[CONNECTIONS][{mode}] Failed to parse response JSON: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid JSON response from LinkedIn API"
                )
        
        logger.info(f"[CONNECTIONS][{mode}] Successfully sent connection request with message")
        return ConnectionResponse(success=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[CONNECTIONS][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.post("/list", response_model=GetConnectionsResponse, summary="Get Connections List")
async def get_connections_list(
    request_data: GetConnectionsRequest,
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Fetch list of LinkedIn connections with pagination.
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False: Transparent HTTP proxy via browser extension
    
    Args:
        request_data: Request parameters including start_index, count, api_key, server_call.
        ws_handler: WebSocket event handler instance.
        db: Database session.
        
    Returns:
        GetConnectionsResponse with list of connections and metadata.
        
    Raises:
        HTTPException: On authentication failure, timeout, or processing errors.
    """
    # Validate API key (returns APIKey object v1.1.0)
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_data.api_key, 
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[CONNECTIONS_LIST] API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[CONNECTIONS_LIST] Unexpected error during API key validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during authentication"
        )
    
    # Validate server_call permission
    await validate_server_call_permission(request_data.server_call)
    
    user_id_str = str(api_key.user_id)
    start_index = request_data.start_index
    count = request_data.count
    
    # Check WebSocket connection if using proxy mode
    if not request_data.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[CONNECTIONS_LIST] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Browser instance not connected. Please check your extension."
            )
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_data.server_call else "PROXY"
    logger.info(f"[CONNECTIONS_LIST][{mode}] Fetching connections list")
    logger.info(f"[CONNECTIONS_LIST][{mode}] Parameters - start_index: {start_index}, count: {count}")
    
    try:
        # Get connection service (uses CSRF/cookies from api_key object)
        connection_service = await get_linkedin_service(db, api_key, LinkedInConnectionService)
        
        # --- EXECUTE REQUEST (proxy or direct) ---
        if request_data.server_call:
            # Direct server-side call
            try:
                connections_data = await connection_service.fetch_connections_list(start_index)
            except Exception as e:
                # Check if it's an HTTP error from LinkedIn
                import httpx
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (302, 403):
                    logger.warning(f"[CONNECTIONS_LIST][{mode}] Detected {e.response.status_code} from LinkedIn. Refreshing session via extension...")
                    # Request extension to refresh cookies + csrf, persist, and rebuild service
                    await refresh_linkedin_session(ws_handler, db, api_key)
                    connection_service = await get_linkedin_service(db, api_key, LinkedInConnectionService)
                    # Retry once
                    connections_data = await connection_service.fetch_connections_list(start_index)
                else:
                    raise  # Re-raise other exceptions
        else:
            # For proxy mode, we need to build URL and payload
            url = connection_service._build_connections_url(start_index)
            payload = connection_service._build_connections_payload(start_index)
            
            headers = {
                **connection_service.headers,
                "Content-Type": "application/json",
            }
            
            # Proxy via browser extension
            proxy_response = await proxy_http_request(
                ws_handler=ws_handler,
                user_id=user_id_str,
                url=url,
                method="POST",
                headers=headers,
                body=json.dumps(payload),
                response_type="text",  # RSC returns text
                include_credentials=True,
                timeout=60.0,
                instance_id=api_key.instance_id  # Route to specific instance
            )
            
            logger.info(f"[CONNECTIONS_LIST][{mode}] Received response with status {proxy_response['status_code']}")
            
            # Check for HTTP errors
            if proxy_response['status_code'] >= 400:
                error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
                logger.error(f"[CONNECTIONS_LIST][{mode}] {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=error_msg
                )
            
            # Parse the RSC response
            try:
                response_text = proxy_response['body']
                connections_data = connection_service._parse_connections_response(response_text)
            except Exception as e:
                logger.error(f"[CONNECTIONS_LIST][{mode}] Failed to parse response: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to parse LinkedIn connections response"
                )
        
        # Limit to requested count
        connections_data = connections_data[:count]
        
        # Validate/parse the result into the Pydantic models
        validated_connections = [ConnectionDetail(**item) for item in connections_data]
        
        logger.info(f"[CONNECTIONS_LIST][{mode}] Successfully fetched {len(validated_connections)} connections")
        return GetConnectionsResponse(
            data=validated_connections,
            total=len(validated_connections),
            start_index=start_index
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[CONNECTIONS_LIST][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )

