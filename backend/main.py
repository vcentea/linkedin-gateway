"""
Main module for the FastAPI application.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import json
from typing import Dict, List, Optional, Any, Tuple
from functools import partial
import asyncio
from starlette import status
import logging

from app.core.config import settings
from app.db.session import engine
from app.db.base import Base
from app.auth.routes import router as auth_router
from app.auth.local_auth import router as local_auth_router
from app.user.routes import router as user_router
from app.api.v1.posts import router as posts_router
from app.api.v1.feed import router as feed_router
from app.user.api_key import router as api_key_router
from app.api.v1.api_keys import router as api_keys_v1_router  # Multi-key management (v1.1.0)
from app.ws.connection_manager import ConnectionManager
from app.ws.auth import validate_ws_token
from app.ws.message_types import MessageType, MessageSchema
from app.ws.events import WebSocketEventHandler
from app.api.ws import router as ws_router
from app.ws.state import pending_ws_requests, PendingRequest
from app.api.v1.profiles import router as profiles_v1_router
from app.api.v1.profile_identity import router as profile_identity_router
from app.api.v1.profile_contact import router as profile_contact_router
from app.api.v1.profile_about_skills import router as profile_about_skills_router
from app.api.v1.comments import router as comments_v1_router
from app.api.v1.reactions import router as reactions_v1_router
from app.api.v1.user_comments import router as user_comments_v1_router
from app.api.v1.connections import router as connections_v1_router
from app.api.v1.messages import router as messages_v1_router
from app.api.v1.server_info import router as server_info_router
from app.api.v1.auth_config import router as auth_config_router
from app.api.v1.utils import router as utils_router
from app.api.dependencies import get_ws_handler as shared_get_ws_handler
# Gemini AI endpoints (v1.2.0)
from app.api.v1.gemini_chat import router as gemini_chat_router
from app.api.v1.gemini_auth import router as gemini_auth_router
from app.api.v1.gemini_v1beta import router as gemini_v1beta_router

# Setup logging
logger = logging.getLogger(__name__)

# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler - runs on startup and shutdown.
    """
    # Startup
    from app.core.edition import get_edition, get_channel
    
    edition = get_edition()
    channel = get_channel()
    
    print("\n" + "="*80)
    print("🚀 LinkedIn Gateway API Starting")
    print("="*80)
    print(f"\n📦 Edition: {edition.upper()}")
    print(f"🔧 Channel: {channel}")
    
    # Check OAuth credentials
    missing_credentials = []
    if not settings.LINKEDIN_CLIENT_ID or settings.LINKEDIN_CLIENT_ID == "...":
        missing_credentials.append("LINKEDIN_CLIENT_ID")
    if not settings.LINKEDIN_CLIENT_SECRET or settings.LINKEDIN_CLIENT_SECRET == "...":
        missing_credentials.append("LINKEDIN_CLIENT_SECRET")
    
    if missing_credentials:
        print(f"\n⚠️  Missing OAuth: {', '.join(missing_credentials)}")
    else:
        print("\n✅ OAuth Credentials: Configured")
    
    # Display callback URL
    port = int(os.getenv("PORT", os.getenv("API_PORT", settings.API_PORT)))
    public_url = os.getenv("PUBLIC_URL")
    
    if public_url:
        callback_url = f"{public_url.rstrip('/')}/auth/user/callback"
        print(f"🔗 Callback URL: {callback_url}")
        print("✅ HTTPS configured")
    else:
        callback_url = f"http://localhost:{port}/auth/user/callback"
        print(f"🔗 Callback URL: {callback_url}")
        print("⚠️  HTTP only - Set PUBLIC_URL env var for HTTPS")
    
    # Database status
    try:
        from app.db.session import DATABASE_URL
        if os.getenv("DATABASE_URL"):
            print("✅ Database: Using DATABASE_URL")
        else:
            print("✅ Database: Using DB_* env vars")
    except Exception as e:
        print(f"⚠️  Database: {str(e)}")
    
    print(f"\n🌐 Server: http://0.0.0.0:{port}")
    print(f"📖 Docs: http://localhost:{port}/docs")
    print("="*80 + "\n")
    
    yield
    
    # Shutdown
    logger.info("LinkedIn Gateway API shutting down")

