"""
API endpoints for WebSocket-related functionality.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.db.models.user import User


# Models for request/response
class NotificationRequest(BaseModel):
    """Request model for sending a notification."""
    title: str
    message: str
    level: str = "info"
    data: Optional[Dict[str, Any]] = None


class NotificationBroadcastRequest(BaseModel):
    """Request model for broadcasting a notification."""
    title: str
    message: str
    level: str = "info"
    data: Optional[Dict[str, Any]] = None


class UserNotificationRequest(BaseModel):
    """Request model for sending a notification to multiple users."""
    title: str
    message: str
    user_ids: List[str]
    level: str = "info"
    data: Optional[Dict[str, Any]] = None


class StatusResponse(BaseModel):
    """Response model for status endpoints."""
    status: str
    details: Optional[Dict[str, Any]] = None


# Initialize router
router = APIRouter(
    prefix="/ws",
    tags=["websocket"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/status", response_model=Dict[str, Any])
async def get_ws_status(current_user: User = Depends(get_current_user)):
    """
    Get the current WebSocket connection status.
    
    Requires authentication. Admin users can see all connections.
    Regular users will only see their own connection status.
    """
    from main import ws_manager
    
    # Check if user is admin
    is_admin = getattr(current_user, "is_admin", False)
    
    if is_admin:
        # Return full status for admins
        return {
            "connections": ws_manager.get_total_connections(),
            "users": len(ws_manager.active_connections),
            "user_connections": {
                user_id: len(connections) 
                for user_id, connections in ws_manager.active_connections.items()
            }
        }
    else:
        # Return only user's own status
        return {
            "connected": current_user.id in ws_manager.active_connections,
            "connections": ws_manager.get_user_connection_count(current_user.id)
        }


@router.post("/notify/user/{user_id}", response_model=StatusResponse)
async def notify_user(
    user_id: str,
    notification: NotificationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Send a notification to a specific user.
    
    Requires authentication. Admin users can send to any user.
    Regular users can only send to themselves.
    """
    from main import ws_event_handler
    
    # Check if user is admin or sending to themselves
    is_admin = getattr(current_user, "is_admin", False)
    if not is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to send notifications to other users"
        )
    
    await ws_event_handler.send_notification(
        user_id,
        notification.title,
        notification.message,
        notification.level,
        notification.data
    )
    
    return {
        "status": "notification sent",
        "details": {"user_id": user_id}
    }


@router.post("/notify/broadcast", response_model=StatusResponse)
async def broadcast_notification(
    notification: NotificationBroadcastRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Broadcast a notification to all connected users.
    
    Requires authentication and admin privileges.
    """
    from main import ws_event_handler
    
    # Check if user is admin
    is_admin = getattr(current_user, "is_admin", False)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can broadcast notifications"
        )
    
    await ws_event_handler.broadcast_notification(
        notification.title,
        notification.message,
        notification.level,
        notification.data
    )
    
    return {
        "status": "notification broadcast",
    }


@router.post("/notify/users", response_model=StatusResponse)
async def notify_users(
    notification: UserNotificationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Send a notification to multiple users.
    
    Requires authentication and admin privileges.
    """
    from main import ws_event_handler
    
    # Check if user is admin
    is_admin = getattr(current_user, "is_admin", False)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can send notifications to multiple users"
        )
    
    # Send to each user
    for user_id in notification.user_ids:
        await ws_event_handler.send_notification(
            user_id,
            notification.title,
            notification.message,
            notification.level,
            notification.data
        )
    
    return {
        "status": "notifications sent",
        "details": {"user_count": len(notification.user_ids)}
    } 