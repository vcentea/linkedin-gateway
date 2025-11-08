"""
API endpoint for LinkedIn feed operations.

This endpoint supports three execution modes:
1. server_call=True: Execute LinkedIn API call directly from backend
2. proxy=True: Execute via browser extension as transparent HTTP proxy
3. Neither: Use specialized WebSocket message (legacy, for backward compatibility)
"""
import logging
import asyncio
import json
from uuid import uuid4
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from datetime import datetime
import iso8601

from app.db.dependencies import get_db
from app.db.models.post import Post
from app.db.models.profile import Profile
from app.ws.events import WebSocketEventHandler
from app.ws.state import pending_ws_requests, PendingRequest
from app.ws.message_types import MessageSchema
from app.api.dependencies import get_ws_handler
from app.crud import post as post_crud
from app.crud import profile as profile_crud
from app.schemas.post import PostCreate
from app.schemas.profile import ProfileCreate
from app.auth.dependencies import validate_api_key_from_header_or_body
from app.linkedin.services.feed import LinkedInFeedService
from app.linkedin.helpers import get_linkedin_service
from app.linkedin.helpers.proxy_http import proxy_http_request
from app.api.v1.server_validation import validate_server_call_permission

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/feed",
    tags=["feed"],
)


# Request/Response models
class FeedRequest(BaseModel):
    """Request model for feed posts."""
    start_index: int = Field(0, description="Starting index for posts")
    count: int = Field(10, description="Number of posts to fetch (1-50)", ge=1, le=50)
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use proxy via extension")


class PostResponseItem(BaseModel):
    """Response model for a single post."""
    id: int
    postid: str
    ugcpostid: str | None = Field(None, description="UGC Post ID if available (extracted from *socialDetail)")
    url: str | None = None
    postcontent: str | None = None
    author_id: int
    author_linkedin_id: str = Field(..., description="Author's LinkedIn profile ID")
    author_name: str | None = Field(None, description="Author's full name")
    author_headline: str | None = Field(None, description="Author's job title/headline")
    author_connection_degree: str | None = Field(None, description="Connection degree (1st, 2nd, 3rd, etc.)")
    reactions: int | None = None
    comments: int | None = None
    reposts: int | None = None
    engagement: int | None = None
    timestamp: datetime | None = None

    class Config:
        from_attributes = True


# Helper functions
def parse_timestamp(ts_string: str | None) -> datetime | None:
    """Parse ISO 8601 timestamp safely."""
    if not ts_string:
        return None
    try:
        return iso8601.parse_date(ts_string)
    except iso8601.ParseError:
        logger.warning(f"Could not parse timestamp: {ts_string}")
        return None


async def process_and_save_posts(
    raw_posts_data: List[Dict[str, Any]],
    db: AsyncSession
) -> List[Post]:
    """
    Process raw post data and save to database.
    
    Args:
        raw_posts_data: List of raw post dictionaries from LinkedIn API.
        db: Database session.
        
    Returns:
        List of Post objects (existing or newly created).
    """
    processed_db_posts: List[Post] = []
    
    for i, raw_post in enumerate(raw_posts_data):
        logger.info(f"Processing post {i+1}/{len(raw_posts_data)}")
        post_id_urn = raw_post.get('postId')
        if not post_id_urn:
            logger.warning(f"Skipping post {i+1} due to missing 'postId'")
            continue

        # Check if post already exists
        existing_post = await post_crud.get_by_postid(db=db, postid=post_id_urn)

        if existing_post:
            processed_db_posts.append(existing_post)
            logger.info(f"Post {post_id_urn} already exists (DB ID: {existing_post.id})")
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
                        logger.info(f"Created new profile for {author_profile_id_str}")
                    except Exception as e:
                        logger.error(f"Error creating profile: {e}")
                        continue
            else:
                logger.warning(f"Skipping post {post_id_urn} due to missing 'authorProfileId'")
                continue

            if not author_profile or not author_profile.id:
                logger.warning(f"Could not find or create profile for post {post_id_urn}")
                continue

            # Transform and Create Post
            try:
                # Store connection degree in metadata
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
                logger.info(f"Saved new post {post_id_urn} with DB ID {new_post.id}")
            except Exception as e:
                logger.error(f"Error saving post {post_id_urn}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save post {post_id_urn} to database: {e}"
                )
    
    logger.info(f"Processed {len(processed_db_posts)} posts")
    return processed_db_posts


