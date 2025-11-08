"""
Local authentication routes for email/password login.
Only available on custom (non-main) servers.
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.session import get_db
from ..db.models.user import User
from ..core.config import settings
from ..core.security import verify_password, get_password_hash, create_session
from ..core.validators import is_local_user
from ..schemas.auth import (
    EmailLoginRequest,
    EmailRegisterRequest,
    AuthResponse,
    PasswordResetResponse,
    ErrorResponse
)
from ..api.v1.server_validation import check_if_main_server

logger = logging.getLogger(__name__)

router = APIRouter()


async def validate_custom_server_only():
    """
    Dependency to ensure local auth is only available on custom servers.
    
    Raises:
        HTTPException: 403 if called on main server
    """
    is_main = await check_if_main_server()
    
    if is_main:
        logger.warning("[LOCAL_AUTH] Attempted local auth on main server - BLOCKED")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Local authentication not available",
                "message": (
                    "Email/password authentication is only available on custom private servers. "
                    "The main production server uses LinkedIn OAuth only. "
                    "Please use 'Sign in with LinkedIn' or deploy your own private server."
                )
            }
        )


@router.post(
    "/login/email",
    response_model=AuthResponse,
    tags=["Authentication"],
    dependencies=[Depends(validate_custom_server_only)],
    summary="Login with Email/Password (Custom Servers Only)"
)
async def login_email(
    credentials: EmailLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user with email and password.
    
    Only available on custom servers, not on the main production server.
    
    - If user doesn't exist: Creates a new user with the provided credentials
    - If user exists: Validates password and logs in
    - If password is wrong: Returns error with reset instructions
    
    Args:
        credentials: Email and password
        db: Database session
        
    Returns:
        AuthResponse with user data and access token
        
    Raises:
        HTTPException: 401 if password is invalid
        HTTPException: 400 if email is invalid or other errors
    """
    logger.info(f"[LOCAL_AUTH] Login attempt for email: {credentials.email}")
    
    # Email and password validation happens on client side
    # Backend just processes the login
    email = credentials.email.lower().strip()
    
    try:
        # Check if user exists by email
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        existing_user = False
        
        if not user:
            # User doesn't exist - CREATE NEW USER
            logger.info(f"[LOCAL_AUTH] User not found, creating new user for: {email}")
            
            # Generate special LinkedIn ID for local users
            linkedin_id = f"LOCAL_{uuid.uuid4()}"
            
            # Hash the password
            password_hash = get_password_hash(credentials.password)
            
            # Create new user
            user = User(
                linkedin_id=linkedin_id,
                email=email,
                name=credentials.email.split('@')[0],  # Use email prefix as default name
                password_hash=password_hash,
                is_active=True
            )
            
            db.add(user)
            await db.flush()  # Get user ID
            await db.refresh(user)
            
            logger.info(f"[LOCAL_AUTH] New local user created: {user.id} with LinkedIn ID: {linkedin_id}")
            existing_user = False
            
        else:
            # User EXISTS - VERIFY PASSWORD
            logger.info(f"[LOCAL_AUTH] User found: {user.id}, verifying password")
            
            # Check if this is a local user (has password_hash)
            if not user.password_hash:
                # This is a LinkedIn OAuth user without a password
                logger.warning(f"[LOCAL_AUTH] User {email} is a LinkedIn user without password")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "This account uses LinkedIn authentication. "
                        "Please use 'Sign in with LinkedIn' instead."
                    )
                )
            
            # Verify password
            if not verify_password(credentials.password, user.password_hash):
                logger.warning(f"[LOCAL_AUTH] Invalid password for user: {email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "Invalid password. "
                        "Please contact your server administrator to reset your password."
                    )
                )
            
            logger.info(f"[LOCAL_AUTH] Password verified successfully for user: {user.id}")
            existing_user = True
        
        # Update last login
        user.last_login = datetime.utcnow()
        user.last_activity = datetime.utcnow()
        
        # Create session token (expires in 2 years)
        expires_at = datetime.now(timezone.utc) + timedelta(days=730)
        
        # Generate a session token
        session_token = f"LOCAL_SESSION_{uuid.uuid4()}"
        
        # Store session
        stored_token = await create_session(
            user_id=user.id,
            db=db,
            linkedin_token=session_token,
            linkedin_expires_at=expires_at
        )
        
        if not stored_token:
            logger.error(f"[LOCAL_AUTH] Failed to create session for user: {user.id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )
        
        logger.info(f"[LOCAL_AUTH] Session created successfully for user: {user.id}")
        
        # Return response in same format as LinkedIn OAuth
        return AuthResponse(
            status="success",
            accessToken=session_token,
            id=str(user.id),
            name=user.name,
            email=user.email,
            profile_picture_url=user.profile_picture_url,
            existing_user=existing_user,
            token_expires_at=expires_at.isoformat()
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"[LOCAL_AUTH] Error during email login: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )


@router.post(
    "/register/email",
    response_model=AuthResponse,
    tags=["Authentication"],
    dependencies=[Depends(validate_custom_server_only)],
    summary="Register with Email/Password (Custom Servers Only)"
)
async def register_email(
    registration: EmailRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user with email and password.
    
    This is essentially the same as login - if user doesn't exist, they're created.
    This endpoint is provided for semantic clarity.
    
    Only available on custom servers, not on the main production server.
    
    Args:
        registration: Email, password, and optional name
        db: Database session
        
    Returns:
        AuthResponse with user data and access token
    """
    # Convert to login request and use the same logic
    login_request = EmailLoginRequest(
        email=registration.email,
        password=registration.password
    )
    
    response = await login_email(login_request, db)
    
    # Update name if provided and user was just created
    if registration.name and not response.existing_user:
        try:
            result = await db.execute(
                select(User).where(User.email == registration.email.lower().strip())
            )
            user = result.scalar_one_or_none()
            if user:
                user.name = registration.name
                await db.flush()
                response.name = registration.name
                logger.info(f"[LOCAL_AUTH] Updated name for new user: {user.id}")
        except Exception as e:
            logger.warning(f"[LOCAL_AUTH] Failed to update user name: {e}")
    
    return response


@router.get(
    "/reset-password",
    response_model=PasswordResetResponse,
    tags=["Authentication"],
    dependencies=[Depends(validate_custom_server_only)],
    summary="Password Reset Instructions (Custom Servers Only)"
)
async def reset_password():
    """
    Get password reset instructions.
    
    For custom servers, password resets must be handled by the server administrator.
    This endpoint returns instructions to contact the administrator.
    
    Only available on custom servers, not on the main production server.
    
    Returns:
        PasswordResetResponse with contact instructions
    """
    admin_email = getattr(settings, 'ADMIN_EMAIL', None)
    
    return PasswordResetResponse(
        message="Please contact your server administrator to reset your password.",
        contact=admin_email
    )


@router.post(
    "/reset-password",
    response_model=PasswordResetResponse,
    tags=["Authentication"],
    dependencies=[Depends(validate_custom_server_only)],
    summary="Password Reset Request (Custom Servers Only)"
)
async def reset_password_post(email: EmailLoginRequest):
    """
    Handle password reset request (POST version).
    
    Same as GET version - returns instructions to contact administrator.
    
    Args:
        email: User email (for logging purposes)
        
    Returns:
        PasswordResetResponse with contact instructions
    """
    logger.info(f"[LOCAL_AUTH] Password reset requested for: {email.email}")
    
    admin_email = getattr(settings, 'ADMIN_EMAIL', None)
    
    return PasswordResetResponse(
        message="Please contact your server administrator to reset your password.",
        contact=admin_email
    )