# Create tables if they don't exist
# Comment this out if using Alembic migrations
# Base.metadata.create_all(bind=engine)

from app.__version__ import __version__

app = FastAPI(
    title="LinkedIn Gateway API",
    description="API for LinkedIn Automation System",
    version=__version__,
    lifespan=lifespan,
)

# Initialize the WebSocket connection manager
ws_manager = ConnectionManager()

# Initialize the WebSocket event handler
ws_event_handler = WebSocketEventHandler(ws_manager)

# IMPORTANT: Add SessionMiddleware BEFORE routes that use sessions
# Replace 'YOUR_SECRET_KEY' with a strong, secure key from settings or env
# For development, you can generate one: openssl rand -hex 32
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET_KEY or "YOUR_VERY_SECRET_KEY_REPLACE_ME_IN_PROD",
    https_only=False,
    max_age=14 * 24 * 60 * 60
)

# Configure CORS
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Pending Request Management --- 
# Moved to app/ws/state.py
# class PendingRequest:
#    ...
# pending_ws_requests: Dict[str, PendingRequest] = {}
# --- End Pending Request Management ---

# Override WebSocket handler dependency for API routers
async def override_get_ws_handler() -> WebSocketEventHandler:
    return ws_event_handler

# Apply override to the shared dependency function
app.dependency_overrides[shared_get_ws_handler] = override_get_ws_handler

# Load edition-specific plugins
from app.core.edition import get_edition

edition = get_edition()

if edition == "saas":
    try:
        from app.saas_plugins.bootstrap import register
        register(app)
        logger.info("✓ SaaS plugins loaded successfully")
    except ImportError as e:
        logger.warning(f"SaaS plugins not available: {e}")
elif edition == "enterprise":
    try:
        from app.enterprise_plugins.bootstrap import register
        register(app)
        logger.info("✓ Enterprise plugins loaded successfully")
    except ImportError as e:
        logger.warning(f"Enterprise plugins not available: {e}")

# Include routers
app.include_router(auth_router, prefix="/auth")
app.include_router(local_auth_router, prefix="/auth")
app.include_router(user_router)
app.include_router(ws_router)
app.include_router(posts_router, prefix="/api/v1")
app.include_router(feed_router, prefix="/api/v1")
app.include_router(api_key_router)
app.include_router(api_keys_v1_router, prefix="/v1")  # Multi-key management API (v1.1.0)
app.include_router(profiles_v1_router, prefix="/api/v1")
app.include_router(profile_identity_router, prefix="/api/v1")
app.include_router(profile_contact_router, prefix="/api/v1")
app.include_router(profile_about_skills_router, prefix="/api/v1")
app.include_router(comments_v1_router, prefix="/api/v1")
app.include_router(reactions_v1_router, prefix="/api/v1")
app.include_router(user_comments_v1_router, prefix="/api/v1")
app.include_router(connections_v1_router, prefix="/api/v1")
app.include_router(messages_v1_router, prefix="/api/v1")
app.include_router(server_info_router, prefix="/api/v1")
app.include_router(auth_config_router, prefix="/auth")
app.include_router(utils_router, prefix="/api/v1")
# Gemini AI endpoints (v1.2.0)
app.include_router(gemini_chat_router, prefix="/api/v1")  # Gemini chat: /api/v1/gemini/chat/completions
app.include_router(gemini_v1beta_router, prefix="/api/v1")  # Gemini v1beta: /api/v1/gemini/v1beta/models
app.include_router(gemini_auth_router, prefix="/api/v1")  # Gemini OAuth: /api/v1/gemini/auth/*

# Remove duplicate pending_post_requests if it's the same as pending_ws_requests
# pending_post_requests: Dict[str, Dict] = {} 

@app.get("/")
async def root():
    """
    Root endpoint for health checks.
    """
    return {"message": "LinkedIn Gateway API is running"}

@app.get("/health")
async def health():
    """
    Health check endpoint.
    """
    return {"status": "ok"}

@app.get("/version", tags=["health"])
async def get_version():
    """
    Get API version and feature flags.
    Used by extension to check compatibility.
    
    Returns:
        dict: Version information including:
            - version: API version string
            - features: Dictionary of available features
            - min_extension_version: Minimum compatible extension version
    """
    from app.core.version import get_version_info
    return get_version_info()

