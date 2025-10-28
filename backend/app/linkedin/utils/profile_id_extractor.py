"""
Shared utility for extracting LinkedIn profile IDs from URLs.

This module provides a reusable function for converting LinkedIn profile URLs
to profile IDs, used by both the posts service and profile service.

NEW: Uses HTML parsing approach via internal endpoint for better reliability.
OLD: GraphQL API approach (kept as legacy for rollback if needed).
"""
import logging
import re
import httpx
from typing import Dict
import os

logger = logging.getLogger(__name__)


async def _extract_profile_id_from_html(html: str, vanity_name: str) -> str:
    """
    Extract profile ID from HTML content by parsing bpr-guid code blocks.
    
    Args:
        html: HTML content from LinkedIn profile page
        vanity_name: The vanity name to match against
        
    Returns:
        The extracted profile ID
        
    Raises:
        ValueError: If profile ID cannot be extracted
    """
    from html import unescape
    import json
    
    # Pattern: <code id="bpr-guid-XXX">JSON</code>
    #          <code id="datalet-bpr-guid-XXX">{"request":"/voyager/api/graphql?variables=(vanityName:...)
    
    # Find all bpr-guid pairs
    pattern = r'<code[^>]*id="bpr-guid-(\d+)"[^>]*>([^<]+)</code>\s*<code[^>]*id="datalet-bpr-guid-\1"[^>]*>([^<]+)</code>'
    
    for match in re.finditer(pattern, html, re.DOTALL):
        guid = match.group(1)
        data_content = match.group(2)
        metadata_content = match.group(3)
        
        # Check if this is the voyagerIdentityDashProfiles GraphQL response
        if 'voyagerIdentityDashProfiles' in metadata_content and f'vanityName:{vanity_name}' in metadata_content:
            logger.info(f"Found voyagerIdentityDashProfiles block for vanity name: {vanity_name}")
            
            # Decode HTML entities
            decoded = unescape(data_content)
            
            try:
                # Parse JSON
                data = json.loads(decoded)
                
                # Extract from identityDashProfilesByMemberIdentity.*elements[0]
                elements = (data.get('data', {})
                               .get('data', {})
                               .get('identityDashProfilesByMemberIdentity', {})
                               .get('*elements', []))
                
                if elements:
                    urn = elements[0]
                    # Extract ID from URN: urn:li:fsd_profile:PROFILE_ID
                    urn_match = re.search(r'urn:li:fsd_profile:([A-Za-z0-9_-]+)', urn)
                    if urn_match:
                        profile_id = urn_match.group(1)
                        logger.info(f"Successfully extracted profile ID from HTML: {profile_id}")
                        return profile_id
                        
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from bpr-guid-{guid}: {e}")
                continue
    
    raise ValueError(f"Could not find profile ID in HTML for vanity name: {vanity_name}")


async def extract_profile_id(
    profile_input: str,
    headers: Dict[str, str],
    timeout: float = 30.0
) -> str:
    """
    Extract profile ID from LinkedIn profile URL or return as-is if already an ID.
    
    NEW IMPLEMENTATION: Uses HTML parsing via internal /api/v1/utils/extract-profile-id endpoint.
    This approach is more reliable as it doesn't require CSRF token validation.
    
    Args:
        profile_input: LinkedIn profile URL or profile ID
        headers: HTTP headers with authentication cookies
        timeout: Request timeout in seconds
        
    Returns:
        The extracted profile ID
        
    Raises:
        ValueError: If profile ID cannot be extracted
    """
    logger.info(f"extractProfileId called with: {profile_input}")
    
    # First, try to extract from the URL if it's a direct profile ID URL
    urn_match = re.search(r'urn:li:fsd_profile:([A-Za-z0-9_-]+)', profile_input)
    if urn_match:
        logger.info(f"Extracted profile ID from URN: {urn_match.group(1)}")
        return urn_match.group(1)
    
    # Check if input is already a profile ID (not a URL)
    if not re.search(r'https?://|linkedin\.com', profile_input, re.IGNORECASE):
        # Validate it looks like a profile ID
        if re.match(r'^[A-Za-z0-9_-]+$', profile_input):
            logger.info(f"Input is already a profile ID: {profile_input}")
            return profile_input
    
    # Direct HTML-based extraction (bypass internal endpoint to avoid auth complexity)
    try:
        # Extract vanity name from URL
        vanity_match = re.search(r'linkedin\.com/in/([^/\?]+)', profile_input)
        if not vanity_match:
            raise ValueError(f"Could not extract vanity name from URL: {profile_input}")
        
        vanity_name = vanity_match.group(1)
        logger.info(f"Extracted vanity name: {vanity_name}")
        
        # Build profile URL
        profile_url = f"https://www.linkedin.com/in/{vanity_name}/"
        
        logger.info(f"Fetching profile HTML for: {profile_url}")
        
        # Fetch the profile HTML page
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(profile_url, headers=headers)
            response.raise_for_status()
            html = response.text
        
        # Extract profile ID from HTML using same logic as endpoint
        profile_id = await _extract_profile_id_from_html(html, vanity_name)
        
        logger.info(f"Successfully extracted profile ID: {profile_id}")
        return profile_id
                
    except Exception as e:
        logger.error(f"Failed to extract profile ID: {str(e)}")
        raise ValueError(f"Failed to extract profile ID from URL '{profile_input}': {str(e)}")


