"""
Authentication configuration check endpoint.
Allows clients to check if LinkedIn OAuth is properly configured.
"""
import logging
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["authentication-config"],
)


class LinkedInConfigStatus(BaseModel):
    """LinkedIn OAuth configuration status."""
    is_configured: bool = Field(..., description="Whether LinkedIn OAuth is fully configured")
    has_client_id: bool = Field(..., description="Whether LINKEDIN_CLIENT_ID is set")
    has_client_secret: bool = Field(..., description="Whether LINKEDIN_CLIENT_SECRET is set")
    setup_instructions: str | None = Field(None, description="Setup instructions if not configured")


@router.get("/linkedin/config-status", response_model=LinkedInConfigStatus)
async def check_linkedin_config():
    """
    Check if LinkedIn OAuth credentials are properly configured.
    
    Only checks if CLIENT_ID and CLIENT_SECRET are set on the server side.
    We cannot validate them without doing a full OAuth flow.
    Redirect URI should be validated on the client side.
    
    Returns configuration status and setup instructions if needed.
    Useful for custom servers to know if LinkedIn login should be enabled.
    
    Returns:
        LinkedInConfigStatus with configuration details
    """
    # Check if credentials are set and not placeholder values
    # LinkedIn Client IDs are typically 14 characters
    # LinkedIn Client Secrets are typically 16 characters
    has_client_id = bool(
        settings.LINKEDIN_CLIENT_ID and 
        settings.LINKEDIN_CLIENT_ID != "..." and
        len(settings.LINKEDIN_CLIENT_ID) >= 10
    )
    
    has_client_secret = bool(
        settings.LINKEDIN_CLIENT_SECRET and 
        settings.LINKEDIN_CLIENT_SECRET != "..." and
        len(settings.LINKEDIN_CLIENT_SECRET) >= 10
    )
    
    # Credentials are "configured" if both are set with reasonable values
    # We cannot validate them without doing OAuth, so we just check they exist
    is_configured = has_client_id and has_client_secret
    
    setup_instructions = None
    if not is_configured:
        missing = []
        if not has_client_id:
            missing.append("LINKEDIN_CLIENT_ID")
        if not has_client_secret:
            missing.append("LINKEDIN_CLIENT_SECRET")
        
        setup_instructions = (
            f"LinkedIn OAuth is not configured. Missing: {', '.join(missing)}.\n\n"
            "To enable LinkedIn authentication:\n"
            "1. Go to https://www.linkedin.com/developers/apps\n"
            "2. Create or select your app\n"
            "3. Get your Client ID and Client Secret from the 'Auth' tab\n"
            "4. Add these to your backend/.env file:\n"
            "   LINKEDIN_CLIENT_ID=your_client_id\n"
            "   LINKEDIN_CLIENT_SECRET=your_client_secret\n"
            "   LINKEDIN_REDIRECT_URI=https://your-domain.com/auth/user/callback\n"
            "5. Add the redirect URI to your LinkedIn app's 'Authorized redirect URLs'\n"
            "6. Restart the server"
        )
    
    logger.info(
        f"[AUTH_CONFIG] LinkedIn OAuth configured: {is_configured} "
        f"(ID: {has_client_id}, Secret: {has_client_secret})"
    )
    
    return LinkedInConfigStatus(
        is_configured=is_configured,
        has_client_id=has_client_id,
        has_client_secret=has_client_secret,
        setup_instructions=setup_instructions
    )

