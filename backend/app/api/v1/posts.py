"""
API endpoints for post-related operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from typing import Dict, Any, Optional, List
from uuid import uuid4, UUID
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from datetime import datetime
import iso8601 # For parsing ISO 8601 timestamps
import logging # Added logging
import httpx
import re

from app.db.dependencies import get_db
from app.db.models.post import Post # Import the Post model
from app.db.models.profile import Profile # Import the Profile model
from app.ws.message_types import MessageSchema
from app.ws.events import WebSocketEventHandler
from app.ws.state import pending_ws_requests, PendingRequest
# Import shared dependency
from app.api.dependencies import get_ws_handler
# Assume CRUD operations exist and can be imported
from app.crud import post as post_crud
from app.crud import profile as profile_crud
from app.schemas.post import PostCreate, GetProfilePostsRequest, GetProfilePostsResponse, ProfilePostDetail, GetPostTextRequest, GetPostTextResponse # Assuming a schema for creating posts
from app.schemas.profile import ProfileCreate # Assuming a schema for creating profiles
from app.crud import api_key as api_key_crud # Keep CRUD import
from app.core import security # Keep security import
from app.crud.api_key import API_KEY_PREFIX, API_KEY_PREFIX_LENGTH # Keep constants
# Import the shared validation function
from app.auth.dependencies import validate_api_key_from_header_or_body
# Import LinkedIn services for server-side execution
from app.linkedin.services.feed import LinkedInFeedService
from app.linkedin.services.posts import LinkedInPostsService
# Configure logging
logger = logging.getLogger(__name__)

MAX_PROFILE_POSTS = 500

# Define the response model for the actual posts data
class PostResponseItem(BaseModel):
    # This should align with your actual Post model + necessary fields
    id: int
    postid: str # Changed from postid to match DB model more closely if needed
    url: Optional[str] = None
    postcontent: Optional[str] = None # Changed from snippet
    author_id: int
    author_linkedin_id: str = Field(..., description="Author's LinkedIn profile ID")
    author_connection_degree: Optional[str] = Field(None, description="Connection degree (1st, 2nd, 3rd, etc.)")
    reactions: Optional[int] = None
    comments: Optional[int] = None
    reposts: Optional[int] = None
    engagement: Optional[int] = None
    timestamp: Optional[datetime] = None # Changed to datetime

    class Config:
        from_attributes = True # Pydantic v2 alias for orm_mode

# --- Request Body Model --- 
class FeedRequest(BaseModel):
    start_index: int = Field(..., description="Starting index for posts")
    count: int = Field(10, description="Number of posts to fetch (1-50)", ge=1, le=50)
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")

router = APIRouter(
    prefix="/posts",
    tags=["posts"],
)

# Helper to parse timestamp safely
def parse_timestamp(ts_string: Optional[str]) -> Optional[datetime]:
    if not ts_string:
        return None
    try:
        # Use iso8601 library for robust parsing
        return iso8601.parse_date(ts_string)
    except iso8601.ParseError:
        print(f"Warning: Could not parse timestamp: {ts_string}")
        return None

@router.post(
    "/request-feed", 
    response_model=List[PostResponseItem], 
    summary="Request Feed Posts via API Key (Body Auth)",
    deprecated=True
)
async def request_posts_from_feed(
    request_data: FeedRequest, # Changed: Read from body
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db), # Add DB session dependency
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    **DEPRECATED**: Use `/api/v1/feed/posts` with `X-API-Key` header instead.
    
    This endpoint will be removed in a future version.
    
    ---
    
    Requests posts from a user's LinkedIn feed via WebSocket, saves new ones
    to the database, and returns the corresponding Post objects.
    
    Authentication is performed using the `api_key` provided in the request body.

    Args:
        request_data (FeedRequest): Contains start_index, count, and api_key.
        ws_handler: WebSocket event handler instance
        db: Database session

    Returns:
        List[PostResponseItem]: A list of the fetched/saved Post objects.

    Raises:
        HTTPException 408: If the client does not respond within the timeout.
        HTTPException 503: If the WebSocket service is not available.
        HTTPException 400: If the count parameter is invalid.
        HTTPException 404: If the user is not connected via WebSocket.
        HTTPException 500: If the client reports an error or DB operation fails.
    """
    # --- Validate API Key from Body --- 
    try:
        # Returns APIKey object (v1.1.0) with CSRF/cookies for multi-key support
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_data.api_key, 
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        # Re-raise auth exceptions directly
        raise auth_exc
    except Exception as e:
        # Catch unexpected errors during validation
        logger.exception(f"Unexpected error during API key validation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error during authentication")
    # --- End Validation ---

    # Access validated data from request_data
    start_index = request_data.start_index
    count = request_data.count
    user_id_str = str(api_key.user_id)

    # --- SERVER-SIDE EXECUTION PATH ---
    if request_data.server_call:
        logger.info(f"[SERVER_CALL] Executing feed request on server for user {user_id_str}")
        
        try:
            # Get initialized LinkedIn service (uses CSRF/cookies from api_key object)
            feed_service = await get_linkedin_service(db, api_key, LinkedInFeedService)
            raw_posts_data = await feed_service.fetch_posts_from_feed(
                start_index=start_index,
                count=count
            )
            logger.info(f"[SERVER_CALL] Successfully fetched {len(raw_posts_data)} posts from LinkedIn")
            
            # Process and save posts (reuse existing logic)
            processed_db_posts: List[Post] = []
            
            for i, raw_post in enumerate(raw_posts_data):
                logger.info(f"[SERVER_CALL] Processing item {i+1}/{len(raw_posts_data)}")
                post_id_urn = raw_post.get('postId')
                if not post_id_urn:
                    logger.warning(f"[SERVER_CALL] Skipping raw post {i+1} due to missing 'postId'")
                    continue

                # Check if post already exists
                existing_post = await post_crud.get_by_postid(db=db, postid=post_id_urn)

                if existing_post:
                    processed_db_posts.append(existing_post)
                    logger.info(f"[SERVER_CALL] Post {post_id_urn} already exists (DB ID: {existing_post.id})")
                else:
                    # Find or Create Author Profile
                    author_profile_id_str = raw_post.get('authorProfileId')
                    author_profile = None
                    if author_profile_id_str:
                        author_profile = await profile_crud.get_by_profileid(db=db, profileid=author_profile_id_str)
                        if not author_profile:
                            profile_in = ProfileCreate(
                                linkedin_id=author_profile_id_str,
                                name=raw_post.get('authorName'),
                                jobtitle=raw_post.get('authorJobTitle'),
                                vanity_name=None,
                                profile_url=raw_post.get('authorUrl'),
                            )
                            try:
                                author_profile = await profile_crud.create_profile(db=db, profile_in=profile_in)
                                logger.info(f"[SERVER_CALL] Created new profile for {author_profile_id_str}")
                            except Exception as e:
                                logger.error(f"[SERVER_CALL] Error creating profile: {e}")
                                continue
                    else:
                        logger.warning(f"[SERVER_CALL] Skipping post {post_id_urn} due to missing 'authorProfileId'")
                        continue

                    if not author_profile or not author_profile.id:
                        logger.warning(f"[SERVER_CALL] Could not find or create profile for post {post_id_urn}")
                        continue

                    # Transform and Create Post
                    try:
                        # Store connection degree in metadata for later retrieval
                        post_metadata = {}
                        if raw_post.get('authorConnectionDegree'):
                            post_metadata['authorConnectionDegree'] = raw_post.get('authorConnectionDegree')
                        
                        post_create_data = PostCreate(
                            postid=post_id_urn,
                            url=raw_post.get('postUrl'),
                            postcontent=raw_post.get('postContent'),
                            author_id=author_profile.id,
                            reactions=raw_post.get('likes'),
                            comments=raw_post.get('comments'),
                            timestamp=parse_timestamp(raw_post.get('timestamp')),
                            post_metadata=post_metadata,
                        )
                        new_post = await post_crud.create_post(db=db, post_in=post_create_data)
                        processed_db_posts.append(new_post)
                        logger.info(f"[SERVER_CALL] Saved new post {post_id_urn} with DB ID {new_post.id}")
                    except Exception as e:
                        logger.error(f"[SERVER_CALL] Error saving post {post_id_urn}: {e}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to save post {post_id_urn} to database: {e}"
                        )
            
            logger.info(f"[SERVER_CALL] Returning {len(processed_db_posts)} processed/saved posts")
            
            # Transform Post objects to PostResponseItem with author details
            # We need to eagerly load author relationships to avoid lazy loading issues
            response_items = []
            for post in processed_db_posts:
                # Fetch the post with eagerly loaded author relationship
                stmt = select(Post).options(selectinload(Post.author)).where(Post.id == post.id)
                result = await db.execute(stmt)
                post_with_author = result.scalar_one()
                
                response_items.append(PostResponseItem(
                    id=post_with_author.id,
                    postid=post_with_author.postid,
                    url=post_with_author.url,
                    postcontent=post_with_author.postcontent,
                    author_id=post_with_author.author_id,
                    author_linkedin_id=post_with_author.author.linkedin_id,
                    author_connection_degree=post_with_author.post_metadata.get('authorConnectionDegree') if post_with_author.post_metadata else None,
                    reactions=post_with_author.reactions,
                    comments=post_with_author.comments,
                    reposts=post_with_author.reposts,
                    engagement=post_with_author.engagement,
                    timestamp=post_with_author.timestamp
                ))
            
            return response_items
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[SERVER_CALL] Error during server-side execution: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Server-side LinkedIn API call failed: {str(e)}"
            )
    
    # --- WEBSOCKET EXECUTION PATH (EXISTING) ---
    if not ws_handler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebSocket service not available"
        )

    # Log the state *before* the check
    logger.info(f"[WS Check] Checking connection for user_id: {user_id_str}")
    active_conn_keys = list(ws_handler.connection_manager.active_connections.keys())
    logger.info(f"[WS Check] Current active connection keys: {active_conn_keys}")
    user_connections = ws_handler.connection_manager.active_connections.get(user_id_str)
    connection_count = len(user_connections) if user_connections else 0
    logger.info(f"[WS Check] Connections found for {user_id_str}: {connection_count}")
    
    # Check if user has any active WebSocket connections

    
    # Note: Check removed - proxy_http_request already validates instance connection
    # --- End WebSocket Connection Check --- 

    # Count validation is now handled by Pydantic model (FeedRequest)
    request_id = f"{user_id_str}_{uuid4()}"
    message = MessageSchema.request_get_posts_message(
        start_index=start_index,
        count=count,
        request_id=request_id
    )

    pending_request = PendingRequest()
    pending_ws_requests[request_id] = pending_request

    try:
        print(f"Sending REQUEST_GET_POSTS to user {user_id_str} for request_id {request_id}")
        await ws_handler.connection_manager.broadcast_to_user(message, user_id_str)

        try:
            print(f"Waiting for response for request_id {request_id}...")
            await asyncio.wait_for(pending_request.event.wait(), timeout=60.0)
            print(f"Response received or timeout for request_id {request_id}")
        except asyncio.TimeoutError:
            print(f"Timeout waiting for response for request_id {request_id}")
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="Client did not respond within the time limit."
            )

        if pending_request.error:
            print(f"Client reported error for request_id {request_id}: {pending_request.error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Client failed to fetch posts: {str(pending_request.error)}"
            )

        raw_posts_data: List[Dict[str, Any]] = pending_request.result
        if raw_posts_data is None:
             print(f"Response received for {request_id}, but result data is missing.")
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Received response from client, but data was missing."
            )

        print(f"Successfully received {len(raw_posts_data)} raw posts for request_id {request_id}")
        # --- Process and Save Posts ---
        processed_db_posts: List[Post] = []
        print(f"Starting post processing loop for {len(raw_posts_data)} items...")

        # Rely on the transaction implicitly started by the first DB operation (validation)
        # and managed by the get_db dependency context manager.

        # Process posts within the same implicitly started transaction
        for i, raw_post in enumerate(raw_posts_data):
            print(f"--- Processing item {i+1}/{len(raw_posts_data)} --- Post ID: {raw_post.get('postId', 'N/A')}") # Log post ID only
            post_id_urn = raw_post.get('postId')
            if not post_id_urn:
                print(f"Warning: Skipping raw post {i+1} due to missing 'postId'.") # Updated Log
                continue

            # Check if post already exists
            print(f"Checking existence for postid: {post_id_urn}") # Added Log
            existing_post = await post_crud.get_by_postid(db=db, postid=post_id_urn)

            if existing_post:
                processed_db_posts.append(existing_post)
                print(f"Post {post_id_urn} already exists (DB ID: {existing_post.id}), adding to results.") # Updated Log
            else:
                print(f"Post {post_id_urn} is new. Processing author profile...") # Added Log
                # --- Find or Create Author Profile ---
                author_profile_id_str = raw_post.get('authorProfileId')
                author_profile = None
                if author_profile_id_str:
                    print(f"Checking/creating profile for author ID: {author_profile_id_str}") # Added Log
                    author_profile = await profile_crud.get_by_profileid(db=db, profileid=author_profile_id_str)
                    if not author_profile:
                         print(f"Profile {author_profile_id_str} not found, attempting creation...") # Added Log
                         # Create profile if it doesn't exist
                         # Vanity name fetching is removed from here
                         vanity_name = None # Set to None initially
                         
                         # Request vanity name via WebSocket
                         # This part needs to be integrated with the new WS flow
                         # For now, we assume vanity_name will be updated later or is null
                         
                         profile_in = ProfileCreate(
                             linkedin_id=author_profile_id_str, # Use the correct field name
                             name=raw_post.get('authorName'), # Map fullname to name
                             jobtitle=raw_post.get('authorJobTitle'), # Map headline to jobtitle
                             # Set the vanity name if found (will be None for now)
                             vanity_name=vanity_name,
                             # Set the profile URL
                             profile_url=raw_post.get('authorUrl'),
                             # Add other fields if available in raw_post and ProfileCreate
                         )
                         try:
                            author_profile = await profile_crud.create_profile(db=db, profile_in=profile_in)
                            print(f"Created new profile for {author_profile_id_str} (DB ID: {author_profile.id})") # Updated Log
                         except Exception as e: # Catch potential DB errors during profile creation
                            print(f"Error creating profile for {author_profile_id_str}: {e}")
                            print(f"Skipping post {post_id_urn} due to profile creation error.") # Added Log
                            continue # Skip this post if profile creation fails
                    else:
                         print(f"Found existing profile for {author_profile_id_str} (DB ID: {author_profile.id})") # Added Log
                else:
                    print(f"Warning: Skipping post {post_id_urn} due to missing 'authorProfileId'.")
                    continue # Skip post if we can't link an author

                # Ensure we have a valid author profile ID
                if not author_profile or not author_profile.id:
                     print(f"Warning: Could not find or create profile for post {post_id_urn}. Skipping save.")
                     continue
                else:
                     print(f"Using profile ID {author_profile.id} for post {post_id_urn}") # Added Log

                # --- Transform and Create Post ---
                try:
                    print(f"Preparing PostCreate schema for post {post_id_urn}...") # Added Log
                    
                    # Store connection degree in metadata for later retrieval
                    post_metadata = {}
                    if raw_post.get('authorConnectionDegree'):
                        post_metadata['authorConnectionDegree'] = raw_post.get('authorConnectionDegree')
                    
                    post_create_data = PostCreate(
                        postid=post_id_urn,
                        url=raw_post.get('postUrl'),
                        postcontent=raw_post.get('postContent'),
                        author_id=author_profile.id, # Link to the profile
                        reactions=raw_post.get('likes'), # Map 'likes' to 'reactions'
                        comments=raw_post.get('comments'),
                        timestamp=parse_timestamp(raw_post.get('timestamp')),
                        post_metadata=post_metadata,
                        # Map other fields if available and needed by PostCreate
                        # reposts=raw_post.get('reposts'),
                        # engagement=raw_post.get('engagement'),
                        # shareurn=raw_post.get('shareurn'),
                    )
                    print(f"Attempting to save post {post_id_urn} to DB...") # Added Log
                    new_post = await post_crud.create_post(db=db, post_in=post_create_data)
                    processed_db_posts.append(new_post)
                    print(f"Saved new post {post_id_urn} with DB ID {new_post.id}. Added to results.") # Updated Log
                except Exception as e:
                    print(f"Error saving post {post_id_urn} to DB: {e}")
                    # Decide how to handle: re-raise, log, skip?
                    # Re-raising will rollback the transaction for this batch
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to save post {post_id_urn} to database: {e}"
                    )
        print(f"--- Finished processing loop. {len(processed_db_posts)} posts in result list. ---") # Added Log

        # --- End Process and Save Posts ---

        print(f"Returning {len(processed_db_posts)} processed/saved posts for request_id {request_id}")
        
        # Transform Post objects to PostResponseItem with author details
        # We need to eagerly load author relationships to avoid lazy loading issues
        response_items = []
        for post in processed_db_posts:
            # Fetch the post with eagerly loaded author relationship
            stmt = select(Post).options(selectinload(Post.author)).where(Post.id == post.id)
            result = await db.execute(stmt)
            post_with_author = result.scalar_one()
            
            response_items.append(PostResponseItem(
                id=post_with_author.id,
                postid=post_with_author.postid,
                url=post_with_author.url,
                postcontent=post_with_author.postcontent,
                author_id=post_with_author.author_id,
                author_linkedin_id=post_with_author.author.linkedin_id,
                author_connection_degree=post_with_author.post_metadata.get('authorConnectionDegree') if post_with_author.post_metadata else None,
                reactions=post_with_author.reactions,
                comments=post_with_author.comments,
                reposts=post_with_author.reposts,
                engagement=post_with_author.engagement,
                timestamp=post_with_author.timestamp
            ))
        
        return response_items

    finally:
        if request_id in pending_ws_requests:
            del pending_ws_requests[request_id]
            print(f"Cleaned up pending request {request_id}")


