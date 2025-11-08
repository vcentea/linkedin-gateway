"""
WebSocket event handlers.
"""
from fastapi import WebSocket
from typing import Dict, Any, Optional

from app.ws.connection_manager import ConnectionManager
from app.ws.message_types import MessageSchema


class WebSocketEventHandler:
    """
    Handler for WebSocket events and messages.
    Processes incoming messages and routes them to appropriate handlers.
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        """
        Initialize the event handler with a connection manager.
        
        Args:
            connection_manager: The WebSocket connection manager
        """
        self.connection_manager = connection_manager
    
    async def handle_linkedin_event(self, user_id: str, event_type: str, data: Dict[str, Any]):
        """
        Handle LinkedIn events and notify the appropriate users.
        
        Args:
            user_id: The ID of the user who should receive the event
            event_type: The type of LinkedIn event
            data: Event data
        """
        # Create a LinkedIn event message
        message = MessageSchema.linkedin_event_message(event_type, data)
        
        # Broadcast to the specific user
        await self.connection_manager.broadcast_to_user(message, user_id)
    
    async def send_notification(
        self, 
        user_id: str, 
        title: str, 
        message: str, 
        level: str = "info", 
        data: Optional[Dict[str, Any]] = None
    ):
        """
        Send a notification to a specific user.
        
        Args:
            user_id: The ID of the user to notify
            title: Notification title
            message: Notification message
            level: Severity level (info, warning, error, success)
            data: Optional additional data
        """
        notification = MessageSchema.notification_message(title, message, level, data)
        await self.connection_manager.broadcast_to_user(notification, user_id)
    
    async def broadcast_notification(
        self, 
        title: str, 
        message: str, 
        level: str = "info", 
        data: Optional[Dict[str, Any]] = None
    ):
        """
        Broadcast a notification to all connected users.
        
        Args:
            title: Notification title
            message: Notification message
            level: Severity level (info, warning, error, success)
            data: Optional additional data
        """
        notification = MessageSchema.notification_message(title, message, level, data)
        await self.connection_manager.broadcast(notification)
    
    async def send_status_update(
        self, 
        user_id: str, 
        status: str, 
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Send a status update to a specific user.
        
        Args:
            user_id: The ID of the user to update
            status: The new status
            details: Optional status details
        """
        status_message = MessageSchema.status_update_message(status, details)
        await self.connection_manager.broadcast_to_user(status_message, user_id) 