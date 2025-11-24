"""
URL parsing utilities for LinkedIn.

Mirrors functionality from chrome-extension/src-v2/content/linkedin/feed.js
"""
import re
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def parse_linkedin_post_url(post_url: str) -> Optional[str]:
    """
    Parse a LinkedIn post URL to extract the URN (activity or ugcPost).
    
    Mirrors parseLinkedInPostUrl from feed.js
    
    Supports multiple URL formats:
    - URLs with direct URN notation: containing "urn:li:activity:1234567890"
    - URLs with simple ID notation: containing "activity:1234567890" or "ugcPost:1234567890"
    - URLs with hyphen notation: containing "activity-1234567890" or "ugcPost-1234567890"
    
    Args:
        post_url: The full LinkedIn post URL
        
    Returns:
        The extracted URN (e.g., "urn:li:activity:1234567890") or None if not found
        
    Examples:
        >>> parse_linkedin_post_url("https://www.linkedin.com/feed/update/urn:li:activity:123")
        'urn:li:activity:123'
        
        >>> parse_linkedin_post_url("https://www.linkedin.com/posts/activity-123456789")
        'urn:li:activity:123456789'
    """
    if not post_url or not isinstance(post_url, str):
        logger.warning(f"Invalid post_url provided: {post_url}")
        return None
    
    logger.info(f"Parsing LinkedIn URL: {post_url}")
    
    try:
        # Try to find URN directly in the path or query parameters
        urn_match = re.search(r'(urn:li:(?:activity|ugcPost):\d+)', post_url)
        if urn_match:
            urn = urn_match.group(1)
            logger.info(f"Parsed URN directly from URL: {urn}")
            return urn
        
        # Fallback: Look for activity or ugcPost colon patterns
        activity_match = re.search(r'(?:activity:|ugcPost:)(\d+)', post_url)
        if activity_match:
            post_id = activity_match.group(1)
            post_type = 'ugcPost' if 'ugcPost:' in post_url else 'activity'
            urn = f"urn:li:{post_type}:{post_id}"
            logger.info(f"Parsed URN using fallback colon pattern: {urn}")
            return urn
        
        # Fallback: Handle hyphen-based patterns (e.g., "activity-1234567890-")
        hyphen_activity = re.search(r'activity-(\d+)', post_url)
        if hyphen_activity:
            post_id = hyphen_activity.group(1)
            urn = f"urn:li:activity:{post_id}"
            logger.info(f"Parsed URN from hyphen pattern: {urn}")
            return urn
        
        hyphen_ugc = re.search(r'ugcPost-(\d+)', post_url)
        if hyphen_ugc:
            post_id = hyphen_ugc.group(1)
            urn = f"urn:li:ugcPost:{post_id}"
            logger.info(f"Parsed URN from hyphen pattern: {urn}")
            return urn
        
        logger.warning(f"Could not extract URN from URL: {post_url}")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing URL {post_url}: {str(e)}")
        return None

