"""
LinkedIn Feed API service.

Mirrors functionality from chrome-extension/src-v2/content/linkedin/feed.js
Provides server-side implementation of feed operations.
"""
from typing import List, Dict, Any, Optional
from .base import LinkedInServiceBase
from ..utils.parsers import parse_linkedin_post_url
import logging
import re

logger = logging.getLogger(__name__)

class LinkedInFeedService(LinkedInServiceBase):
    """Service for LinkedIn feed operations."""
    
    def _build_feed_url(self, start_index: int, count: int) -> str:
        """
        Build the LinkedIn feed API URL.
        
        Args:
            start_index: The starting index for fetching posts.
            count: The number of posts to fetch.
            
        Returns:
            str: The complete feed API URL.
        """
        # Request one more than needed (mirroring JS implementation)
        requested_count = count + 1
        url = (
            f"{self.VOYAGER_BASE_URL}/feed/updatesV2"
            f"?count={requested_count}&start={start_index}"
            f"&q=feed&includeLongTermHistory=true&useCase=DEFAULT"
        )
        return url
    
    def _parse_feed_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse the LinkedIn feed API response to extract post data.
        
        Handles the new fs_updateV2 format with:
        - Post URLs (from socialContent.shareUrl)
        - Accurate likes/comments counts (from SocialActivityCounts)
        
        Args:
            data: The raw API response JSON.
            
        Returns:
            List of formatted post objects.
        """
        # Process response
        if not data.get('included') or not isinstance(data['included'], list):
            logger.warning('LinkedIn API response does not contain expected "included" array.')
            return []
        
        # Step 1: Create comprehensive lookup maps
        update_map = {}
        social_detail_map = {}
        social_counts_map = {}
        
#        logger.info(f"Processing {len(data['included'])} items from included array")
        
        for item in data['included']:
            item_type = item.get('$type', '')
            entity_urn = item.get('entityUrn', '')
            
            if not entity_urn:
                continue
            
            # New structure uses different type names
            if item_type == 'com.linkedin.voyager.feed.render.UpdateV2':
                update_map[entity_urn] = item
            elif item_type == 'com.linkedin.voyager.feed.SocialDetail':
                social_detail_map[entity_urn] = item
            elif item_type == 'com.linkedin.voyager.feed.shared.SocialActivityCounts':
                social_counts_map[entity_urn] = item
        
        logger.info(f"Created maps - Updates: {len(update_map)}, SocialDetails: {len(social_detail_map)}, SocialCounts: {len(social_counts_map)}")
        
        # Step 2: Get the list of post URNs from the main feed
        post_urn_list = data.get('data', {}).get('*elements', [])
        
        posts_array = []
        
        logger.info(f"Found {len(post_urn_list)} elements in feed response")
        
        # Step 3: Consolidate data for each post
        for post_urn in post_urn_list:
            # Use regex for robust ID extraction from complex URNs
            # Format: urn:li:fs_updateV2:(urn:li:activity:ID,MAIN_FEED,...)
            id_match = re.search(r'activity:(\d+)', post_urn)
            if not id_match:
                # Skip elements that are not standard posts (e.g., promotions, sponsored content)
                logger.debug(f"Skipping non-post element: {post_urn[:80]}...")
                continue
            
            post_id = id_match.group(1)
            
            # Look up the post object
            post_object = update_map.get(post_urn)
            if not post_object:
                logger.debug(f"No UpdateV2 object found for URN: {post_urn[:80]}...")
                continue
            
            try:
                # Extract post details using existing method
                post_data = self._extract_post_details(post_object)
                if not post_data or not post_data.get('postId'):
                    logger.debug(f"Could not extract post details for activity:{post_id}")
                    continue
                
                # Get the full URL from socialContent.shareUrl (most reliable)
                full_url = post_object.get('socialContent', {}).get('shareUrl', '')
                if not full_url:
                    # Fallback to constructed URL
                    full_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}"
                
                # Get likes and comment counts from SocialActivityCounts
                likes = 0
                comment_count = 0
                
                # Link from post object -> social detail -> social counts
                social_detail_urn = post_object.get('*socialDetail')
                if social_detail_urn:
                    social_detail = social_detail_map.get(social_detail_urn)
                    
                    if social_detail:
                        # Get likes and comment counts
                        social_counts_urn = social_detail.get('*totalSocialActivityCounts')
                        if social_counts_urn:
                            social_counts = social_counts_map.get(social_counts_urn)
                            
                            if social_counts:
                                likes = social_counts.get('numLikes', 0)
                                comment_count = social_counts.get('numComments', 0)
                
                posts_array.append({
                    'postId': post_data['postId'],  # This is "activity:123" or "ugcPost:123"
                    'ugcPostId': post_data.get('ugcPostId', ''),  # Separate ugcPost ID if available
                    'postUrl': full_url,  # Full URL from socialContent.shareUrl
                    'authorName': post_data['authorName'],
                    'authorProfileId': post_data['profileID'],
                    'authorJobTitle': post_data['job_title'],
                    'authorConnectionDegree': post_data['conn_degree'],
                    'postContent': post_data['postContent'],
                    'likes': likes,  # From SocialActivityCounts
                    'comments': comment_count,  # From SocialActivityCounts
                    'timestamp': post_data.get('timestamp')
                })
                
            except Exception as e:
                logger.error(f"Error extracting post details for activity:{post_id}: {str(e)}")
                # Continue processing other posts
                continue
        
        logger.info(f"Successfully extracted {len(posts_array)} posts")
        return posts_array
    
    async def fetch_posts_from_feed(
        self, 
        start_index: int, 
        count: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch posts from LinkedIn feed.
        
        Mirrors fetchPostsFromFeed from feed.js
        Makes a direct API call to LinkedIn's voyager API and processes
        the response to extract post data, author information, and engagement metrics.
        
        Args:
            start_index: The starting index for fetching posts
            count: The number of posts to fetch
            
        Returns:
            List of formatted post objects with structure:
            {
                'postId': str,
                'postUrl': str,
                'authorName': str,
                'authorProfileId': str,
                'authorJobTitle': str,
                'authorConnectionDegree': str,
                'postContent': str,
                'likes': int,
                'comments': int,
                'timestamp': str (ISO format)
            }
            
        Raises:
            ValueError: If parameters are invalid
            httpx.HTTPStatusError: If the API request fails
        """
        # Input validation
        if not isinstance(start_index, int) or start_index < 0:
            raise ValueError(f"Invalid start_index: {start_index}. Must be non-negative integer.")
        
        if not isinstance(count, int) or count <= 0:
            raise ValueError(f"Invalid count: {count}. Must be positive integer.")
        
        logger.info(f"Fetching {count} posts starting from index {start_index}")
        
        # Build URL
        url = self._build_feed_url(start_index, count)
        
        # Make the request
        data = await self._make_request(url)
        
        # Parse and return results
        return self._parse_feed_response(data)
    
    def _extract_post_details(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract essential details from a single LinkedIn feed item.
        
        Mirrors extractSinglePostDetails from postSearch.js (lines 448-517)
        
        Args:
            item: A single item from the LinkedIn API response
            
        Returns:
            Dictionary with extracted post details or None if not valid
        """
        # Basic check for valid post structure
        if not item.get('actor') or not item.get('commentary', {}).get('text', {}).get('text'):
            return None
        
        actor = item.get('actor', {})
        commentary = item.get('commentary', {})
        update_metadata = item.get('updateMetadata', {})
        
        extracted_data = {
            'postId': '',
            'ugcPostId': '',
            'authorName': actor.get('name', {}).get('text', ''),
            'profileID': '',
            'postContent': commentary.get('text', {}).get('text', ''),
            'conn_degree': '',
            'job_title': actor.get('description', {}).get('text', ''),
            'timestamp': update_metadata.get('timestamp')
        }
        
        # Extract UGC Post ID from *socialDetail (CRITICAL - matches old app lines 459-468)
        # This is SEPARATE from the postId used for URLs
        social_detail = item.get('*socialDetail', '')
        if social_detail:
            # Try to extract ugcPost ID
            ugc_match = re.search(r'urn:li:ugcPost:(\d+)', social_detail)
            if ugc_match:
                extracted_data['ugcPostId'] = ugc_match.group(1)
                logger.debug(f"Extracted ugcPost ID from *socialDetail: {extracted_data['ugcPostId']}")
        
        # Get the full URN from updateMetadata for URL construction (matches old app line 384)
        # This is ALWAYS used for the post URL, regardless of ugcPost vs activity
        urn = update_metadata.get('urn', '')
        if urn:
            # Extract the last 2 parts and take only the first part before any comma
            # Example: "urn:li:activity:7384096805824937984,..." -> "activity:7384096805824937984"
            urn_parts = urn.split(':')
            if len(urn_parts) >= 2:
                post_id_part = ':'.join(urn_parts[-2:]).split(',')[0]
                extracted_data['postId'] = post_id_part
                logger.debug(f"Extracted post ID from updateMetadata.urn: {post_id_part}")
        
        # Extract Profile ID
        name_attrs = actor.get('name', {}).get('attributes', [])
        profile_attr = next((attr for attr in name_attrs if attr.get('*miniProfile')), None)
        
        if profile_attr and profile_attr.get('*miniProfile'):
            urn_parts = profile_attr['*miniProfile'].split(':')
            extracted_data['profileID'] = urn_parts[-1]
        elif actor.get('urn') and ':member:' in actor['urn']:
            # Fallback to actor URN
            urn_parts = actor['urn'].split(':')
            extracted_data['profileID'] = urn_parts[-1]
        
        # Extract Connection Degree
        supplementary_info = actor.get('supplementaryActorInfo')
        if supplementary_info:
            extracted_data['conn_degree'] = (
                supplementary_info.get('text') or 
                supplementary_info.get('accessibilityText') or 
                ''
            )
        
        # Ensure essential fields are present
        if not all([extracted_data['postId'], extracted_data['authorName'], extracted_data['profileID']]):
            return None
        
        return extracted_data

