"""
CRUD operations for profiles.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.profile import Profile
from app.schemas.profile import ProfileCreate, ProfileUpdate

# Import the WebSocket helper for profile actions
from app.ws.profile_actions import request_profile_data_via_websocket


async def create_profile(
    db: AsyncSession,
    profile_in: ProfileCreate,
    ws_handler=None,
    user_id: Optional[str] = None
) -> Profile:
    """
    Create a new profile. If ws_handler and user_id are provided, fetch vanity name via WebSocket.
    
    Args:
        db: Database session
        profile_in: Profile data
        ws_handler: Optional WebSocketEventHandler for fetching vanity name
        user_id: Optional user ID for WebSocket targeting
    Returns:
        Profile: Created profile
    """
    vanity_name = None
    if ws_handler and user_id and profile_in.linkedin_id:
        try:
            profile_data = await request_profile_data_via_websocket(
                ws_event_handler=ws_handler,
                user_id=user_id,
                profile_id=profile_in.linkedin_id,
                request_type="vanity_name",
                timeout=60.0
            )
            vanity_name = profile_data.get("vanity_name")
        except Exception as e:
            # Log error, but do not block profile creation
            import logging
            logging.getLogger(__name__).warning(f"Could not fetch vanity name: {e}")
    # Prepare profile data
    profile_data = profile_in.model_dump()
    if vanity_name:
        profile_data["vanity_name"] = vanity_name
    db_profile = Profile(**profile_data)
    db.add(db_profile)
    await db.flush()
    await db.refresh(db_profile)
    return db_profile


async def get_profile(db: AsyncSession, profile_id: int) -> Optional[Profile]:
    """
    Get a profile by ID.
    
    Args:
        db: Database session
        profile_id: Profile ID
        
    Returns:
        Optional[Profile]: Profile if found, None otherwise
    """
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    return result.scalar_one_or_none()


async def get_by_profileid(db: AsyncSession, profileid: str) -> Optional[Profile]:
    """
    Get a profile by its linkedin_id.
    
    Args:
        db: Database session
        profileid: The profile's LinkedIn ID
        
    Returns:
        Optional[Profile]: Profile if found, None otherwise
    """
    result = await db.execute(select(Profile).where(Profile.linkedin_id == profileid))
    return result.scalar_one_or_none()


async def get_profiles(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> List[Profile]:
    """
    Get a list of profiles.
    
    Args:
        db: Database session
        skip: Number of profiles to skip
        limit: Maximum number of profiles to return
        
    Returns:
        List[Profile]: List of profiles
    """
    result = await db.execute(select(Profile).offset(skip).limit(limit))
    return result.scalars().all()


async def get_by_vanity_name(db: AsyncSession, vanity_name: str) -> Optional[Profile]:
    """
    Get a profile by its vanity_name.
    
    Args:
        db: Database session
        vanity_name: The profile's vanity name (case-insensitive match).
        
    Returns:
        Optional[Profile]: Profile if found, None otherwise
    """
    # Perform case-insensitive search for vanity name
    stmt = select(Profile).where(Profile.vanity_name.ilike(vanity_name))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_profile(
    db: AsyncSession,
    db_obj: Profile,
    obj_in: ProfileUpdate | Dict[str, Any]
) -> Profile:
    """
    Update an existing profile.

    Args:
        db: Database session.
        db_obj: The profile object to update.
        obj_in: ProfileUpdate schema or dict containing update data.

    Returns:
        The updated profile object.
    """
    from pydantic import BaseModel
    
    if isinstance(obj_in, dict):
        update_data = obj_in
    elif isinstance(obj_in, BaseModel):
        # Use model_dump with exclude_unset=True to only update provided fields
        update_data = obj_in.model_dump(exclude_unset=True)
    else:
        raise ValueError("obj_in must be a ProfileUpdate schema or a dict")

    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    await db.flush()
    await db.refresh(db_obj)
    # Commit is handled by the get_db context manager
    return db_obj 