async def build_response_items(posts: List[Post], db: AsyncSession) -> List[PostResponseItem]:
    """
    Build response items from Post objects with eagerly loaded author relationships.
    
    Args:
        posts: List of Post objects.
        db: Database session.
        
    Returns:
        List of PostResponseItem objects.
    """
    response_items = []
    for post in posts:
        # Fetch the post with eagerly loaded author relationship
        stmt = select(Post).options(selectinload(Post.author)).where(Post.id == post.id)
        result = await db.execute(stmt)
        post_with_author = result.scalar_one()
        
        response_items.append(PostResponseItem(
            id=post_with_author.id,
            postid=post_with_author.postid,
            ugcpostid=post_with_author.ugcpostid,  # Include ugcPostId from database
            url=post_with_author.url,
            postcontent=post_with_author.postcontent,
            author_id=post_with_author.author_id,
            author_linkedin_id=post_with_author.author.linkedin_id,
            author_name=post_with_author.author.name,  # Author's full name
            author_headline=post_with_author.author.jobtitle,  # Author's job title/headline
            author_connection_degree=post_with_author.post_metadata.get('authorConnectionDegree') if post_with_author.post_metadata else None,
            reactions=post_with_author.reactions,
            comments=post_with_author.comments,
            reposts=post_with_author.reposts,
            engagement=post_with_author.engagement,
            timestamp=post_with_author.timestamp
        ))
    
    return response_items


# Main endpoint
@router.post("/posts", response_model=List[PostResponseItem], summary="Request Feed Posts")
async def request_feed_posts(
    request_data: FeedRequest,
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """
    Request posts from LinkedIn feed.
    
    Supports two execution modes:
    1. server_call=True: Direct server-side LinkedIn API call
    2. server_call=False: Transparent HTTP proxy via browser extension
    
    Args:
        request_data: Request parameters including api_key, start_index, count, server_call.
        ws_handler: WebSocket event handler instance.
        db: Database session.
        
    Returns:
        List of PostResponseItem objects.
        
    Raises:
        HTTPException: On authentication failure, timeout, or processing errors.
    """
    # Validate API key from header or body (returns APIKey object v1.1.0)
    try:
        api_key = await validate_api_key_from_header_or_body(
            api_key_from_body=request_data.api_key, 
            api_key_header=x_api_key,
            db=db
        )
        logger.info(f"[FEED] API Key validated for user ID: {api_key.user_id}")
    except HTTPException as auth_exc:
        raise auth_exc
    except Exception as e:
        logger.exception(f"[FEED] Unexpected error during API key validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during authentication"
        )
    
    # Validate server_call permission
    await validate_server_call_permission(request_data.server_call)
    
    user_id_str = str(api_key.user_id)
    start_index = request_data.start_index
    count = request_data.count
    
    # Check WebSocket connection if using proxy mode
    if not request_data.server_call:
        if not ws_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket service not available"
            )
        
        if not ws_handler.connection_manager.is_instance_connected(api_key.instance_id):
            logger.warning(f"[FEED] Instance {api_key.instance_id} not connected via WebSocket")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Browser instance not connected. Please check your extension.")
    
    # --- UNIFIED EXECUTION LOGIC ---
    mode = "SERVER_CALL" if request_data.server_call else "PROXY"
    logger.info(f"[FEED][{mode}] Executing feed request for user {user_id_str}")
    logger.info(f"[FEED][{mode}] Parameters - start_index: {start_index}, count: {count}")
    
    try:
        # Get feed service to build URL and parse response (uses CSRF/cookies from api_key object)
        feed_service = await get_linkedin_service(db, api_key, LinkedInFeedService)
        
        # Build the LinkedIn API URL
        url = feed_service._build_feed_url(start_index, count)
        logger.info(f"[FEED][{mode}] Target URL: {url[:100]}...")
        
        # --- EXECUTE REQUEST (proxy or direct) ---
        if request_data.server_call:
            # Direct server-side call
            response_data = await feed_service._make_request(url)
        else:
            # Proxy via browser extension - route to specific instance
            proxy_response = await proxy_http_request(
                ws_handler=ws_handler,
                user_id=user_id_str,
                url=url,
                method="GET",
                headers=feed_service.headers,
                response_type="json",
                include_credentials=True,
                timeout=60.0,
                instance_id=api_key.instance_id  # Route to specific instance (with fallback)
            )
            
            logger.info(f"[FEED][{mode}] Received response with status {proxy_response['status_code']}")
            
            # Check for HTTP errors
            if proxy_response['status_code'] >= 400:
                error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
                logger.error(f"[FEED][{mode}] {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=error_msg
                )
            
            # Parse response body as JSON
            try:
                response_data = json.loads(proxy_response['body'])
            except json.JSONDecodeError as e:
                logger.error(f"[FEED][{mode}] Failed to parse response JSON: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid JSON response from LinkedIn API"
                )
        
        # --- PARSE RESPONSE (same for both modes) ---
        raw_posts_data = feed_service._parse_feed_response(response_data)
        logger.info(f"[FEED][{mode}] Successfully parsed {len(raw_posts_data)} posts")
        
        # Process and save posts
        processed_db_posts = await process_and_save_posts(raw_posts_data, db)
        
        # Build response
        response_items = await build_response_items(processed_db_posts, db)
        logger.info(f"[FEED][{mode}] Returning {len(response_items)} posts")
        return response_items
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[FEED][{mode}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )

