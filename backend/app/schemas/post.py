"""
Pydantic schemas for posts.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class PostBase(BaseModel):
    """Base schema for post data."""
    postid: str = Field(..., description="Unique identifier for the post")
    ugcpostid: Optional[str] = Field(None, description="User-generated content post ID")
    url: Optional[str] = Field(None, description="URL of the post")
    snippet: Optional[str] = Field(None, description="Post snippet")
    author_id: int = Field(..., description="ID of the post author")
    reactions: Optional[int] = Field(None, description="Number of reactions")
    comments: Optional[int] = Field(None, description="Number of comments")
    reposts: Optional[int] = Field(None, description="Number of reposts")
    engagement: Optional[int] = Field(None, description="Total engagement count")
    postcontent: Optional[str] = Field(None, description="Full post content")
    timestamp: Optional[datetime] = Field(None, description="Post timestamp")
    shareurn: Optional[str] = Field(None, description="Share URN")
    post_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional post metadata")


class PostCreate(PostBase):
    """Schema for creating a new post."""
    pass


class PostUpdate(PostBase):
    """Schema for updating an existing post."""
    pass


class PostInDB(PostBase):
    """Schema for post data as stored in the database."""
    id: int = Field(..., description="Database ID of the post")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class CommenterDetail(BaseModel):
    userId: str = Field(..., description="Unique ID of the commenter.")
    userName: str = Field(..., description="Full name of the commenter.")
    userTitle: Optional[str] = Field(None, description="Job title/headline of the commenter.")
    connectionLevel: Optional[str] = Field(None, description="Connection level with the commenter (e.g., '1st', '2nd', '3rd+').")
    commentText: str = Field(..., description="The text content of the comment.")
    commentUrn: Optional[str] = Field(None, description="URN of the comment for replying (e.g., 'urn:li:fsd_comment:(7373608379778441216,urn:li:ugcPost:7370796586257395712)').")
    isReply: bool = Field(False, description="True if this is a reply to another comment, False if it's a direct comment on the post.")
    parentCommentId: Optional[str] = Field(None, description="The comment ID of the parent comment if this is a reply. Extracted from SocialDetail.threadUrn.")
    childCommentIds: Optional[List[str]] = Field(None, description="List of comment IDs for replies to this comment. Extracted from SocialDetail.comments.elements.")


class GetCommentersRequest(BaseModel):
    post_url: str = Field(..., description="The full URL of the LinkedIn post.")
    count: int = Field(-1, description="Number of comments to fetch. Use -1 to fetch all comments (with pagination), or specify a positive number to fetch up to that many comments.")
    num_replies: Optional[int] = Field(1, description="Number of replies to fetch per comment.")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")
    min_delay: Optional[float] = Field(2.0, ge=0, le=30, description="Minimum delay in seconds between paginated requests (default: 2.0)")
    max_delay: Optional[float] = Field(5.0, ge=0, le=60, description="Maximum delay in seconds between paginated requests (default: 5.0)")


class GetCommentersResponse(BaseModel):
    data: List[CommenterDetail] = Field(..., description="List of commenter details.")


class PostCommentRequest(BaseModel):
    """Request model for posting a comment to a LinkedIn post."""
    post_url: str = Field(
        ..., 
        description="Full LinkedIn post URL OR post ID (e.g., 'https://www.linkedin.com/posts/username_activity-123...' or 'activity:123' or 'ugcPost:123')"
    )
    comment_text: str = Field(..., description="The text content of the comment")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use proxy via extension")


class ReplyToCommentRequest(BaseModel):
    """Request model for replying to a specific comment."""
    comment_urn: str = Field(
        ..., 
        description="The URN of the comment to reply to (from get-commenters endpoint, e.g., 'urn:li:fsd_comment:(7383266296794161153,urn:li:activity:7383255837701591040)')"
    )
    reply_text: str = Field(..., description="The text content of the reply")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use proxy via extension")


class CommentResponse(BaseModel):
    """Response model for comment operations."""
    success: bool = Field(..., description="Whether the operation was successful")


class ReactorDetail(BaseModel):
    """Detail about a user who reacted to a post."""
    userId: str = Field(..., description="Unique ID of the reactor.")
    userName: str = Field(..., description="Full name of the reactor.")
    userTitle: Optional[str] = Field(None, description="Job title/headline of the reactor.")
    connectionLevel: Optional[str] = Field(None, description="Connection level with the reactor (e.g., '1st', '2nd', '3rd+').")
    reactionType: str = Field("LIKE", description="Type of reaction (e.g., 'LIKE', 'CELEBRATE', 'SUPPORT', 'LOVE', 'INSIGHTFUL', 'FUNNY').")


class GetReactionsRequest(BaseModel):
    """Request model for fetching post reactions."""
    post_url: str = Field(..., description="The full URL of the LinkedIn post.")
    count: int = Field(-1, description="Number of reactions to fetch. Use -1 to fetch all reactions (with pagination), or specify a positive number to fetch up to that many reactions.")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")
    min_delay: Optional[float] = Field(2.0, ge=0, le=30, description="Minimum delay in seconds between paginated requests (default: 2.0)")
    max_delay: Optional[float] = Field(5.0, ge=0, le=60, description="Maximum delay in seconds between paginated requests (default: 5.0)")


class GetReactionsResponse(BaseModel):
    """Response model for fetching post reactions."""
    data: List[ReactorDetail] = Field(..., description="List of reactor details.")


class UserCommentDetail(BaseModel):
    """Detail about a comment made by a user."""
    commentText: str = Field(..., description="The user's comment text.")
    commentId: str = Field(..., description="The comment ID/URN.")
    postText: str = Field(..., description="The text of the post the user commented on.")
    postUrl: Optional[str] = Field(None, description="URL to the post.")
    parentCommentText: Optional[str] = Field(None, description="Parent comment text (if this is a reply).")
    parentCommentId: Optional[str] = Field(None, description="Parent comment ID (if this is a reply).")
    parentCommenterName: Optional[str] = Field(None, description="Name of the parent commenter (if this is a reply).")
    parentCommenterHeadline: Optional[str] = Field(None, description="Headline/title of the parent commenter (if this is a reply).")
    parentCommenterProfileId: Optional[str] = Field(None, description="Profile ID of the parent commenter (if this is a reply).")
    isReply: bool = Field(False, description="True if this is a reply to another comment.")
    replyToUserCommentText: Optional[str] = Field(None, description="Text of reply to user's comment (if any).")
    replyToUserCommentId: Optional[str] = Field(None, description="ID of reply to user's comment (if any).")


class GetUserCommentsRequest(BaseModel):
    """Request model for fetching user profile comments."""
    profile_id: str = Field(..., description="LinkedIn profile ID (e.g., 'ACoAABkVEvgBp3i06XxDrVLz2rUjmE4TqHNSPGI') or profile URL (e.g., 'https://www.linkedin.com/in/username/')")
    count: int = Field(-1, ge=-1, le=200, description="Number of comments to fetch. Use -1 to fetch all (with pagination, capped at 200).")
    api_key: Optional[str] = Field(default=None, description="API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")
    min_delay: Optional[float] = Field(2.0, ge=0, le=30, description="Min delay between paginated requests (default: 2.0)")
    max_delay: Optional[float] = Field(5.0, ge=0, le=60, description="Max delay between paginated requests (default: 5.0)")


class GetUserCommentsResponse(BaseModel):
    """Response model for fetching user profile comments."""
    data: List[UserCommentDetail] = Field(..., description="List of user comments with context.")


class ProfilePostDetail(BaseModel):
    postId: str = Field(..., description="Post ID URN")
    postUrl: str = Field(..., description="URL to the post")
    ugcPostId: Optional[str] = Field(None, description="UGC Post ID if available")
    articleId: Optional[str] = Field(None, description="Article ID if post is an article")
    videoAssetId: Optional[str] = Field(None, description="Video asset ID if post contains video")
    authorName: Optional[str] = Field(None, description="Author name (may differ from profile owner for reposts)")
    authorProfileId: Optional[str] = Field(None, description="Author LinkedIn profile ID")
    postContent: str = Field(..., description="Post content text")
    postDate: Optional[str] = Field(None, description="Post publication date (ISO format, calculated from relative time)")
    postAge: Optional[str] = Field(None, description="How old the post is from LinkedIn (e.g., '1d', '2w ago', '3mo')")
    likes: int = Field(0, description="Number of likes")
    comments: int = Field(0, description="Number of comments")
    imageUrl: Optional[str] = Field(None, description="URL to post image if available")
    isVideo: bool = Field(False, description="Whether the post contains video")
    hasVideo: bool = Field(False, description="Whether the post has video content")
    videoType: Optional[str] = Field(None, description="Type of video (e.g., 'linkedin', 'external')")


class GetProfilePostsRequest(BaseModel):
    profile_id: str = Field(..., description="The LinkedIn profile ID (e.g., 'ACoAACMM5dYBNanTp_QOusBX7d2mYYF2MalFm9g') or profile URL (e.g., 'https://www.linkedin.com/in/username/')")
    count: int = Field(default=10, ge=1, le=500, description="Number of posts to retrieve (will paginate automatically in chunks of 20)")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")
    min_delay: Optional[float] = Field(2.0, ge=0, le=30, description="Minimum delay in seconds between paginated requests (default: 2.0)")
    max_delay: Optional[float] = Field(5.0, ge=0, le=60, description="Maximum delay in seconds between paginated requests (default: 5.0)")


class GetProfilePostsResponse(BaseModel):
    posts: List[ProfilePostDetail] = Field(..., description="List of post details.")
    hasMore: bool = Field(..., description="Whether more posts are available")
    paginationToken: Optional[str] = Field(None, description="Token for next page")


class GetPostTextRequest(BaseModel):
    post_url: str = Field(..., description="The full URL of the LinkedIn post.")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")


class GetPostTextResponse(BaseModel):
    postText: Optional[str] = Field(None, description="The text content of the post. None if not found.")
    postUrl: str = Field(..., description="The URL of the post that was requested.") 
