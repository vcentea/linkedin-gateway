"""
Helper to refresh LinkedIn cookies and CSRF token via the browser extension
and persist them to the database.

Multi-key support (v1.1.0):
- Refreshes credentials for a specific API key (browser instance)
- Routes refresh request to the correct WebSocket connection
- Updates only the targeted API key's credentials
"""
import logging
from typing import Dict, Any, Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.ws.events import WebSocketEventHandler
from app.ws.state import pending_ws_requests, PendingRequest
from app.ws.message_types import MessageSchema
from app.db.models.api_key import APIKey

logger = logging.getLogger(__name__)


async def refresh_linkedin_session(
    ws_handler: WebSocketEventHandler,
    db: AsyncSession,
    api_key_or_user_id: Union[APIKey, UUID],
    timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Ask the extension to refresh LinkedIn cookies + CSRF token and persist them.

    Multi-key support (v1.1.0):
    - If APIKey object: refreshes that specific key's credentials, routes to its instance
    - If UUID: legacy mode, refreshes primary key for that user (backward compatibility)

    Args:
        ws_handler: WebSocket event handler
        db: Database session
        api_key_or_user_id: APIKey object (multi-key) or user UUID (legacy)
        timeout: Timeout in seconds

    Returns:
        Dict with refreshed data: { 'csrf_token': str, 'cookies': dict }
    """
    # Multi-key mode vs legacy mode detection
    if isinstance(api_key_or_user_id, APIKey):
        # Multi-key mode: refresh specific API key
        api_key = api_key_or_user_id
        user_id_str = str(api_key.user_id)
        instance_id = api_key.instance_id
        target_key_id = api_key.id

        logger.info(f"[REFRESH_SESSION][MULTI-KEY] Refreshing credentials for API key {target_key_id} (prefix: {api_key.prefix}), instance: {instance_id or 'default'}")
    else:
        # Legacy mode: refresh primary key for user
        user_id = api_key_or_user_id
        user_id_str = str(user_id)
        instance_id = None
        target_key_id = None

        logger.info(f"[REFRESH_SESSION][LEGACY] Refreshing primary key for user {user_id_str}")

    # Check WebSocket connection
    if not ws_handler or user_id_str not in ws_handler.connection_manager.active_connections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not connected via WebSocket. Cannot refresh LinkedIn session."
        )

    # Smart instance routing with fallback (for backward compatibility)
    target_instance = None
    if instance_id:
        if instance_id in ws_handler.connection_manager.active_connections[user_id_str]:
            # Requested instance is connected - use it
            target_instance = instance_id
            logger.info(f"[REFRESH_SESSION] Routing to requested instance: {instance_id}")
        elif "default" in ws_handler.connection_manager.active_connections[user_id_str]:
            # Fallback to "default" for old extensions
            target_instance = "default"
            logger.warning(f"[REFRESH_SESSION] Instance {instance_id} not connected, falling back to 'default' (old extension)")
        else:
            # Fallback to any available instance
            available_instances = list(ws_handler.connection_manager.active_connections[user_id_str].keys())
            if available_instances:
                target_instance = available_instances[0]
                logger.warning(f"[REFRESH_SESSION] Instance {instance_id} not connected, falling back to '{target_instance}'")
            else:
                # No instances at all
                logger.error(f"[REFRESH_SESSION] No instances available for user {user_id_str}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No WebSocket connections available for user"
                )
    else:
        # Legacy mode: no instance_id, broadcast to all
        target_instance = None
        logger.info(f"[REFRESH_SESSION] No instance_id specified, broadcasting to all connections")

    # Prepare WS request
    import asyncio
    from uuid import uuid4
    request_id = f"{user_id_str}_{uuid4()}"
    pending_request = PendingRequest()
    pending_ws_requests[request_id] = pending_request

    message = MessageSchema.request_refresh_linkedin_session_message(request_id)

    try:
        # Send request to target instance
        await ws_handler.connection_manager.broadcast_to_user(message, user_id_str, target_instance)
        logger.info(f"[REFRESH_SESSION] Sent refresh request to instance: {target_instance or 'all'}")

        try:
            await asyncio.wait_for(pending_request.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="Extension did not respond to refresh session request"
            )

        if pending_request.error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Extension failed to refresh session: {pending_request.error}"
            )

        result = pending_request.result or {}
        csrf_token: Optional[str] = result.get("csrf_token")
        cookies: Optional[Dict[str, str]] = result.get("cookies")

        if not csrf_token or not cookies:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Extension returned incomplete refresh data"
            )

        # Persist to DB - update specific key or primary key
        if target_key_id:
            # Multi-key mode: update the specific API key
            logger.info(f"[REFRESH_SESSION][MULTI-KEY] Updating API key {target_key_id}")
            api_key.csrf_token = csrf_token
            api_key.linkedin_cookies = cookies
            db.add(api_key)
            await db.flush()
        else:
            # Legacy mode: update primary key via CRUD functions
            logger.info(f"[REFRESH_SESSION][LEGACY] Updating primary key for user {user_id_str}")
            from app.crud.api_key import update_csrf_token, update_linkedin_cookies
            await update_csrf_token(db, UUID(user_id_str), csrf_token)
            await update_linkedin_cookies(db, UUID(user_id_str), cookies)

        logger.info(f"[REFRESH_SESSION] Successfully refreshed and persisted credentials")
        return {"csrf_token": csrf_token, "cookies": cookies}

    finally:
        if request_id in pending_ws_requests:
            del pending_ws_requests[request_id]


