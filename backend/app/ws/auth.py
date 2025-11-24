from jose import jwt, JWTError
from app.core.config import settings
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.db.session import get_db
from app.db.models.user import UserSession


async def validate_ws_token(token: Optional[str]) -> Optional[str]:
    """
    Validate a token from a WebSocket connection.
    Looks up the token in the UserSession table.
    
    Args:
        token: The session token to validate
        
    Returns:
        Optional[str]: The user_id if valid, None otherwise
    """
    if not token:
        print("No token provided for validation")
        return None
    
    try:
        # Get database session
        db = next(get_db())
        
        try:
            # Find session with this token
            print(f"Looking up token in UserSession table")
            session = db.query(UserSession).filter(
                UserSession.session_token == token,
                UserSession.expires_at > datetime.utcnow()
            ).first()

            if not session:
                print(f"No valid session found for token")
                return None

            # Update last activity
            session.last_activity = datetime.utcnow()
            db.commit()
            
            # Return the user ID
            user_id = str(session.user_id)
            print(f"Found valid session for user_id: {user_id}")
            return user_id
            
        except Exception as e:
            print(f"Error validating token against session: {e}")
            db.rollback()
            return None
            
    except Exception as e:
        print(f"Database error during token validation: {e}")
        return None 