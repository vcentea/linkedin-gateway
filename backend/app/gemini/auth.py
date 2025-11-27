"""
Authentication and credential management for Gemini API.

Handles Google OAuth 2.0 credential loading, validation, and refresh.
Based on geminicli2api (https://github.com/gzzhongqi/geminicli2api)
"""
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest

from .config import GEMINI_CLIENT_ID, GEMINI_CLIENT_SECRET, GEMINI_SCOPES, TOKEN_URI

logger = logging.getLogger(__name__)


def load_credentials_from_dict(creds_dict: Dict[str, Any]) -> Optional[Credentials]:
    """
    Load Google OAuth credentials from a dictionary.
    
    The dictionary should contain:
    - client_id: OAuth client ID (defaults to Gemini CLI public credentials)
    - client_secret: OAuth client secret (defaults to Gemini CLI public credentials)
    - token: Current access token
    - refresh_token: Refresh token for obtaining new access tokens
    - scopes: List of OAuth scopes (optional, defaults to GEMINI_SCOPES)
    - token_uri: Token exchange endpoint (optional, defaults to Google's)
    - expiry: Token expiry timestamp in ISO format (optional)
    
    Args:
        creds_dict: Dictionary containing OAuth credential fields
        
    Returns:
        Google Credentials object or None if loading fails
    """
    if not creds_dict:
        logger.warning("Empty credentials dictionary provided")
        return None
    
    # Check for required field - refresh_token is essential for long-term use
    if not creds_dict.get("refresh_token"):
        logger.warning("No refresh_token in credentials - cannot refresh expired tokens")
    
    try:
        # Normalize credential fields
        normalized = _normalize_credentials(creds_dict)
        
        # Create credentials object
        credentials = Credentials.from_authorized_user_info(normalized, GEMINI_SCOPES)
        
        logger.info("Successfully loaded Gemini credentials from dictionary")
        return credentials
        
    except Exception as e:
        logger.error(f"Failed to load credentials from dictionary: {e}")
        return None


def _normalize_credentials(creds_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize credential dictionary to expected format.
    
    Handles variations in field names and formats.
    """
    normalized = creds_dict.copy()
    
    # Use Gemini CLI public credentials if not provided
    if "client_id" not in normalized:
        normalized["client_id"] = GEMINI_CLIENT_ID
    if "client_secret" not in normalized:
        normalized["client_secret"] = GEMINI_CLIENT_SECRET
    if "token_uri" not in normalized:
        normalized["token_uri"] = TOKEN_URI
    
    # Handle access_token vs token naming
    if "access_token" in normalized and "token" not in normalized:
        normalized["token"] = normalized["access_token"]
    
    # Handle scope vs scopes naming
    if "scope" in normalized and "scopes" not in normalized:
        scope_str = normalized["scope"]
        normalized["scopes"] = scope_str.split() if isinstance(scope_str, str) else scope_str
    
    # Handle expiry format issues
    if "expiry" in normalized:
        expiry_str = normalized["expiry"]
        if isinstance(expiry_str, str):
            try:
                # Handle various ISO format variations
                if "+00:00" in expiry_str:
                    parsed = datetime.fromisoformat(expiry_str)
                elif expiry_str.endswith("Z"):
                    parsed = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                else:
                    parsed = datetime.fromisoformat(expiry_str)
                
                # Convert to format expected by google-auth
                normalized["expiry"] = parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
                
            except Exception as e:
                logger.warning(f"Could not parse expiry format '{expiry_str}': {e}")
                # Remove problematic expiry - credentials will be treated as expired
                del normalized["expiry"]
    
    return normalized


def refresh_credentials_if_needed(credentials: Credentials) -> Tuple[bool, Optional[Credentials]]:
    """
    Refresh credentials if they are expired.
    
    Args:
        credentials: Google Credentials object
        
    Returns:
        Tuple of (was_refreshed: bool, credentials: Credentials or None on failure)
    """
    if not credentials:
        return False, None
    
    # Check if refresh is needed
    if not credentials.expired:
        return False, credentials
    
    # Check if we can refresh
    if not credentials.refresh_token:
        logger.error("Credentials expired but no refresh_token available")
        return False, None
    
    try:
        logger.info("Refreshing expired Gemini credentials...")
        credentials.refresh(GoogleAuthRequest())
        logger.info("Gemini credentials refreshed successfully")
        return True, credentials
        
    except Exception as e:
        logger.error(f"Failed to refresh credentials: {e}")
        return False, None


def credentials_to_dict(credentials: Credentials) -> Dict[str, Any]:
    """
    Convert Credentials object back to dictionary for storage.
    
    Args:
        credentials: Google Credentials object
        
    Returns:
        Dictionary suitable for storage
    """
    creds_dict = {
        "client_id": credentials.client_id or GEMINI_CLIENT_ID,
        "client_secret": credentials.client_secret or GEMINI_CLIENT_SECRET,
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "scopes": list(credentials.scopes) if credentials.scopes else GEMINI_SCOPES,
        "token_uri": credentials.token_uri or TOKEN_URI,
    }
    
    if credentials.expiry:
        # Ensure expiry is in UTC
        if credentials.expiry.tzinfo is None:
            expiry_utc = credentials.expiry.replace(tzinfo=timezone.utc)
        else:
            expiry_utc = credentials.expiry
        creds_dict["expiry"] = expiry_utc.isoformat()
    
    return creds_dict


def validate_credentials(creds_dict: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate that credentials dictionary has required fields.
    
    Args:
        creds_dict: Dictionary to validate
        
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    if not creds_dict:
        return False, "Empty credentials"
    
    # refresh_token is required for long-term use
    if not creds_dict.get("refresh_token"):
        return False, "Missing refresh_token - required for token refresh"
    
    # Must have either token or ability to get one
    if not creds_dict.get("token") and not creds_dict.get("refresh_token"):
        return False, "Must have either token or refresh_token"
    
    return True, ""


def get_access_token(credentials: Credentials) -> Optional[str]:
    """
    Get a valid access token, refreshing if necessary.
    
    Args:
        credentials: Google Credentials object
        
    Returns:
        Valid access token or None
    """
    if not credentials:
        return None
    
    # Refresh if expired
    if credentials.expired and credentials.refresh_token:
        was_refreshed, credentials = refresh_credentials_if_needed(credentials)
        if not was_refreshed and not credentials:
            return None
    
    return credentials.token

