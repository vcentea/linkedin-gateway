"""
Validation utilities for authentication and user data.
"""
import re
from typing import Tuple


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email format using basic regex.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Basic email regex pattern
    email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    
    if not email:
        return False, "Email is required"
    
    if not re.match(email_pattern, email.strip()):
        return False, "Invalid email format"
    
    return True, ""


def is_local_user(linkedin_id: str) -> bool:
    """
    Check if a user is a local (email/password) user.
    
    Local users have LinkedIn IDs starting with "LOCAL_".
    
    Args:
        linkedin_id: LinkedIn ID to check
        
    Returns:
        True if local user, False if LinkedIn OAuth user
    """
    return linkedin_id.startswith("LOCAL_") if linkedin_id else False


def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"
    
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    
    # Add more password requirements if needed
    # For now, we keep it simple
    
    return True, ""

