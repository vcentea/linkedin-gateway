from fastapi import WebSocket
from typing import Dict, List, Set, Optional
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manager for WebSocket connections.
    Handles connection tracking, message broadcasting, and disconnection.

    IMPORTANT: Connections are tracked by browser INSTANCE, not by USER.
    - Each browser/extension installation has a unique instance_id
    - Users can login/logout without affecting the WebSocket connection
    - API requests are routed to the correct instance via api_key.instance_id
    """

    def __init__(self):
        # Maps instance_id directly to WebSocket
        # Each browser instance maintains a single persistent connection
        self.active_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, instance_id: str):
        """
        Register a new WebSocket connection for a browser instance.

        IMPORTANT: Connections are tied to instance_id (browser), NOT user_id.
        Users can switch without affecting the connection.

        Args:
            websocket: The WebSocket connection
            instance_id: Browser instance identifier (required)
        """
        if not instance_id:
            logger.error("[WS] Cannot connect without instance_id")
            raise ValueError("instance_id is required")

        # Replace existing connection for this instance
        if instance_id in self.active_connections:
            logger.info(f"[WS] Replacing existing connection for instance {instance_id}")

        self.active_connections[instance_id] = websocket
        logger.info(f"[WS] Connected instance {instance_id}")
        
    async def disconnect(self, websocket: WebSocket, instance_id: str):
        """
        Remove a WebSocket connection for a browser instance.

        Args:
            websocket: The WebSocket connection
            instance_id: Browser instance identifier
        """
        if not instance_id:
            logger.warning("[WS] Cannot disconnect without instance_id")
            return

        if instance_id in self.active_connections:
            if self.active_connections[instance_id] == websocket:
                del self.active_connections[instance_id]
                logger.info(f"[WS] Disconnected instance {instance_id}")
            else:
                logger.warning(f"[WS] WebSocket mismatch for instance {instance_id}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send a message to a specific WebSocket
        
        Args:
            message: The message to send
            websocket: The destination WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")
    
    async def send_to_instance(self, message: dict, instance_id: str):
        """
        Send a message to a specific browser instance.

        Args:
            message: The message to send
            instance_id: Browser instance identifier to target
        """
        if not instance_id:
            logger.error("[WS] Cannot send message without instance_id")
            return

        if instance_id not in self.active_connections:
            logger.warning(f"[WS] Instance {instance_id} not connected, cannot send message")
            return

        websocket = self.active_connections[instance_id]
        try:
            await websocket.send_json(message)
            logger.debug(f"[WS] Sent message to instance {instance_id}")
        except Exception as e:
            logger.error(f"[WS] Error sending to instance {instance_id}: {e}")
            # Remove disconnected connection
            await self.disconnect(websocket, instance_id)

    # Keep old method name for backward compatibility, but route by instance_id only
    async def broadcast_to_user(self, message: dict, user_id: str, instance_id: Optional[str] = None):
        """
        DEPRECATED: Use send_to_instance() instead.
        Kept for backward compatibility with existing code.

        Routes message to instance_id (ignores user_id parameter).
        """
        if instance_id:
            await self.send_to_instance(message, instance_id)
        else:
            logger.warning(f"[WS] broadcast_to_user called without instance_id - cannot route")
    
    async def broadcast(self, message: dict):
        """
        Broadcast a message to all connected browser instances.

        Args:
            message: The message to broadcast
        """
        disconnected_instances = []

        for instance_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"[WS] Error broadcasting to instance {instance_id}: {e}")
                disconnected_instances.append(instance_id)

        # Remove any disconnected connections
        for instance_id in disconnected_instances:
            if instance_id in self.active_connections:
                websocket = self.active_connections[instance_id]
                await self.disconnect(websocket, instance_id)

    def get_total_connections(self) -> int:
        """
        Get the total number of active connections (instances).

        Returns:
            int: Total number of connections
        """
        return len(self.active_connections)

    def is_instance_connected(self, instance_id: str) -> bool:
        """
        Check if a specific instance is connected.

        Args:
            instance_id: Browser instance identifier

        Returns:
            bool: True if connected, False otherwise
        """
        return instance_id in self.active_connections 