@app.get("/ws/status")
async def websocket_status():
    """
    Get WebSocket connection statistics.
    """
    return {
        "connections": ws_manager.get_total_connections(),
        "users": len(ws_manager.active_connections)
    }

@app.post("/notify/{user_id}")
async def send_notification(
    user_id: str,
    title: str,
    message: str,
    level: str = "info"
):
    """
    Send a notification to a specific user.
    """
    await ws_event_handler.send_notification(user_id, title, message, level)
    return {"status": "notification sent"}

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket
):
    """
    WebSocket endpoint for real-time communication.

    IMPORTANT: WebSocket connections are tied to browser INSTANCE, not USER.
    The instance_id uniquely identifies the browser/extension installation.
    Users can login/logout without affecting the WebSocket connection.

    Connection URL: wss://server/ws?instance_id={instance_id}

    Args:
        websocket: The WebSocket connection
    """
    instance_id = None

    try:
        # Accept the connection explicitly first
        await websocket.accept()

        # Extract instance_id from query parameters - REQUIRED
        try:
            instance_id = websocket.query_params.get("instance_id")
        except (AttributeError, Exception) as e:
            print(f"Error getting instance_id from query params: {e}")
            pass

        if not instance_id:
            print(f"WebSocket connection rejected: No instance_id provided")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="instance_id required")
            return

        print(f"WebSocket attempting to connect for instance_id: {instance_id}")

        # Add to the manager with instance_id ONLY (no user_id)
        await ws_manager.connect(websocket, instance_id)
        print(f"WebSocket connection established for instance_id: {instance_id}")
    
    except Exception as e:
        # If connection/accept/add fails, log and close immediately
        print(f"Error during WebSocket connect/accept for instance_id {instance_id}: {e}")
        import traceback
        traceback.print_exc()
        # We might not be able to send a close code if accept failed
        # but try anyway
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass # Ignore if closing fails
        return # Stop further execution

    authenticated_user_id: Optional[str] = None

    try:
        print(f"[WS] Entering message loop for instance_id {instance_id}")
        while True:
            print(f"[WS] Waiting for message from instance_id {instance_id}...")
            data = await websocket.receive_json()
            message_type_str = data.get("type")
            print(f"Received message from instance_id {instance_id}, type: {message_type_str}")

            
            if not message_type_str:
                print("Message type missing")
                await ws_manager.send_personal_message(MessageSchema.error_message("Message type missing"), websocket)
                continue
            
            try:
                message_type = MessageType(message_type_str)
                print(f"Parsed message type: {message_type.value}")
            except ValueError:
                print(f"Unknown message type: {message_type_str}")
                await ws_manager.send_personal_message(MessageSchema.error_message(f"Unknown message type: {message_type_str}"), websocket)
                continue
                
            # Handle Authentication (optional - allows tracking which user is using this instance)
            if message_type == MessageType.AUTH:
                token = data.get("token")
                validated_user_id = await validate_ws_token(token)
                if validated_user_id:
                    authenticated_user_id = validated_user_id
                    await ws_manager.send_personal_message(MessageSchema.auth_success_message(validated_user_id), websocket)
                    print(f"WebSocket instance {instance_id} authenticated for user_id: {validated_user_id}")
                else:
                    # Don't close connection on auth failure - just log it
                    # The instance can try to auth again with a different user
                    await ws_manager.send_personal_message(MessageSchema.error_message("Authentication failed"), websocket)
                    print(f"WebSocket authentication failed for instance_id: {instance_id}")
                continue # Wait for next message

            # --- Handle Response for Pending Requests --- 
            elif message_type == MessageType.RESPONSE_GET_POSTS:
                request_id = data.get("request_id")
                if request_id in pending_ws_requests:
                    print(f"Received response for pending request_id: {request_id}")
                    pending_request = pending_ws_requests[request_id]
                    if data.get("status") == "success":
                        pending_request.result = data.get("data")
                    else:
                        # Store error details if provided by client
                        pending_request.error = Exception(data.get("error_message", "Client reported an error"))
                    pending_request.event.set() # Signal the waiting HTTP handler
                    # Keep request in dict until retrieved by HTTP handler
                else:
                    print(f"Received response for unknown or completed request_id: {request_id}")
            
            # Add handler for Profile Data Response (Added)
            elif message_type == MessageType.RESPONSE_PROFILE_DATA:
                request_id = data.get("request_id")
                if request_id in pending_ws_requests:
                    print(f"Received profile data response for pending request_id: {request_id}")
                    pending_request = pending_ws_requests[request_id]
                    if data.get("status") == "success":
                        pending_request.result = data.get("data")
                    else:
                        pending_request.error = Exception(data.get("error_message", "Client reported an error fetching profile data"))
                    pending_request.event.set() # Signal the waiting handler
                else:
                    print(f"Received profile data response for unknown or completed request_id: {request_id}")

            # Add handler for Commenter Data Response
            elif message_type == MessageType.RESPONSE_GET_COMMENTERS:
                request_id = data.get("request_id")
                if request_id in pending_ws_requests:
                    print(f"Received commenter data response for pending request_id: {request_id}")
                    pending_request = pending_ws_requests[request_id]
                    if data.get("status") == "success":
                        # Ensure data key exists and is a list (or handle if it's missing/wrong type)
                        pending_request.result = data.get("data", []) 
                    else:
                        pending_request.error = Exception(data.get("error_message", "Client reported an error fetching commenters"))
                    pending_request.event.set() # Signal the waiting handler
                else:
                    print(f"Received commenter data response for unknown or completed request_id: {request_id}")

            # Add handler for Profile Posts Response
            elif message_type == MessageType.RESPONSE_GET_PROFILE_POSTS:
                request_id = data.get("request_id")
                if request_id in pending_ws_requests:
                    print(f"Received profile posts response for pending request_id: {request_id}")
                    pending_request = pending_ws_requests[request_id]
                    if data.get("status") == "success":
                        # Store the full response data (posts, hasMore, paginationToken)
                        pending_request.result = {
                            "posts": data.get("posts", []),
                            "hasMore": data.get("hasMore", False),
                            "paginationToken": data.get("paginationToken")
                        }
                    else:
                        pending_request.error = Exception(data.get("error_message", "Client reported an error fetching profile posts"))
                    pending_request.event.set() # Signal the waiting handler
                else:
                    print(f"Received profile posts response for unknown or completed request_id: {request_id}")
            
            # Add handler for Proxy HTTP Response
            elif message_type == MessageType.RESPONSE_PROXY_HTTP:
                request_id = data.get("request_id")
                if request_id in pending_ws_requests:
                    print(f"[PROXY_HTTP] Received response for pending request_id: {request_id}")
                    pending_request = pending_ws_requests[request_id]
                    if data.get("status") == "success":
                        # Store the raw HTTP response data
                        pending_request.result = {
                            'status_code': data.get('status_code'),
                            'headers': data.get('headers', {}),
                            'body': data.get('body')
                        }
                        print(f"[PROXY_HTTP] Success: status_code={data.get('status_code')}, body_length={len(data.get('body', ''))}")
                    else:
                        pending_request.error = Exception(data.get("error_message", "Extension reported an error executing HTTP request"))
                        print(f"[PROXY_HTTP] Error: {data.get('error_message')}")
                    pending_request.event.set() # Signal the waiting handler
                else:
                    print(f"[PROXY_HTTP] Received response for unknown or completed request_id: {request_id}")

            # Add handler for Refresh LinkedIn Session Response
            elif message_type == MessageType.RESPONSE_REFRESH_LINKEDIN_SESSION:
                request_id = data.get("request_id")
                if request_id in pending_ws_requests:
                    print(f"[REFRESH_SESSION] Received response for pending request_id: {request_id}")
                    pending_request = pending_ws_requests[request_id]
                    if data.get("status") == "success":
                        # Store the refreshed credentials
                        pending_request.result = {
                            'csrf_token': data.get('csrf_token'),
                            'cookies': data.get('cookies')
                        }
                        print(f"[REFRESH_SESSION] Success: csrf_token={data.get('csrf_token')[:20] if data.get('csrf_token') else 'None'}..., cookies_count={len(data.get('cookies', {}))}")
                    else:
                        pending_request.error = Exception(data.get("error_message", "Extension reported an error refreshing session"))
                        print(f"[REFRESH_SESSION] Error: {data.get('error_message')}")
                    pending_request.event.set() # Signal the waiting handler
                else:
                    print(f"[REFRESH_SESSION] Received response for unknown or completed request_id: {request_id}")
            # --- End Response Handling ---

            elif message_type == MessageType.PING:
                # Respond to pings to keep connection alive
                await ws_manager.send_personal_message(MessageSchema.pong_message(), websocket)
                print(f"Sent pong response to instance_id: {instance_id}")

            # Add other message type handlers here if needed
            # Example: Handle status updates FROM the client
            # elif message_type == MessageType.STATUS_UPDATE:
            #     print(f"Received status update from instance {instance_id}: {data.get('status')}")
            #     # Potentially broadcast or process this status

            else:
                 # Ignore unexpected message types for now, or send error
                 print(f"Ignoring unhandled message type {message_type.value} from instance_id: {instance_id}")
                 # Optional: await ws_manager.send_personal_message(MessageSchema.error_message(f"Unhandled message type: {message_type_str}"), websocket)

    except WebSocketDisconnect as e:
        print(f"[WS] WebSocket disconnected for instance_id: {instance_id}")
        print(f"[WS] Disconnect code: {e.code if hasattr(e, 'code') else 'unknown'}, reason: {e.reason if hasattr(e, 'reason') else 'unknown'}")
    except Exception as e:
        print(f"[WS] Error in WebSocket endpoint for instance_id {instance_id}: {e}")
        import traceback
        traceback.print_exc()
        # Attempt to send error before closing if possible
        try:
            await websocket.send_json(MessageSchema.error_message(f"Server error: {e}"))
        except Exception:
            pass # Ignore if sending fails
    finally:
        # Cleanup connection
        await ws_manager.disconnect(websocket, instance_id)
        print(f"Cleaned up connection for instance_id: {instance_id}")
        # Clean up any pending requests initiated by this instance if they disconnect
        # We can use authenticated_user_id if it was set
        if authenticated_user_id:
            requests_to_remove = [req_id for req_id, pending in pending_ws_requests.items() if req_id.startswith(f"{authenticated_user_id}_")]
            for req_id in requests_to_remove:
                 if req_id in pending_ws_requests:
                     if not pending_ws_requests[req_id].event.is_set():
                          pending_ws_requests[req_id].error = Exception("Client disconnected before responding")
                          pending_ws_requests[req_id].event.set()
                     print(f"Marked pending request {req_id} as errored due to disconnect")

