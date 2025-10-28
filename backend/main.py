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
from app.api.v1.connections import router as connections_v1_router
from app.api.v1.messages import router as messages_v1_router
from app.api.v1.server_info import router as server_info_router
from app.api.v1.auth_config import router as auth_config_router
from app.api.v1.utils import router as utils_router
from app.api.dependencies import get_ws_handler as shared_get_ws_handler

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

# Load SaaS plugins if edition is 'saas'
from app.core.edition import get_edition

if get_edition() == "saas":
    try:
        from app.saas_plugins.bootstrap import register
        register(app)
        logger.info("✓ SaaS plugins loaded successfully")
    except ImportError as e:
        logger.warning(f"SaaS plugins not available: {e}")

# Include routers
app.include_router(auth_router, prefix="/auth")
app.include_router(local_auth_router, prefix="/auth")
app.include_router(user_router)
app.include_router(ws_router)
app.include_router(posts_router, prefix="/api/v1")
app.include_router(feed_router, prefix="/api/v1")
app.include_router(api_key_router)
app.include_router(profiles_v1_router, prefix="/api/v1")
app.include_router(profile_identity_router, prefix="/api/v1")
app.include_router(profile_contact_router, prefix="/api/v1")
app.include_router(profile_about_skills_router, prefix="/api/v1")
app.include_router(comments_v1_router, prefix="/api/v1")
app.include_router(connections_v1_router, prefix="/api/v1")
app.include_router(messages_v1_router, prefix="/api/v1")
app.include_router(server_info_router, prefix="/api/v1")
app.include_router(auth_config_router, prefix="/api/v1")
app.include_router(utils_router, prefix="/api/v1")

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

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    try:
        # Accept the connection explicitly first
        await websocket.accept()
        print(f"WebSocket attempting to connect for user_id: {user_id}")
        
        # Now add to the manager
        await ws_manager.connect(websocket, user_id)
        print(f"WebSocket connection established and added to manager for user_id: {user_id}")
    
    except Exception as e:
        # If connection/accept/add fails, log and close immediately
        print(f"Error during WebSocket connect/accept for user_id {user_id}: {e}")
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
        while True:
            data = await websocket.receive_json()
            message_type_str = data.get("type")
            print(f"Received message from user_id {user_id}, type: {message_type_str}")

            
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
                
            # Handle Authentication first if not yet authenticated
            if not authenticated_user_id and message_type == MessageType.AUTH:
                token = data.get("token")
                validated_user_id = await validate_ws_token(token) # Use your session/token validation logic
                if validated_user_id and validated_user_id == user_id:
                    authenticated_user_id = validated_user_id
                    await ws_manager.send_personal_message(MessageSchema.auth_success_message(user_id), websocket)
                    print(f"WebSocket authenticated for user_id: {user_id}")
                else:
                    await ws_manager.send_personal_message(MessageSchema.error_message("Authentication failed"), websocket)
                    print(f"WebSocket authentication failed for user_id: {user_id}")
                    # Close connection on auth failure
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    break # Exit the loop
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
            # --- End Response Handling --- 

            elif message_type == MessageType.PING:
                # Respond to pings to keep connection alive
                await ws_manager.send_personal_message(MessageSchema.pong_message(), websocket)
                print(f"Sent pong response to user_id: {user_id}")

            # Add other message type handlers here if needed
            # Example: Handle status updates FROM the client
            # elif message_type == MessageType.STATUS_UPDATE:
            #     print(f"Received status update from {user_id}: {data.get('status')}")
            #     # Potentially broadcast or process this status

            else:
                 # Ignore unexpected message types for now, or send error
                 print(f"Ignoring unhandled message type {message_type.value} from user_id: {user_id}")
                 # Optional: await ws_manager.send_personal_message(MessageSchema.error_message(f"Unhandled message type: {message_type_str}"), websocket)

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for user_id: {user_id}")
    except Exception as e:
        print(f"Error in WebSocket endpoint for user_id {user_id}: {e}")
        # Attempt to send error before closing if possible
        try:
            await websocket.send_json(MessageSchema.error_message(f"Server error: {e}"))
        except Exception:
            pass # Ignore if sending fails
    finally:
        # Cleanup connection
        await ws_manager.disconnect(websocket, user_id)
        print(f"Cleaned up connection for user_id: {user_id}")
        # Clean up any pending requests initiated by this user if they disconnect
        # Note: This cleanup might be too aggressive if user reconnects quickly
        # A more robust solution might involve timeouts on the pending requests themselves
        requests_to_remove = [req_id for req_id, pending in pending_ws_requests.items() if req_id.startswith(f"{user_id}_")] # Uses imported dict
        for req_id in requests_to_remove:
             if req_id in pending_ws_requests: # Uses imported dict
                 if not pending_ws_requests[req_id].event.is_set():
                      pending_ws_requests[req_id].error = Exception("Client disconnected before responding")
                      pending_ws_requests[req_id].event.set()
                 # Optionally remove immediately or let HTTP handler clean up
                 # del pending_ws_requests[req_id] # Uses imported dict
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
        from datetime import datetime, timezone
        current_time = datetime.now(timezone.utc)
        
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