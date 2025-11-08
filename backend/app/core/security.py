import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional # Use Annotated for newer FastAPI

from fastapi import Response, Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer # Import OAuth2 scheme
from sqlalchemy.ext.asyncio import AsyncSession # Changed to AsyncSession
from sqlalchemy import select # Import select
from uuid import UUID

# Import passlib for hashing
from passlib.context import CryptContext

from ..db.session import get_db
from ..db.models.user import User, UserSession # UserSession model exists
from .config import settings

# --- Hashing Setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
# --- End Hashing Setup ---

# Define the OAuth2 scheme (tokenUrl is needed but can be dummy)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# Modified create_session to store provided token and expiry
async def create_session(
    user_id: UUID,
    db: AsyncSession, # Changed to AsyncSession
    linkedin_token: str,
    linkedin_expires_at: datetime
) -> str | None:
    """
    Creates/Updates a session for the user using the LinkedIn token.
    Returns the LinkedIn token (acting as session ID) or None if failed.
    
    Multi-session support: Allows multiple active sessions per user (different browsers/devices).
    Only deletes EXPIRED sessions, not active ones.
    """
    session_token = linkedin_token # Use the LinkedIn token as the session identifier
    expires_at = linkedin_expires_at
    current_time = datetime.utcnow() # This is already UTC naive
    
    try:
        # Clean up ONLY expired sessions for this user (not all sessions!)
        # This allows multiple browsers/devices to be logged in simultaneously
        stmt = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.expires_at < current_time  # Only expired sessions
        )
        result = await db.execute(stmt)
        expired_sessions = result.scalars().all()
        if expired_sessions:
            print(f"Found {len(expired_sessions)} expired sessions for user {user_id} to delete.")
            for session_to_delete in expired_sessions:
                await db.delete(session_to_delete)
            await db.flush() # Ensure deletions are flushed before adding new session
            print(f"Expired sessions deleted for user {user_id}.")
        else:
            print(f"No expired sessions found for user {user_id}.")
        
        # Check if this exact session token already exists (refresh scenario)
        stmt = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.session_token == session_token
        )
        result = await db.execute(stmt)
        existing_session = result.scalar_one_or_none()
        
        if existing_session:
            # Update existing session's expiry
            print(f"Updating existing session for user {user_id}")
            existing_session.expires_at = expires_at.replace(tzinfo=None)
            existing_session.last_activity = current_time
        else:
            # Create new session (allows multiple active sessions)
            print(f"Creating new session for user {user_id} (multi-session support)")
            new_session = UserSession(
                user_id=user_id,
                session_token=session_token,
                expires_at=expires_at.replace(tzinfo=None), # Make datetime naive UTC
                last_activity=current_time # Already naive UTC
            )
            db.add(new_session)
        
        await db.commit()
        print(f"Stored session token (LinkedIn token) for user {user_id}")
        return session_token
    except Exception as e:
        await db.rollback()
        print(f"Error storing session for user {user_id}: {e}")
        return None

# Dependency to get user from Bearer token
async def get_current_user_from_token(token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)) -> User | None:
    """
    Dependency to get the current user based on the Bearer token.
    Looks up the token in the UserSession table.
    """
    if not token:
        return None

    try:
        current_time = datetime.utcnow() # Use UTC naive
        stmt = select(UserSession).where(
            UserSession.session_token == token,
            UserSession.expires_at > current_time
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            print(f"Session token not found or expired in DB")
            return None
            
        # Optional: Update last_activity
        session.last_activity = current_time
        await db.commit() # Commit the last_activity update
        
        # Fetch the associated user
        user_stmt = select(User).where(User.id == session.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        return user
        
    except Exception as e:
        print(f"Error validating token from DB session: {e}")
        return None

# Dependency to get the active user, raising errors if not found/inactive
async def get_current_active_user(
    current_user: Annotated[User | None, Depends(get_current_user_from_token)]
) -> User:
    """Dependency that requires an active, authenticated user."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

# Placeholder for JWT functions if needed later
# from jose import JWTError, jwt
# def create_access_token(data: dict, expires_delta: timedelta | None = None):
#     to_encode = data.copy()
#     if expires_delta:
#         expire = datetime.utcnow() + expires_delta
#     else:
#         expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
#     return encoded_jwt

# def verify_token(token: str):
#     try:
#         payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
#         user_id: str = payload.get("sub")
#         if user_id is None:
#             return None
#         return user_id
#     except JWTError:
#         return None 