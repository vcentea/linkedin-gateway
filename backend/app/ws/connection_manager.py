from fastapi import WebSocket
from typing import Dict, List, Set


class ConnectionManager:
    """
    Manager for WebSocket connections.
    Handles connection tracking, message broadcasting, and disconnection.
    """
    
    def __init__(self):
        # Maps user_id to a set of active connections (allows multiple connections per user)
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str):
        """
        Register a new WebSocket connection for a user
        
        Args:
            websocket: The WebSocket connection
            user_id: The ID of the user
        """
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        
    async def disconnect(self, websocket: WebSocket, user_id: str):
        """
        Remove a WebSocket connection for a user
        
        Args:
            websocket: The WebSocket connection
            user_id: The ID of the user
        """
        if user_id in self.active_connections:
            # Remove this specific connection
            self.active_connections[user_id].discard(websocket)
            
            # If no more connections for this user, remove the user entry
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
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
    
    async def broadcast_to_user(self, message: dict, user_id: str):
        """
        Broadcast a message to all connections of a specific user
        
        Args:
            message: The message to broadcast
            user_id: The ID of the user to broadcast to
        """
        if user_id not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception:
                # Mark this connection for removal
                disconnected.add(connection)
        
        # Remove any disconnected connections
        for connection in disconnected:
            await self.disconnect(connection, user_id)
    
    async def broadcast(self, message: dict):
        """
        Broadcast a message to all connected clients
        
        Args:
            message: The message to broadcast
        """
        disconnected_users = []
        
        for user_id, connections in self.active_connections.items():
            disconnected_connections = set()
            
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    # Mark this connection for removal
                    disconnected_connections.add(connection)
            
            # Remove any disconnected connections
            for connection in disconnected_connections:
                connections.discard(connection)
            
            # If no connections left for this user, mark for removal
            if not connections:
                disconnected_users.append(user_id)
        
        # Remove any users with no connections
        for user_id in disconnected_users:
            del self.active_connections[user_id]
    
    def get_user_connection_count(self, user_id: str) -> int:
        """
        Get the number of active connections for a user
        
        Args:
            user_id: The ID of the user
            
        Returns:
            int: The number of active connections
        """
        if user_id in self.active_connections:
            return len(self.active_connections[user_id])
        return 0
    
    def get_total_connections(self) -> int:
        """
        Get the total number of connections across all users
        
        Returns:
            int: Total number of connections
        """
        return sum(len(connections) for connections in self.active_connections.values()) 