"""
LinkedIn Connection Request API service.

Mirrors functionality from chrome-extension/src/services/profile_service.js
Provides server-side implementation of connection request operations.
"""
from typing import Dict, Any, Optional
from .base import LinkedInServiceBase
from ..utils.profile_id_extractor import extract_profile_id
import logging

logger = logging.getLogger(__name__)

class LinkedInConnectionService(LinkedInServiceBase):
    """Service for LinkedIn connection request operations."""
    
    async def send_simple_connection_request(self, profile_identifier: str) -> Dict[str, Any]:
        """
        Send a simple connection request without a message.
        
        Mirrors sendSimpleConnectionRequest from profile_service.js
        
        Args:
            profile_identifier: The LinkedIn profile ID or profile URL with vanity name.
            
        Returns:
            Dict containing the API response.
            
        Raises:
            ValueError: If profile_identifier is invalid.
            httpx.HTTPStatusError: If the API request fails.
        """
        if not profile_identifier:
            raise ValueError("profile_identifier is required")
        
        # Extract profile ID from URL or validate direct ID
        profile_id = await extract_profile_id(
            profile_input=profile_identifier,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        
        logger.info(f"Sending simple connection request to profile: {profile_id}")
        
        # Build the URL
        url = (
            f"{self.VOYAGER_BASE_URL}/voyagerRelationshipsDashMemberRelationships"
            f"?action=verifyQuotaAndCreateV2"
            f"&decorationId=com.linkedin.voyager.dash.deco.relationships.InvitationCreationResultWithInvitee-2"
        )
        
        # Build the payload
        payload = {
            "invitee": {
                "inviteeUnion": {
                    "memberProfile": f"urn:li:fsd_profile:{profile_id}"
                }
            }
        }
        
        # Add content-type header for POST request
        headers = {
            **self.headers,
            "Content-Type": "application/json",
        }
        
        # Make the request
        data = await self._make_request(
            url=url,
            method='POST',
            json=payload
        )
        
        logger.info(f"Successfully sent simple connection request to {profile_id}")
        return data
    
    async def send_connection_request_with_message(
        self, 
        profile_identifier: str, 
        message: str
    ) -> Dict[str, Any]:
        """
        Send a connection request with a custom message.
        
        Mirrors sendConnectionRequestWithMessage from profile_service.js
        
        Args:
            profile_identifier: The LinkedIn profile ID or profile URL with vanity name.
            message: The custom message to include with the connection request.
            
        Returns:
            Dict containing the API response.
            
        Raises:
            ValueError: If profile_identifier or message is invalid.
            httpx.HTTPStatusError: If the API request fails.
        """
        if not profile_identifier:
            raise ValueError("profile_identifier is required")
        
        if not message or not message.strip():
            raise ValueError("message is required and cannot be empty")
        
        # Extract profile ID from URL or validate direct ID
        profile_id = await extract_profile_id(
            profile_input=profile_identifier,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        
        logger.info(f"Sending connection request with message to profile: {profile_id}")
        
        # Build the URL
        url = (
            f"{self.VOYAGER_BASE_URL}/voyagerRelationshipsDashMemberRelationships"
            f"?action=verifyQuotaAndCreateV2"
            f"&decorationId=com.linkedin.voyager.dash.deco.relationships.InvitationCreationResultWithInvitee-2"
        )
        
        # Build the payload
        payload = {
            "invitee": {
                "inviteeUnion": {
                    "memberProfile": f"urn:li:fsd_profile:{profile_id}"
                }
            },
            "customMessage": message
        }
        
        # Add content-type header for POST request
        headers = {
            **self.headers,
            "Content-Type": "application/json",
        }
        
        # Make the request
        data = await self._make_request(
            url=url,
            method='POST',
            json=payload
        )
        
        logger.info(f"Successfully sent connection request with message to {profile_id}")
        return data

