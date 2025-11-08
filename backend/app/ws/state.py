import asyncio
from typing import Dict, Any, Optional

class PendingRequest:
    """Represents a pending request waiting for a WebSocket response."""
    def __init__(self):
        self.event = asyncio.Event()
        self.result: Any = None
        self.error: Optional[Exception] = None

# Global dictionary to store pending requests
pending_ws_requests: Dict[str, PendingRequest] = {} 