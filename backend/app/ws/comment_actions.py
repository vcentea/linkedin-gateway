"""
Helper functions for comment-related WebSocket actions.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.ws.events import WebSocketEventHandler
from app.ws.state import pending_ws_requests, PendingRequest
from app.ws.message_types import MessageSchema

logger = logging.getLogger(__name__)

async def request_commenters_via_websocket(
    user_id: UUID,
    post_url: str,
    ws_handler: WebSocketEventHandler,
    request_id: str,
    start: int = 0,
    count: int = 10,
    num_replies: int = 1,
    timeout: float = 60.0
) -> List[Dict[str, Any]]:
    """
    Send a request to fetch commenters for a LinkedIn post via WebSocket and await the response.
    
    Args:
        user_id: User ID for the request.
        post_url: URL of the LinkedIn post to fetch commenters for.
        ws_handler: WebSocket event handler instance.
        request_id: Unique identifier for this request.
        start: Starting index for pagination.
        count: Number of comments to fetch.
        num_replies: Number of replies to fetch per comment.
        timeout: Maximum time to wait for response in seconds.
        
    Returns:
        List of commenter data dictionaries.
        
    Raises:
        asyncio.TimeoutError: If the response is not received within the timeout.
        Exception: If the client reports an error.
        ValueError: If the response data is missing or invalid.
    """
    user_id_str = str(user_id)
    
    # Create message
    message = MessageSchema.request_get_commenters_message(
        request_id=request_id,
        post_url=post_url,
        start=start,
        count=count,
        num_replies=num_replies
    )
    
    # Create pending request object
    pending_request = PendingRequest()
    pending_ws_requests[request_id] = pending_request
    
    try:
        # Send request via WebSocket
        logger.info(f"Sending commenter request via WebSocket (ID: {request_id}) to user {user_id_str}")
        await ws_handler.connection_manager.broadcast_to_user(message, user_id_str)
        
        # Wait for response with timeout
        logger.info(f"Waiting for commenter response (ID: {request_id}) from user {user_id_str}...")
        await asyncio.wait_for(pending_request.event.wait(), timeout=timeout)
        
        # Check for reported errors
        if pending_request.error:
            logger.error(f"Client reported error for commenter request {request_id}: {pending_request.error}")
            raise pending_request.error
        
        # Process result
        result_data = pending_request.result
        if result_data is None:
            logger.warning(f"Received response for commenters request {request_id} but result data is None")
            # Return empty list if data is missing but no error was reported
            return []
            
        return result_data
        
    finally:
        # Always clean up the pending request
        if request_id in pending_ws_requests:
            del pending_ws_requests[request_id]
            logger.debug(f"Cleaned up pending commenters request {request_id}") 