async def extract_profile_id_graphql_legacy(
    profile_input: str,
    headers: Dict[str, str],
    timeout: float = 30.0
) -> str:
    """
    LEGACY: Extract profile ID using GraphQL API approach.
    
    This is the old implementation kept for rollback purposes.
    Uses LinkedIn's GraphQL API to resolve vanity names to profile IDs.
    
    WARNING: This approach sometimes fails with CSRF errors (403 Forbidden).
    Use the new extract_profile_id() function instead.
    
    Args:
        profile_input: LinkedIn profile URL or profile ID
        headers: HTTP headers with authentication cookies
        timeout: Request timeout in seconds
        
    Returns:
        The extracted profile ID
        
    Raises:
        ValueError: If profile ID cannot be extracted
    """
    logger.info(f"extractProfileId called with: {profile_input}")
    
    # First, try to extract from the URL if it's a direct profile ID URL
    urn_match = re.search(r'urn:li:fsd_profile:([A-Za-z0-9_-]+)', profile_input)
    if urn_match:
        logger.info(f"Extracted profile ID from URN: {urn_match.group(1)}")
        return urn_match.group(1)
    
    # Check if input is already a profile ID (not a URL)
    if not re.search(r'https?://|linkedin\.com', profile_input, re.IGNORECASE):
        # Validate it looks like a profile ID
        if re.match(r'^[A-Za-z0-9_-]+$', profile_input):
            logger.info(f"Input is already a profile ID: {profile_input}")
            return profile_input
    
    # Extract the vanity name from the URL
    vanity_match = re.search(r'linkedin\.com/in/([^/\?]+)', profile_input)
    if not vanity_match:
        raise ValueError(f"Could not extract vanity name from URL: {profile_input}")
    
    vanity_name = vanity_match.group(1)
    logger.info(f"Extracted vanity name: {vanity_name}")
    
    # Use LinkedIn's GraphQL API to get profile ID from vanity name
    graphql_url = (
        f"https://www.linkedin.com/voyager/api/graphql"
        f"?variables=(vanityName:{vanity_name})"
        f"&queryId=voyagerIdentityDashProfiles.34ead06db82a2cc9a778fac97f69ad6a"
    )
    
    logger.info(f"Fetching profile ID via GraphQL API for vanity name: {vanity_name}")
    
    # Ensure required headers are present for GraphQL
    # Must include browser-like headers to avoid 302 redirect
    # Start with headers from base.py (golden recipe)
    graphql_headers = {**headers}
    
    # Override/add ONLY the necessary headers for GraphQL
    # DO NOT duplicate x-restli-protocol-version (it's already in base headers)
    graphql_headers.update({
        'accept': 'application/vnd.linkedin.normalized+json+2.1',  # CRITICAL: Tells LinkedIn which format to return
    })
    
    # Log headers for debugging (excluding sensitive cookie data)
    logger.debug(f"GraphQL request headers: csrf-token={graphql_headers.get('csrf-token', 'MISSING')[:10]}..., " +
                f"has_cookie={bool(graphql_headers.get('cookie'))}")
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(
                graphql_url,
                headers=graphql_headers
            )
            
            logger.info(f"GraphQL response status: {response.status_code}")
            
            # Log response for debugging if not successful
            if response.status_code != 200:
                logger.error(f"GraphQL API error response: {response.text[:500]}")
            
            response.raise_for_status()
            data = response.json()
            
            logger.debug(f"GraphQL response received, status: {response.status_code}")
            
            # Search for the profile in the included array
            included = data.get('included', [])
            if not included:
                raise ValueError(f"No profile data found in GraphQL response for vanity name: {vanity_name}")
            
            # Find the profile object with matching publicIdentifier
            for item in included:
                if item.get('publicIdentifier') == vanity_name:
                    entity_urn = item.get('entityUrn', '')
                    
                    # Extract profile ID from URN format: urn:li:fsd_profile:PROFILE_ID
                    urn_match = re.search(r'urn:li:fsd_profile:([A-Za-z0-9_-]+)', entity_urn)
                    if urn_match:
                        profile_id = urn_match.group(1)
                        logger.info(f"Successfully extracted profile ID: {profile_id}")
                        return profile_id
            
            # If we get here, we didn't find the profile
            raise ValueError(f"Could not find profile with vanity name '{vanity_name}' in GraphQL response")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching profile ID: {e.response.status_code}")
        raise ValueError(f"Failed to extract profile ID from URL '{profile_input}': LinkedIn API returned {e.response.status_code}")
    except Exception as e:
        logger.error(f"Error extracting profile ID: {str(e)}")
        raise ValueError(f"Failed to extract profile ID from URL '{profile_input}': {str(e)}")

