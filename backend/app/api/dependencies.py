"""
Shared dependencies for API endpoints.
"""

from typing import Dict, Any

# Import necessary components
from app.ws.events import WebSocketEventHandler
from app.ws.state import pending_ws_requests, PendingRequest

# Dependency function signature for WS Handler (implementation provided by override in main.py)
async def get_ws_handler() -> WebSocketEventHandler:
    """
    Dependency placeholder for WebSocketEventHandler.
    The actual implementation is injected via app.dependency_overrides in main.py.
    """
    # This placeholder should never be executed if overrides are set correctly.
    raise NotImplementedError("WebSocket handler dependency not overridden")

# Dependency function to get the global pending requests dictionary
def get_pending_requests_dict() -> Dict[str, PendingRequest]:
    """
    Dependency function that returns the global pending_ws_requests dictionary.
    """
    return pending_ws_requests 