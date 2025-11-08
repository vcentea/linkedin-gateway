"""
LinkedIn Reactions API service.

Provides server-side implementation of reaction operations.
Follows the same patterns as comments service.
"""
from typing import List, Dict, Any, Optional
from urllib.parse import quote
import logging
import re

from .base import LinkedInServiceBase
from ..utils.parsers import parse_linkedin_post_url

logger = logging.getLogger(__name__)

class LinkedInReactionsService(LinkedInServiceBase):
    """Service for LinkedIn reaction operations."""
    
    REACTIONS_QUERY_ID = 'voyagerSocialDashReactions.41ebf31a9f4c4a84e35a49d5abc9010b'
    
    def _build_headers(self) -> dict:
        """
        Override base headers for reaction requests.
        
        Returns:
            dict: Headers optimized for reaction operations
        """
        headers = super()._build_headers()
        return headers
    
    async def _build_reactions_url(
        self,
        post_url: str,
        start: int = 0,
        count: int = 10,
        pagination_token: Optional[str] = None
    ) -> str:
        """
        Build the LinkedIn GraphQL URL for fetching reactions.
        
        Args:
            post_url: The full URL of the LinkedIn post
            start: The starting index for fetching reactions
            count: The number of reactions to fetch per request
            pagination_token: Optional pagination token from previous response
            
        Returns:
            Full LinkedIn GraphQL API URL
            
        Raises:
            ValueError: If post URN cannot be parsed
        """
        logger.info(f"[BUILD_URL] Received post_url: {post_url}")
        post_urn = parse_linkedin_post_url(post_url)
        if not post_urn:
            raise ValueError(f'Could not parse Post URN from URL: {post_url}')
        
        logger.info(f"[BUILD_URL] Parsed post URN: {post_urn}")
        
        # If it's an activity post, convert to ugcPost URN (reactions require ugcPost)
        if post_urn.startswith("urn:li:activity:"):
            activity_id = post_urn.split(":")[-1]
            logger.info(f"[BUILD_URL] Activity post detected, fetching ugcPost URN...")
            try:
                post_urn = await self._get_ugc_post_urn_from_activity(activity_id)
                logger.info(f"[BUILD_URL] Converted to ugcPost URN: {post_urn}")
            except Exception as e:
                logger.warning(f"[BUILD_URL] Could not convert activity to ugcPost: {e}")
                # Continue with activity URN and let LinkedIn handle it
        
        logger.info(f"[BUILD_URL] Using post URN: {post_urn}")
        
        # URL encode the post URN (MUST match client exactly!)
        encoded_post_urn = quote(post_urn, safe='')
        
        # Build variables string - MUST match exact order from working example
        # Example: (count:10,start:0,threadUrn:urn%3Ali%3AugcPost%3A7388828638206533632)
        variables_parts = [
            f"count:{count}",
            f"start:{start}",
            f"threadUrn:{encoded_post_urn}"
        ]
        
        # Add pagination token if present
        if pagination_token:
            variables_parts.append(f"paginationToken:{pagination_token}")
            logger.info(f"[BUILD_URL] Using pagination token: {pagination_token}")
        
        variables_str = ",".join(variables_parts)
        
        url = (
            f"{self.GRAPHQL_BASE_URL}?includeWebMetadata=true&variables="
            f"({variables_str})"
            f"&queryId={self.REACTIONS_QUERY_ID}"
        )
        
        logger.info(f"[BUILD_URL] Constructed URL: {url}")
        logger.info(f"[BUILD_URL] Variables: {variables_str}")
        logger.info(f"[BUILD_URL] Encoded post URN: {encoded_post_urn}")
        return url
    
    def _parse_reactions_response(
        self, 
        data: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], Optional[str], Optional[int]]:
        """
        Parse the LinkedIn API response to extract reactor details and pagination info.
        
        Args:
            data: Raw JSON response from LinkedIn API
            
        Returns:
            Tuple of (list of reactor detail objects, pagination token or None, total reactions count or None)
        """
        logger.info(f"[PARSE_RESPONSE] Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        pagination_token = None
        total_reactions = None
        
        # Extract pagination info from response
        elements_urns = []
        if 'data' in data and isinstance(data['data'], dict):
            data_section = data['data']
            if 'data' in data_section and isinstance(data_section['data'], dict):
                social_dash_reactions = data_section['data'].get('socialDashReactionsByReactionType', {})
                if isinstance(social_dash_reactions, dict):
                    # Get pagination token
                    metadata = social_dash_reactions.get('metadata', {})
                    if isinstance(metadata, dict):
                        pagination_token = metadata.get('paginationToken')
                        if pagination_token:
                            logger.info(f"[PARSE_RESPONSE] Found pagination token: {pagination_token}")
                    
                    # Get paging info
                    paging = social_dash_reactions.get('paging', {})
                    if isinstance(paging, dict):
                        count = paging.get('count', 0)
                        start = paging.get('start', 0)
                        total_reactions = paging.get('total', 0)
                        logger.info(f"[PARSE_RESPONSE] Paging info - count: {count}, start: {start}, total: {total_reactions}")
                    
                    # IMPORTANT: The elements array contains URNs that reference items in the included array
                    elements = social_dash_reactions.get('elements', [])
                    if isinstance(elements, list):
                        elements_urns = elements
                        logger.info(f"[PARSE_RESPONSE] elements array length: {len(elements)}")
                        if elements:
                            logger.info(f"[PARSE_RESPONSE] Sample element URN: {elements[0] if elements else 'none'}")
        
        # Extract reactors from included data
        included = data.get('included', [])
        
        if not included or len(included) == 0:
            logger.info(f'[PARSE_RESPONSE] No items in "included" array (empty batch or end of results)')
            return [], pagination_token, total_reactions
        
        logger.info(f"[PARSE_RESPONSE] Found 'included' with {len(included)} items")
        reactors = self._process_reaction_batch(included)
        logger.info(f"[PARSE_RESPONSE] Successfully extracted {len(reactors)} reactor details")
        
        return reactors, pagination_token, total_reactions
    
    def _process_reaction_batch(
        self, 
        included_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of response data to extract reactor details.
        
        Args:
            included_data: The 'included' array from the API response
            
        Returns:
            List of reactor detail objects
        """
        if not isinstance(included_data, list):
            logger.error('Invalid included_data: not a list')
            return []
        
        reactors = []
        
        # Filter for Reaction items
        reaction_items = [
            item for item in included_data
            if isinstance(item, dict) and item.get('$type') == 'com.linkedin.voyager.dash.social.Reaction'
        ]
        
        logger.info(f"Found {len(reaction_items)} reaction items (total: {len(included_data)})")
        
        for reaction in reaction_items:
            try:
                # Extract reactor lockup data
                reactor_lockup = reaction.get('reactorLockup', {})
                
                # Extract user name from title
                user_name = None
                title = reactor_lockup.get('title', {})
                if isinstance(title, dict):
                    user_name = title.get('text')
                
                # Extract user title (headline) from subtitle
                user_title = None
                subtitle = reactor_lockup.get('subtitle', {})
                if isinstance(subtitle, dict):
                    user_title = subtitle.get('text')
                
                # Extract connection level from label
                connection_level = None
                label = reactor_lockup.get('label', {})
                if isinstance(label, dict):
                    connection_level = label.get('text')
                
                # Extract user ID from actor profileUrn
                user_id = None
                actor = reaction.get('actor', {})
                if isinstance(actor, dict):
                    profile_urn = actor.get('profileUrn', '')
                    if profile_urn:
                        # Extract profile ID from URN (e.g., "urn:li:fsd_profile:ACoAAD7-6OkBzHtPyDUD0wH2GSITJntEoxFm8K0")
                        match = re.search(r'urn:li:fsd_profile:(.+)', profile_urn)
                        if match:
                            user_id = match.group(1)
                
                # If user_id not found in actor, try actorUrn
                if not user_id:
                    actor_urn = reaction.get('actorUrn', '')
                    if actor_urn:
                        match = re.search(r'urn:li:fsd_profile:(.+)', actor_urn)
                        if match:
                            user_id = match.group(1)
                
                # Extract reaction type
                reaction_type = reaction.get('reactionType', 'LIKE')
                
                # Ensure we have core details
                if user_id and user_name:
                    reactor_detail = {
                        'userId': user_id,
                        'userName': user_name,
                        'userTitle': user_title if user_title else None,
                        'connectionLevel': connection_level if connection_level else None,
                        'reactionType': reaction_type
                    }
                    
                    reactors.append(reactor_detail)
                else:
                    logger.warning(
                        f"Could not extract required details for reaction. "
                        f"UserID found: {bool(user_id)}, UserName found: {bool(user_name)}"
                    )
                    
            except Exception as e:
                logger.error(f"Error processing individual reaction: {str(e)}")
                continue
        
        logger.info(f"Extracted {len(reactors)} reactor details from batch")
        return reactors
    
    async def fetch_reactions_for_post(
        self,
        post_url: str,
        start: int = 0,
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch reactions for a given LinkedIn post URL using the GraphQL endpoint.
        
        Args:
            post_url: The full URL of the LinkedIn post
            start: The starting index for fetching reactions (default: 0)
            count: The number of reactions to fetch per request (default: 10)
            
        Returns:
            List of reactor detail objects with structure:
            {
                'userId': str,
                'userName': str,
                'userTitle': str or None,
                'connectionLevel': str or None,
                'reactionType': str
            }
            
        Raises:
            ValueError: If parameters are invalid or post URN cannot be parsed
            httpx.HTTPStatusError: If the API request fails
        """
        # Input validation
        if not post_url or not isinstance(post_url, str):
            raise ValueError('Post URL is required and must be a string')
        
        if not isinstance(start, int) or start < 0:
            raise ValueError(f'Invalid start index: {start}. Must be non-negative integer.')
        
        if not isinstance(count, int) or count <= 0:
            raise ValueError(f'Invalid count: {count}. Must be positive integer.')
        
        # Build URL
        url = self._build_reactions_url(post_url, start, count)
        
        # Make the request
        data = await self._make_request(url)
        
        # Parse and return
        reactors, _, _ = self._parse_reactions_response(data)
        return reactors

