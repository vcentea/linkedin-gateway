"""
CRUD operations for posts.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.post import Post
from app.schemas.post import PostCreate


async def create_post(db: AsyncSession, post_in: PostCreate) -> Post:
    """
    Create a new post.
    
    Args:
        db: Database session
        post_in: Post data
        
    Returns:
        Post: Created post
    """
    db_post = Post(**post_in.model_dump())
    db.add(db_post)
    # Flush to send changes to DB within the transaction
    await db.flush()
    # Refresh to get the generated ID
    await db.refresh(db_post)
    # Removed await db.commit() - let the calling transaction handle it
    return db_post


async def get_post(db: AsyncSession, post_id: int) -> Optional[Post]:
    """
    Get a post by ID.
    
    Args:
        db: Database session
        post_id: Post ID
        
    Returns:
        Optional[Post]: Post if found, None otherwise
    """
    result = await db.execute(select(Post).where(Post.id == post_id))
    return result.scalar_one_or_none()


async def get_by_postid(db: AsyncSession, postid: str) -> Optional[Post]:
    """
    Get a post by its postid.
    
    Args:
        db: Database session
        postid: The post's unique identifier
        
    Returns:
        Optional[Post]: Post if found, None otherwise
    """
    result = await db.execute(select(Post).where(Post.postid == postid))
    return result.scalar_one_or_none()


async def get_posts(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> List[Post]:
    """
    Get a list of posts.
    
    Args:
        db: Database session
        skip: Number of posts to skip
        limit: Maximum number of posts to return
        
    Returns:
        List[Post]: List of posts
    """
    result = await db.execute(select(Post).offset(skip).limit(limit))
    return result.scalars().all() 