@router.post("/profile-posts", response_model=GetProfilePostsResponse, summary="Extract Posts from LinkedIn Profile")
async def get_profile_posts(
    request_body: GetProfilePostsRequest = Body(...),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Fetches posts from a LinkedIn profile via server-side call or WebSocket.
    
    Authentication is performed using the `api_key` provided in the request body.

    Args:
        request_body: Contains profile_id, start, count, api_key, and server_call flag.
        ws_handler: WebSocket event handler instance
        db: Database session

    Returns:
        GetProfilePostsResponse: List of posts with pagination info

    Raises:
        HTTPException 408: If the client does not respond within the timeout (WebSocket mode).
        HTTPException 503: If the WebSocket service is not available (WebSocket mode).
        HTTPException 404: If the user is not connected via WebSocket (WebSocket mode).
        HTTPException 500: If the server-side or client reports an error.
    """
    # --- Validate API Key from Body --- 
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_body.api_key, 
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"Unexpected error during API key validation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error during authentication")
    # --- End Validation ---

    user_id_str = str(api_key.user_id)
    
    # Check WebSocket connection if using proxy mode
    if not request_body.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[PROFILE_POSTS] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    logger.info(f"[PROFILE_POSTS][{mode}] Executing for user {user_id_str}")
    effective_count = min(request_body.count, MAX_PROFILE_POSTS)
    if request_body.count > MAX_PROFILE_POSTS:
        logger.info(f"[PROFILE_POSTS][{mode}] Applying hard cap of {MAX_PROFILE_POSTS} posts (requested {request_body.count})")
    logger.info(f"[PROFILE_POSTS][{mode}] Parameters - profile_id: {request_body.profile_id}, count: {effective_count}")
    
    try:
        # Get service (uses CSRF/cookies from api_key object)
        posts_service = await get_linkedin_service(db, api_key, LinkedInPostsService)
        
        # Use service method to extract profile ID and handle pagination internally
        # This keeps the proven pagination logic from the service
        result = await posts_service.fetch_posts_for_profile(
            request_body.profile_id,
            effective_count,
            min_delay=request_body.min_delay,
            max_delay=request_body.max_delay
        )
        
        logger.info(f"[PROFILE_POSTS][{mode}] Successfully fetched {len(result['posts'])} posts")
        
        # Validate/parse the result into Pydantic models
        validated_posts = [ProfilePostDetail(**post) for post in result['posts']]
        
        logger.info(f"[PROFILE_POSTS][{mode}] Returning {len(validated_posts)} validated post details")
        return GetProfilePostsResponse(
            posts=validated_posts,
            hasMore=result['hasMore'],
            paginationToken=result['paginationToken']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[PROFILE_POSTS][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.post("/posts/get-post-text", response_model=GetPostTextResponse, tags=["posts"])
async def get_post_text(
    request_body: GetPostTextRequest = Body(...),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Extract post text from a LinkedIn post URL using API Key auth.
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False (default): Transparent HTTP proxy via browser extension
    
    Authentication: Provide API key via X-API-Key header OR in request body
    
    Args:
        request_body: Request containing post_url and execution mode
        ws_handler: WebSocket handler for proxy mode
        db: Database session
        
    Returns:
        GetPostTextResponse with post text (or None if not found) and post URL
        
    Raises:
        HTTPException 401: If API key is invalid
        HTTPException 404: If user is not connected via WebSocket (proxy mode)
        HTTPException 408: If the client does not respond within timeout (proxy mode)
        HTTPException 500: If server-side execution fails
        HTTPException 502: If proxy returns an error
        HTTPException 503: If WebSocket service is unavailable (proxy mode)
    """
    logger.info(f"[POST_TEXT] Received request for post: {request_body.post_url}")

    # --- Validate API Key from Header or Body --- 
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_body.api_key,
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[POST_TEXT] API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[POST_TEXT] Unexpected error during API key validation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error during authentication")

    user_id_str = str(api_key.user_id)

    # Check WebSocket connection if using proxy mode
    if not request_body.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[POST_TEXT] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    logger.info(f"[POST_TEXT][{mode}] Executing for user {user_id_str}")
    logger.info(f"[POST_TEXT][{mode}] Parameters - post_url: {request_body.post_url}")
    
    try:
        # Get service to fetch and parse HTML (uses CSRF/cookies from api_key object)
        posts_service = await get_linkedin_service(db, api_key, LinkedInPostsService)
        
        # --- EXECUTE REQUEST (proxy or direct) ---
        if request_body.server_call:
            # Direct server-side call
            logger.info(f"[POST_TEXT][{mode}] Fetching HTML directly from server")
            html_content = await posts_service.fetch_post_html(request_body.post_url)
        else:
            # Proxy via browser extension
            logger.info(f"[POST_TEXT][{mode}] Proxying HTML fetch through browser extension")
            proxy_response = await proxy_http_request(
                ws_handler=ws_handler,
                user_id=user_id_str,
                url=request_body.post_url,
                method="GET",
                headers=posts_service.headers,
                body=None,
                response_type="text",  # Get HTML response
                include_credentials=True,
                timeout=60.0,
                instance_id=api_key.instance_id  # Route to specific instance
            )
            
            logger.info(f"[POST_TEXT][{mode}] Received response with status {proxy_response['status_code']}")
            
            # Check for HTTP errors
            if proxy_response['status_code'] >= 400:
                error_msg = f"LinkedIn returned status {proxy_response['status_code']}"
                logger.error(f"[POST_TEXT][{mode}] {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=error_msg
                )
            
            # Get HTML content from proxy response
            html_content = proxy_response['body']
        
        logger.info(f"[POST_TEXT][{mode}] Received HTML content ({len(html_content)} bytes)")
        
        # --- EXTRACT POST TEXT FROM HTML ---
        post_text = posts_service.extract_post_text_from_html(html_content)
        
        if post_text:
            logger.info(f"[POST_TEXT][{mode}] ✓ Successfully extracted post text: {post_text[:100]}...")
        else:
            logger.warning(f"[POST_TEXT][{mode}] Post text not found in HTML")
        
        return GetPostTextResponse(
            postText=post_text,
            postUrl=request_body.post_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[POST_TEXT][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )
