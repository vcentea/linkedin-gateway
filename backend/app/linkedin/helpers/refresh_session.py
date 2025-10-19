"""
Helper to refresh LinkedIn cookies and CSRF token via the browser extension
and persist them to the database.
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.ws.events import WebSocketEventHandler
from app.ws.state import pending_ws_requests, PendingRequest
from app.ws.message_types import MessageSchema
from app.crud.api_key import update_csrf_token, update_linkedin_cookies

logger = logging.getLogger(__name__)


async def refresh_linkedin_session(
    ws_handler: WebSocketEventHandler,
    db: AsyncSession,
    user_id: UUID,
    timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Ask the extension to refresh LinkedIn cookies + CSRF token and persist them.

    Returns the refreshed data: { 'csrf_token': str, 'cookies': dict }
    """
    user_id_str = str(user_id)

    if not ws_handler or user_id_str not in ws_handler.connection_manager.active_connections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not connected via WebSocket. Cannot refresh LinkedIn session."
        )

    # Prepare WS request
    import asyncio
    from uuid import uuid4
    request_id = f"{user_id_str}_{uuid4()}"
    pending_request = PendingRequest()
    pending_ws_requests[request_id] = pending_request

    message = MessageSchema.request_refresh_linkedin_session_message(request_id)

    try:
        await ws_handler.connection_manager.broadcast_to_user(message, user_id_str)

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

        # Persist to DB
        logger.info(f"[REFRESH_SESSION] Persisting refreshed CSRF token and cookies for user {user_id_str}")
        await update_csrf_token(db, user_id, csrf_token)
        await update_linkedin_cookies(db, user_id, cookies)

        return {"csrf_token": csrf_token, "cookies": cookies}

    finally:
        if request_id in pending_ws_requests:
            del pending_ws_requests[request_id]


