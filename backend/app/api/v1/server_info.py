"""
API endpoint for server information and announcements.

This endpoint provides dynamic server configuration information,
restrictions, and announcements that can be updated without changing the extension.
"""
import logging
import json
import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.api.v1.server_validation import SERVER_INSTANCE_ID, check_if_main_server
from app.core.edition import get_edition, get_channel
from app.__version__ import __version__

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/server",
    tags=["server"],
)


class ServerRestriction(BaseModel):
    """Server restriction information."""
    title: str = Field(..., description="Title of the restriction")
    message: str = Field(..., description="Restriction message")
    severity: str = Field("info", description="Severity level: info, warning, error")


class WhatsNewItem(BaseModel):
    """What's new announcement item."""
    version: str = Field(..., description="Version number")
    date: str = Field(..., description="Release date")
    title: str = Field(..., description="Update title")
    description: str = Field(..., description="Update description")
    highlights: list[str] = Field(default_factory=list, description="Key highlights")


class LinkedInLimit(BaseModel):
    """LinkedIn API limit information."""
    label: str = Field(..., description="Limit label")
    limit: int = Field(..., description="Limit value")
    recommended: int | None = Field(None, description="Recommended safe value")
    period: str = Field(..., description="Time period (WEEK, DAY)")


class ServerInfoResponse(BaseModel):
    """Response model for server information."""
    server_name: str = Field(..., description="Server name/identifier")
    version: str = Field(..., description="Server version (semantic versioning)")
    is_default_server: bool = Field(..., description="Whether this is the default production server")
    edition: str = Field(..., description="Server edition (core, saas)")
    channel: str = Field(..., description="Deployment channel (default, railway_private)")
    restrictions: list[ServerRestriction] = Field(default_factory=list, description="Server restrictions")
    whats_new: list[WhatsNewItem] = Field(default_factory=list, description="What's new announcements")
    linkedin_limits: list[LinkedInLimit] = Field(default_factory=list, description="LinkedIn API usage limits")


class InstanceIdResponse(BaseModel):
    """Response model for instance ID."""
    instance_id: str = Field(..., description="Unique instance identifier for this server")


def load_whats_new() -> list[WhatsNewItem]:
    """
    Load What's New announcements from the JSON file.
    
    Returns:
        List of WhatsNewItem objects loaded from whats_new.json
    """
    try:
        # Get the path to the JSON file (in the same directory as this module)
        current_dir = Path(__file__).parent
        json_path = current_dir / "whats_new.json"
        
        if not json_path.exists():
            logger.warning(f"What's New file not found at {json_path}, using empty list")
            return []
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to WhatsNewItem objects
        return [WhatsNewItem(**item) for item in data]
    
    except Exception as e:
        logger.error(f"Error loading What's New from JSON: {e}")
        return []


@router.get("/instance-id", response_model=InstanceIdResponse, summary="Get Server Instance ID", include_in_schema=False)
async def get_instance_id():
    """
    Get the unique instance ID for this server.
    
    This endpoint is used to verify if a server is the main/default production server
    by comparing instance IDs. The main server calls itself and compares IDs.
    
    Returns:
        InstanceIdResponse with the unique instance ID.
    """
    return InstanceIdResponse(instance_id=SERVER_INSTANCE_ID)


@router.get("/info", response_model=ServerInfoResponse, summary="Get Server Information", include_in_schema=False)
async def get_server_info():
    """
    Get server information including restrictions and announcements.
    
    This endpoint returns dynamic server configuration that can be updated
    without requiring extension updates. Includes:
    - Server restrictions (e.g., server-call limitations)
    - What's new announcements
    - Feature availability
    
    Returns:
        ServerInfoResponse with server information.
    """
    # Get edition and channel
    edition = get_edition()
    channel = get_channel()
    
    # Check if we're the main server by calling ourselves
    is_main = await check_if_main_server()
    
    # Build restrictions based on server type
    restrictions = []
    if is_main:
        restrictions.append(
            ServerRestriction(
                title="Server-Side Execution Restricted",
                message="Server-side execution (server_call=true) is not available on the default production server. You need your own private server to use this feature. All requests are processed through the secure proxy via your browser extension.",
                severity="info"
            )
        )
    
    server_name = "LinkedIn Gateway Production Server" if is_main else "LinkedIn Gateway Custom Server"
    
    return ServerInfoResponse(
        server_name=server_name,
        version=__version__,
        is_default_server=is_main,
        edition=edition,
        channel=channel,
        restrictions=restrictions,
        whats_new=load_whats_new(),
        linkedin_limits=[
            LinkedInLimit(
                label="Connections Requests",
                limit=100,
                recommended=80,
                period="WEEK"
            ),
            LinkedInLimit(
                label="Sent Messages",
                limit=100,
                recommended=None,
                period="WEEK"
            ),
            LinkedInLimit(
                label="Sent Messages (Premium)",
                limit=150,
                recommended=None,
                period="WEEK"
            ),
            LinkedInLimit(
                label="Full Profile Views",
                limit=50,
                recommended=40,
                period="DAY"
            ),
            LinkedInLimit(
                label="Premium Profile Views",
                limit=100,
                recommended=50,
                period="DAY"
            ),
            LinkedInLimit(
                label="Full Profile Views (Recruiter/Navigator)",
                limit=2000,
                recommended=1000,
                period="DAY"
            ),
            LinkedInLimit(
                label="Posts",
                limit=100,
                recommended=80,
                period="DAY"
            )
        ]
    )


@router.get("/restrictions", response_model=list[ServerRestriction], summary="Get Server Restrictions", include_in_schema=False)
async def get_server_restrictions():
    """
    Get current server restrictions.
    
    Returns only the restrictions without other server info.
    Useful for checking specific limitations.
    
    Returns:
        List of ServerRestriction objects.
    """
    info = await get_server_info()
    return info.restrictions


@router.get("/whats-new", response_model=list[WhatsNewItem], summary="Get What's New", include_in_schema=False)
async def get_whats_new():
    """
    Get what's new announcements.
    
    Returns recent updates and announcements without other server info.
    
    Returns:
        List of WhatsNewItem objects.
    """
    info = await get_server_info()
    return info.whats_new

