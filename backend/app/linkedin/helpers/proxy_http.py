"""
Generic HTTP proxy helper for LinkedIn API calls via browser extension.

This module provides functionality to proxy HTTP requests through the browser extension,
allowing the backend to leverage the browser's authenticated session with LinkedIn.
"""
import logging
import asyncio
from typing import Dict, Any, Optional
from uuid import uuid4

from fastapi import HTTPException, status

from app.ws.events import WebSocketEventHandler
from app.ws.state import pending_ws_requests, PendingRequest
from app.ws.message_types import MessageSchema

logger = logging.getLogger(__name__)


async def proxy_http_request(
    ws_handler: WebSocketEventHandler,
    user_id: str,
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
    response_type: str = "json",
    include_credentials: bool = True,
    timeout: float = 60.0,
    instance_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute an HTTP request via the browser extension proxy.

    Multi-key support (v1.1.0):
    - If instance_id provided: routes request to that specific browser instance
    - If instance_id not provided: broadcasts to all user's connections (legacy)

    This function sends a REQUEST_PROXY_HTTP message to the extension,
    which executes the request in the browser context with credentials,
    and returns the raw HTTP response.

    The 'cookie' header is automatically removed from the headers dict since
    the browser extension filters it out anyway and relies on include_credentials
    to attach cookies. This prevents conflicts with server-side filtered cookies.

    Args:
        ws_handler: WebSocket event handler instance.
        user_id: User ID to send the request to.
        url: Target URL (absolute or LinkedIn path starting with /).
        method: HTTP method (GET, POST, etc.).
        headers: Request headers (cookie header will be automatically removed).
        body: Request body string (or None).
        response_type: Expected response type ('json', 'text', 'bytes').
        include_credentials: Whether to include cookies (default: True).
        timeout: Maximum time to wait for response in seconds.
        instance_id: Optional browser instance identifier to target specific connection.

    Returns:
        Dict containing:
        {
            'status_code': int,
            'headers': Dict[str, str],
            'body': str  # Raw response body as string
        }

    Raises:
        HTTPException: If WebSocket is not available, user not connected,
                      timeout occurs, or client reports an error.
    """
    # Remove cookie header if present - the extension filters it anyway
    # and relying on include_credentials prevents conflicts
    if headers and 'cookie' in headers:
        headers = {**headers}  # Create a copy to avoid mutating the original
        del headers['cookie']
        logger.debug(f"[PROXY_HTTP] Removed cookie header (will use include_credentials={include_credentials})")
    # Validate WebSocket handler
    if not ws_handler:
        logger.error("[PROXY_HTTP] WebSocket handler not available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebSocket service not available"
        )
    
    # Check WebSocket connection for the instance
    logger.info(f"[PROXY_HTTP] Checking connection for instance {instance_id}")

    if not instance_id:
        logger.error(f"[PROXY_HTTP] No instance_id provided - cannot route request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key does not have an instance_id. Please regenerate your API key."
        )

    # Check if instance is connected
    if not ws_handler.connection_manager.is_instance_connected(instance_id):
        logger.warning(f"[PROXY_HTTP] Instance {instance_id} not connected via WebSocket")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Browser instance {instance_id} not connected. Please check your browser extension."
        )

    target_instance = instance_id
    logger.info(f"[PROXY_HTTP] ✓ Routing to instance: {instance_id}")
    
    # Generate request ID
    request_id = f"{user_id}_{uuid4()}"
    
    # Create proxy request message
    message = MessageSchema.request_proxy_http_message(
        request_id=request_id,
        url=url,
        method=method,
        headers=headers,
        body=body,
        response_type=response_type,
        include_credentials=include_credentials
    )
    
    # Register pending request
    pending_request = PendingRequest()
    pending_ws_requests[request_id] = pending_request
    
    try:
        # Log request details
        url_preview = url[:100] + "..." if len(url) > 100 else url
        logger.info(f"[PROXY_HTTP] Sending {method} request to {url_preview}")
        logger.info(f"[PROXY_HTTP] Request ID: {request_id}, targeting instance: {target_instance or 'all'}")

        # Send request via WebSocket (route to target instance)
        await ws_handler.connection_manager.broadcast_to_user(message, user_id, target_instance)
        
        # Wait for response with timeout
        try:
            logger.info(f"[PROXY_HTTP] Waiting for response (timeout: {timeout}s)...")
            await asyncio.wait_for(pending_request.event.wait(), timeout=timeout)
            logger.info(f"[PROXY_HTTP] Response received for request {request_id}")
        except asyncio.TimeoutError:
            logger.error(f"[PROXY_HTTP] Timeout after {timeout}s for request {request_id}")
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"Extension did not respond within {timeout}s"
            )
        
        # Check for errors
        if pending_request.error:
            logger.error(f"[PROXY_HTTP] Extension reported error: {pending_request.error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Extension failed to execute HTTP request: {str(pending_request.error)}"
            )
        
        # Validate result
        result_data = pending_request.result
        if result_data is None:
            logger.error(f"[PROXY_HTTP] Response received but data is missing")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Received response from extension, but data was missing"
            )
        
        # Validate response structure
        if not isinstance(result_data, dict):
            logger.error(f"[PROXY_HTTP] Invalid response format: {type(result_data)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid response format from extension"
            )
        
        status_code = result_data.get('status_code')
        response_headers = result_data.get('headers', {})
        response_body = result_data.get('body')
        
        if status_code is None or response_body is None:
            logger.error(f"[PROXY_HTTP] Missing required fields in response")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Incomplete response from extension"
            )
        
        logger.info(f"[PROXY_HTTP] Successfully received response: status={status_code}, body_length={len(response_body)}")
        
        return {
            'status_code': status_code,
            'headers': response_headers,
            'body': response_body
        }
        
    finally:
        # Clean up pending request
        if request_id in pending_ws_requests:
            del pending_ws_requests[request_id]
            logger.debug(f"[PROXY_HTTP] Cleaned up pending request {request_id}")

