"""
Helper functions for Gemini AI integration.

Provides utilities for:
- Getting initialized Gemini services
- Building request headers
- User agent generation
"""
import logging
import platform
from typing import Optional, Type, TypeVar, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.api_key import APIKey
from .config import CLI_VERSION, CODE_ASSIST_ENDPOINT
from .auth import load_credentials_from_dict, refresh_credentials_if_needed, credentials_to_dict

logger = logging.getLogger(__name__)

# Type variable for service classes
T = TypeVar('T')


def get_user_agent() -> str:
    """
    Generate a user agent string that mimics the Gemini CLI.
    
    The CLI uses format: GeminiCLI/{version} ({platform}; {arch})
    
    Returns:
        User agent string
    """
    os_name = platform.system().lower()
    arch = platform.machine().lower()
    
    # Map to CLI's platform names
    if arch in ["amd64", "x86_64"]:
        arch = "x64"
    elif arch in ["arm64", "aarch64"]:
        arch = "arm64"
    
    user_agent = f"GeminiCLI/{CLI_VERSION} ({os_name}; {arch})"
    logger.info(f"[USER_AGENT] Generated: {user_agent}")
    return user_agent


def get_platform_string() -> str:
    """
    Generate platform string matching gemini-cli format.
    
    Returns:
        Platform identifier string
    """
    system = platform.system().upper()
    arch = platform.machine().upper()
    
    if system == "DARWIN":
        return "DARWIN_ARM64" if arch in ["ARM64", "AARCH64"] else "DARWIN_AMD64"
    elif system == "LINUX":
        return "LINUX_ARM64" if arch in ["ARM64", "AARCH64"] else "LINUX_AMD64"
    elif system == "WINDOWS":
        return "WINDOWS_AMD64"
    return "PLATFORM_UNSPECIFIED"


def get_client_metadata(project_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate client metadata for API requests.
    Matches the exact format used by gemini-cli.
    
    Args:
        project_id: Optional Google Cloud project ID (duetProject)
        
    Returns:
        Client metadata dictionary
    """
    metadata = {
        "ideName": "IDE_UNSPECIFIED",
        "ideType": "IDE_UNSPECIFIED",
        "platform": get_platform_string(),
        "pluginType": "GEMINI",
        "ideVersion": CLI_VERSION,
        "updateChannel": "nightly",  # Enable preview/experimental features
        "duetProject": project_id,
    }
    return metadata


def build_request_headers(access_token: str) -> Dict[str, str]:
    """
    Build HTTP headers for Gemini API requests.
    
    Args:
        access_token: Valid OAuth access token
        
    Returns:
        Dictionary of headers
    """
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": get_user_agent(),
    }


async def get_gemini_credentials_for_key(
    db: AsyncSession,
    api_key: APIKey
) -> Optional[Dict[str, Any]]:
    """
    Get Gemini credentials from an API key, refreshing if necessary.
    
    If credentials are expired and refreshed, updates the database.
    
    Args:
        db: Database session
        api_key: APIKey model instance
        
    Returns:
        Valid credentials dictionary or None
    """
    creds_dict = api_key.gemini_credentials
    
    if not creds_dict:
        logger.warning(f"No Gemini credentials for API key {api_key.prefix}")
        return None
    
    # Load credentials
    credentials = load_credentials_from_dict(creds_dict)
    if not credentials:
        return None
    
    # Check if refresh is needed
    was_refreshed, credentials = refresh_credentials_if_needed(credentials)
    
    if was_refreshed and credentials:
        # Update the stored credentials with new token
        new_creds_dict = credentials_to_dict(credentials)
        api_key.gemini_credentials = new_creds_dict
        db.add(api_key)
        await db.flush()
        logger.info(f"Updated refreshed credentials for API key {api_key.prefix}")
        return new_creds_dict
    
    if credentials:
        return creds_dict
    
    return None


async def get_gemini_service(
    db: AsyncSession,
    api_key: APIKey,
    service_class: Type[T]
) -> T:
    """
    Factory function to get an initialized Gemini service.
    
    Similar pattern to LinkedIn's get_linkedin_service.
    
    Args:
        db: Database session
        api_key: APIKey model instance
        service_class: The service class to instantiate
        
    Returns:
        Initialized service instance
        
    Raises:
        ValueError: If credentials are not available or invalid
    """
    creds_dict = await get_gemini_credentials_for_key(db, api_key)
    
    if not creds_dict:
        raise ValueError(
            "Gemini credentials not configured. "
            "Please connect your Google account via the extension."
        )
    
    # Load and validate credentials
    credentials = load_credentials_from_dict(creds_dict)
    
    if not credentials or not credentials.token:
        raise ValueError("Invalid or expired Gemini credentials")
    
    # Create service instance
    return service_class(
        credentials=credentials,
        api_key=api_key,
        db=db
    )


def get_gemini_api_url(action: str, streaming: bool = False) -> str:
    """
    Build the Gemini API URL for a given action.
    
    Args:
        action: API action (e.g., 'generateContent', 'streamGenerateContent')
        streaming: Whether this is a streaming request
        
    Returns:
        Full API URL
    """
    url = f"{CODE_ASSIST_ENDPOINT}/v1internal:{action}"
    if streaming:
        url += "?alt=sse"
    return url