@app.post("/debug/check-token")
async def check_token_validity(token: str):
    """
    Debug endpoint to check if a token is valid.
    """
    try:
        # Get database session
        from app.db.session import get_db
        db = next(get_db())
        
        # Query the database for the session
        from app.db.models.user import UserSession
        from datetime import datetime
        current_time = datetime.utcnow()
        
        session = db.query(UserSession).filter(
            UserSession.session_token == token
        ).first()
        
        if not session:
            return {
                "valid": False,
                "reason": "No session found with this token",
                "token_preview": token[:20] + "..." if token else "None"
            }
        
        # Check if session is expired
        is_expired = session.expires_at <= current_time
        
        if is_expired:
            return {
                "valid": False,
                "reason": "Session is expired",
                "session_id": str(session.id),
                "user_id": str(session.user_id),
                "expires_at": session.expires_at.isoformat(),
                "current_time": current_time.isoformat(),
                "token_preview": token[:20] + "..." if token else "None"
            }
        
        # Session is valid
        return {
            "valid": True,
            "session_id": str(session.id),
            "user_id": str(session.user_id),
            "expires_at": session.expires_at.isoformat(),
            "current_time": current_time.isoformat(),
            "token_preview": token[:20] + "..." if token else "None"
        }
        
    except Exception as e:
        import traceback
        return {
            "valid": False,
            "reason": f"Error checking token: {str(e)}",
            "traceback": traceback.format_exc(),
            "token_preview": token[:20] + "..." if token else "None"
        }

# Startup event handler moved to lifespan context manager above

if __name__ == "__main__":
    """
    Run the application directly.
    """
    import uvicorn
    
    port = int(os.getenv("API_PORT", settings.API_PORT))
    host = os.getenv("API_HOST", settings.API_HOST)
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
    ) 