"""
Pydantic schemas for LinkedIn connection operations.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class GetConnectionsRequest(BaseModel):
    """Request model for fetching connections."""
    start_index: int = Field(0, description="Starting index for pagination", ge=0)
    count: int = Field(10, description="Number of connections to fetch (1-50)", ge=1, le=50)
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use proxy via extension")
    min_delay: Optional[float] = Field(2.0, ge=0, le=30, description="Minimum delay in seconds between paginated requests (default: 2.0)")
    max_delay: Optional[float] = Field(5.0, ge=0, le=60, description="Maximum delay in seconds between paginated requests (default: 5.0)")


class ConnectionDetail(BaseModel):
    """Detail of a single LinkedIn connection."""
    profile_id: str = Field(..., description="LinkedIn profile ID")
    name: str = Field(..., description="Full name of the connection")
    headline: Optional[str] = Field(None, description="Professional headline")
    profile_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    connected_date: Optional[str] = Field(None, description="Date when connection was established")
    
    class Config:
        from_attributes = True


class GetConnectionsResponse(BaseModel):
    """Response model for connections list."""
    data: List[ConnectionDetail] = Field(..., description="List of connection details")
    total: int = Field(..., description="Total number of connections returned")
    start_index: int = Field(..., description="Starting index used for this batch")

