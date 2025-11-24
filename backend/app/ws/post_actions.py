"""
Helper functions for post-related WebSocket actions.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.ws.events import WebSocketEventHandler
from app.ws.state import pending_ws_requests, PendingRequest
from app.ws.message_types import MessageSchema

logger = logging.getLogger(__name__)

async def request_posts_via_websocket(
    user_id: UUID,
    ws_handler: WebSocketEventHandler,
    request_id: str,
    start_index: int = 0,
    count: int = 10,
    timeout: float = 60.0
) -> List[Dict[str, Any]]:
    """
    Send a request to fetch posts from LinkedIn feed via WebSocket and await the response.
    
    Args:
        user_id: User ID for the request.
        ws_handler: WebSocket event handler instance.
        request_id: Unique identifier for this request.
        start_index: Starting index for pagination.
        count: Number of posts to fetch.
        timeout: Maximum time to wait for response in seconds.
        
    Returns:
        List of post data dictionaries.
        
    Raises:
        asyncio.TimeoutError: If the response is not received within the timeout.
        Exception: If the client reports an error.
        ValueError: If the response data is missing or invalid.
    """
    user_id_str = str(user_id)
    
    # Create message
    message = MessageSchema.request_get_posts_message(
        start_index=start_index,
        count=count,
        request_id=request_id
    )
    
    # Create pending request object
    pending_request = PendingRequest()
    pending_ws_requests[request_id] = pending_request
    
    try:
        # Send request via WebSocket
        logger.info(f"Sending post request via WebSocket (ID: {request_id}) to user {user_id_str}")
        await ws_handler.connection_manager.broadcast_to_user(message, user_id_str)
        
        # Wait for response with timeout
        logger.info(f"Waiting for post response (ID: {request_id}) from user {user_id_str}...")
        await asyncio.wait_for(pending_request.event.wait(), timeout=timeout)
        
        # Check for reported errors
        if pending_request.error:
            logger.error(f"Client reported error for post request {request_id}: {pending_request.error}")
            raise pending_request.error
        
        # Process result
        result_data = pending_request.result
        if result_data is None:
            logger.warning(f"Received response for post request {request_id} but result data is None")
            raise ValueError("Received response from client, but data was missing")
            
        return result_data
        
    finally:
        # Always clean up the pending request
        if request_id in pending_ws_requests:
            del pending_ws_requests[request_id]
            logger.debug(f"Cleaned up pending post request {request_id}") 