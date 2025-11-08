"""
WebSocket helper functions specifically for profile-related actions.
"""
from typing import Dict, Any, Optional
import asyncio
from uuid import uuid4

from app.ws.events import WebSocketEventHandler
from app.ws.message_types import MessageType, MessageSchema
from app.ws.state import PendingRequest, pending_ws_requests


async def request_profile_data_via_websocket(
    ws_event_handler: WebSocketEventHandler,
    user_id: str, # User ID who has the active LinkedIn WebSocket connection
    profile_id: str, # LinkedIn profile ID/URN/URL to fetch data for
    request_type: str = "basic_info", # e.g., "basic_info", "vanity_name"
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Sends a request via WebSocket to the frontend to fetch profile data.

    Args:
        ws_event_handler: The WebSocket event handler instance.
        user_id: The ID of the user whose frontend session should be used.
        profile_id: The LinkedIn identifier for the profile.
        request_type: Specific type of data requested (e.g., 'vanity_name').
        timeout: How long to wait for a response in seconds.

    Returns:
        A dictionary containing the fetched profile data.

    Raises:
        HTTPException: If the target user is not connected via WebSocket.
        TimeoutError: If the frontend doesn't respond within the timeout.
        Exception: If the frontend reports an error or another issue occurs.
    """
    # Check if the target user is connected
    if user_id not in ws_event_handler.connection_manager.active_connections or \
       not ws_event_handler.connection_manager.active_connections[user_id]:
        # Use HTTPException for API layer handling
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} is not connected via WebSocket."
        )

    request_id = f"{user_id}_profile_{request_type}_{uuid4()}"

    # Create the request message
    message = MessageSchema.request_profile_data_message(
        profile_id=profile_id,
        request_type=request_type,
        request_id=request_id
    )

    # Create and store the pending request state
    pending_request = PendingRequest()
    pending_ws_requests[request_id] = pending_request

    try:
        # Send the request to the user's WebSocket connection(s)
        await ws_event_handler.connection_manager.broadcast_to_user(message, user_id)

        # Wait for the response
        try:
            await asyncio.wait_for(pending_request.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Profile data request ({request_type}) for {profile_id} timed out after {timeout} seconds")

        # Check if the frontend reported an error
        if pending_request.error:
            raise pending_request.error

        # Return the successful result
        if pending_request.result is None:
             raise Exception(f"Received empty result for profile data request {request_id}")
        return pending_request.result

    finally:
        # Clean up the pending request state
        if request_id in pending_ws_requests:
            del pending_ws_requests[request_id] 