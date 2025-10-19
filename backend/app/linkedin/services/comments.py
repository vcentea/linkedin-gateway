"""
LinkedIn Comments API service.

Mirrors functionality from chrome-extension/src-v2/content/linkedin/comments.js
Provides server-side implementation of comment operations.
"""
from typing import List, Dict, Any, Optional
from urllib.parse import quote
import logging
import asyncio
import random
import re

from .base import LinkedInServiceBase
from ..utils.parsers import parse_linkedin_post_url

logger = logging.getLogger(__name__)

class LinkedInCommentsService(LinkedInServiceBase):
    """Service for LinkedIn comment operations."""
    
    COMMENTS_QUERY_ID = 'voyagerSocialDashComments.95ed44bc87596acce7c460c70934d0ff'
    
    def _build_headers(self) -> dict:
        """
        Override base headers to add Content-Type for POST requests.
        
        Returns:
            dict: Headers optimized for comment operations
        """
        headers = super()._build_headers()
        # Add Content-Type for POST requests (posting/replying to comments)
        headers['content-type'] = 'application/json'
        return headers
    
    def _build_commenters_url(
        self,
        post_url: str,
        start: int = 0,
        count: int = 10,
        num_replies: int = 1,
        pagination_token: Optional[str] = None
    ) -> str:
        """
        Build the LinkedIn GraphQL URL for fetching commenters.
        
        Args:
            post_url: The full URL of the LinkedIn post
            start: The starting index for fetching comments
            count: The number of comments to fetch per request
            num_replies: The number of replies to fetch for each comment
            pagination_token: Optional pagination token from previous response
            
        Returns:
            Full LinkedIn GraphQL API URL
            
        Raises:
            ValueError: If post URN cannot be parsed
        """
        # Parse the Post URN from the full URL
        logger.info(f"[BUILD_URL] Received post_url: {post_url}")
        post_urn = parse_linkedin_post_url(post_url)
        if not post_urn:
            raise ValueError(f'Could not parse Post URN from URL: {post_url}')
        
        logger.info(f"[BUILD_URL] Parsed post URN: {post_urn}")
        
        # Build the GraphQL API URL - MUST match client exactly!
        encoded_post_urn = quote(post_urn, safe='')
        
        # Build variables string
        variables_parts = [
            f"count:{count}",
            f"numReplies:{num_replies}"
        ]
        
        # Add pagination token if present
        if pagination_token:
            variables_parts.append(f"paginationToken:{pagination_token}")
            logger.info(f"[BUILD_URL] Using pagination token: {pagination_token}")
        
        variables_parts.extend([
            f"socialDetailUrn:urn%3Ali%3Afsd_socialDetail%3A%28{encoded_post_urn}%2C{encoded_post_urn}%2Curn%3Ali%3AhighlightedReply%3A-%29",
            f"sortOrder:RELEVANCE",
            f"start:{start}"
        ])
        
        variables_str = ",".join(variables_parts)
        
        url = (
            f"{self.GRAPHQL_BASE_URL}?variables="
            f"({variables_str})"
            f"&queryId={self.COMMENTS_QUERY_ID}"
        )
        
        logger.info(f"[BUILD_URL] Constructed URL: {url}")
        return url
    
    def _parse_commenters_response(
        self, 
        data: Dict[str, Any], 
        include_replies: bool = True
    ) -> tuple[List[Dict[str, Any]], Optional[str], Optional[int], Optional[str]]:
        """
        Parse the LinkedIn API response to extract commenter details and pagination info.
        
        Args:
            data: Raw JSON response from LinkedIn API
            include_replies: If True, include reply comments; if False, only direct comments
            
        Returns:
            Tuple of (list of commenter detail objects, pagination token or None, total comments count or None, ugcPost URN or None)
        """
        logger.info(f"[PARSE_RESPONSE] Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        # Extract pagination info from response
        # Path: data.data.socialDashCommentsBySocialDetail.metadata.paginationToken
        # Path: data.data.socialDashCommentsBySocialDetail.paging.total (ONLY from first request)
        pagination_token = None
        total_comments = None
        ugc_post_urn = None  # Extract from first response
        
        if 'data' in data and isinstance(data['data'], dict):
            data_section = data['data']
            if 'data' in data_section and isinstance(data_section['data'], dict):
                social_dash_comments = data_section['data'].get('socialDashCommentsBySocialDetail', {})
                if isinstance(social_dash_comments, dict):
                    # Get pagination token and total count from metadata
                    metadata = social_dash_comments.get('metadata', {})
                    if isinstance(metadata, dict):
                        pagination_token = metadata.get('paginationToken')
                        if pagination_token:
                            logger.info(f"[PARSE_RESPONSE] Found pagination token: {pagination_token}")
                        
                        # Get total from updatedCommentCount (only in first request)
                        updated_comment_count = metadata.get('updatedCommentCount')
                        if updated_comment_count is not None and updated_comment_count > 0:
                            total_comments = updated_comment_count
                            logger.info(f"[PARSE_RESPONSE] ✓ Found total direct comments from metadata.updatedCommentCount: {total_comments}")
                        elif updated_comment_count == 0:
                            logger.info(f"[PARSE_RESPONSE] metadata.updatedCommentCount is 0 (no comments)")
                    
                    # Get paging info for diagnostics
                    paging = social_dash_comments.get('paging', {})
                    if isinstance(paging, dict):
                        count = paging.get('count', 0)
                        start = paging.get('start', 0)
                        paging_total = paging.get('total', 0)
                        logger.info(f"[PARSE_RESPONSE] Paging info - count: {count}, start: {start}, paging.total: {paging_total}")
                    
                    # Check elements array length for diagnostics
                    elements = social_dash_comments.get('elements', [])
                    if isinstance(elements, list):
                        logger.info(f"[PARSE_RESPONSE] elements array length: {len(elements)}")
        
        # Extract ugcPost URN from included data (first response only)
        included = data.get('included', [])
        if included and isinstance(included, list):
            for item in included:
                if isinstance(item, dict):
                    # Look for ugcPost URN in various fields
                    urn = item.get('urn', '')
                    entity_urn = item.get('entityUrn', '')
                    
                    # Check urn field
                    ugc_match = re.search(r'(urn:li:ugcPost:\d+)', urn) if urn else None
                    if ugc_match:
                        ugc_post_urn = ugc_match.group(1)
                        logger.info(f"[PARSE_RESPONSE] ✓ Found ugcPost URN in response: {ugc_post_urn}")
                        break
                    
                    # Check entityUrn field
                    entity_ugc_match = re.search(r'(urn:li:ugcPost:\d+)', entity_urn) if entity_urn else None
                    if entity_ugc_match:
                        ugc_post_urn = entity_ugc_match.group(1)
                        logger.info(f"[PARSE_RESPONSE] ✓ Found ugcPost URN in entityUrn: {ugc_post_urn}")
                        break
        
        # Process response
        if not included or len(included) == 0:
            logger.info(f'[PARSE_RESPONSE] No items in "included" array (empty batch or end of results)')
            return [], pagination_token, total_comments, ugc_post_urn
        
        logger.info(f"[PARSE_RESPONSE] Found 'included' with {len(included)} items")
        commenters = self._process_comment_batch(included, include_replies)
        logger.info(f"[PARSE_RESPONSE] Successfully extracted {len(commenters)} commenter details (include_replies={include_replies})")
        
        return commenters, pagination_token, total_comments, ugc_post_urn
    
    async def fetch_commenters_for_post(
        self,
        post_url: str,
        start: int = 0,
        count: int = 10,
        num_replies: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Fetch commenters for a given LinkedIn post URL using the GraphQL endpoint.
        
        Mirrors fetchCommentersForPost from comments.js
        Makes a direct API call to LinkedIn's GraphQL endpoint and extracts
        commenter details from the response.
        
        Args:
            post_url: The full URL of the LinkedIn post
            start: The starting index for fetching comments (default: 0)
            count: The number of comments to fetch per request (default: 10)
            num_replies: The number of replies to fetch for each comment (default: 1)
            
        Returns:
            List of commenter detail objects with structure:
            {
                'userId': str,
                'userName': str,
                'userTitle': str or None,
                'commentText': str
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
        
        if not isinstance(num_replies, int) or num_replies < 0:
            raise ValueError(f'Invalid num_replies: {num_replies}. Must be non-negative integer.')
        
        # Build URL
        url = self._build_commenters_url(post_url, start, count, num_replies)
        
        # Make the request
        data = await self._make_request(url)
        
        # Parse and return (ignore pagination token, total, and ugcPost URN for this simple method)
        # Include replies based on num_replies parameter
        include_replies = (num_replies > 0)
        commenters, _, _, _ = self._parse_commenters_response(data, include_replies)
        return commenters
    
    def _process_comment_batch(
        self, 
        included_data: List[Dict[str, Any]], 
        include_replies: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of response data to extract commenter details.
        
        Distinguishes between direct comments and replies based on permalink.
        - Direct Comment: permalink does NOT contain 'replyUrn' or 'dashReplyUrn'
        - Reply: permalink DOES contain 'replyUrn' or 'dashReplyUrn'
        
        Args:
            included_data: The 'included' array from the API response
            include_replies: If True, include reply comments; if False, only direct comments
            
        Returns:
            List of commenter detail objects
        """
        if not isinstance(included_data, list):
            logger.error('Invalid included_data: not a list')
            return []
        
        commenters = []
        direct_count = 0
        reply_count = 0
        
        # Filter for items that have commentary text
        comments_with_text = [
            item for item in included_data
            if isinstance(item, dict) and item.get('commentary', {}).get('text')
        ]
        
        logger.info(f"Found {len(comments_with_text)} items with commentary text (total: {len(included_data)})")
        
        for comment in comments_with_text:
            try:
                # Check if this is a reply by examining the permalink
                permalink = comment.get('permalink', '')
                is_reply = 'replyUrn' in permalink or 'dashReplyUrn' in permalink
                
                # Skip replies if include_replies is False
                if is_reply and not include_replies:
                    reply_count += 1
                    continue
                
                # Extract details using the paths from JS implementation
                comment_text = comment.get('commentary', {}).get('text', '')
                commenter = comment.get('commenter', {})
                
                user_name = commenter.get('title', {}).get('text') if isinstance(commenter.get('title'), dict) else commenter.get('title')
                user_id = commenter.get('commenterProfileId')
                user_title = commenter.get('subtitle')
                
                # Extract comment URN for replying
                # Use entityUrn (preferred) or fall back to urn
                comment_urn = comment.get('entityUrn') or comment.get('urn')
                
                # Ensure we have core details
                if user_id and user_name:
                    commenter_detail = {
                        'userId': user_id,
                        'userName': user_name,
                        'userTitle': user_title if user_title else None,
                        'commentText': comment_text,
                        'commentUrn': comment_urn,  # URN for replying to this comment
                        'isReply': is_reply  # Mark if this is a reply
                    }
                    commenters.append(commenter_detail)
                    
                    if is_reply:
                        reply_count += 1
                    else:
                        direct_count += 1
                else:
                    logger.warning(
                        f"Could not extract required details for comment URN: {comment.get('urn')}. "
                        f"UserID found: {bool(user_id)}, UserName found: {bool(user_name)}"
                    )
                    
            except Exception as e:
                logger.error(f"Error processing individual comment: {str(e)}")
                # Continue processing other comments
                continue
        
        logger.info(f"Extracted {len(commenters)} commenter details from batch (direct: {direct_count}, replies: {reply_count}, skipped replies: {reply_count if not include_replies else 0})")
        return commenters
    
    async def _get_ugc_post_urn_from_activity(self, activity_id: str) -> str:
        """
        Get the ugcPost URN from an activity ID using LinkedIn's GraphQL API.
        
        This is needed because commenting on activity posts requires the ugcPost URN.
        
        Args:
            activity_id: The activity ID (e.g., "7383418571017842688")
            
        Returns:
            The ugcPost URN (e.g., "urn:li:ugcPost:7383410713530101760")
            
        Raises:
            ValueError: If ugcPost URN cannot be found
            httpx.HTTPStatusError: If the API request fails
        """
        from urllib.parse import quote
        
        # Construct the updateActionsUrn
        update_actions_urn = f"urn:li:fsd_updateActions:(urn:li:activity:{activity_id},FEED_DETAIL,EMPTY,urn:li:reason:-,urn:li:adCreative:-)"
        encoded_urn = quote(update_actions_urn)
        
        # Build the GraphQL URL
        url = f"{self.VOYAGER_BASE_URL}/graphql?variables=(updateActionsUrn:{encoded_urn})&queryId=voyagerFeedDashUpdateActions.e826a55733c1fd7da926544b655f05c0"
        
        logger.info(f"[GET UGC POST URN] Fetching ugcPost URN for activity: {activity_id}")
        
        # Make the request
        data = await self._make_request(url)
        
        # Extract the ugcPost URN from the response
        post_urn = None
        for item in data.get("included", []):
            if "actions" in item:
                for action in item.get("actions", []):
                    target_urn = action.get("targetUrn", "")
                    if target_urn and target_urn.startswith("urn:li:ugcPost:"):
                        post_urn = target_urn
                        break
            if post_urn:
                break
        
        if not post_urn:
            raise ValueError(f"Could not find ugcPost URN for activity: {activity_id}")
        
        logger.info(f"[GET UGC POST URN] Found ugcPost URN: {post_urn}")
        return post_urn
    
    async def prepare_post_comment_request(
        self,
        post_url: str,
        comment_text: str
    ) -> tuple[str, Dict[str, Any]]:
        """
        Prepare the URL and payload for posting a comment.
        
        Args:
            post_url: The full URL of the LinkedIn post
            comment_text: The text content of the comment
            
        Returns:
            Tuple of (url, payload) ready for execution
            
        Raises:
            ValueError: If post URL cannot be parsed
        """
        logger.info(f"[PREPARE POST COMMENT] Processing post URL: {post_url}")
        
        # Parse the post URN from the URL
        post_urn = parse_linkedin_post_url(post_url)
        if not post_urn:
            raise ValueError(f'Could not parse Post URN from URL: {post_url}')
        
        logger.info(f"[PREPARE POST COMMENT] Parsed post URN: {post_urn}")
        
        # If it's an activity post, we need to get the ugcPost URN first
        if post_urn.startswith("urn:li:activity:"):
            activity_id = post_urn.split(":")[-1]
            logger.info(f"[PREPARE POST COMMENT] Activity post detected, fetching ugcPost URN...")
            try:
                post_urn = await self._get_ugc_post_urn_from_activity(activity_id)
                logger.info(f"[PREPARE POST COMMENT] Using ugcPost URN: {post_urn}")
            except Exception as e:
                logger.warning(f"[PREPARE POST COMMENT] Could not get ugcPost URN, will try with activity URN: {e}")
                # Continue with the original activity URN
        
        # Construct the request URL
        url = f"{self.VOYAGER_BASE_URL}/voyagerSocialDashNormComments?decorationId=com.linkedin.voyager.dash.deco.social.NormComment-43"
        
        # Construct the payload
        payload = {
            "commentary": {
                "text": comment_text,
                "attributesV2": [],
                "$type": "com.linkedin.voyager.dash.common.text.TextViewModel"
            },
            "threadUrn": post_urn
        }
        
        return url, payload
    
    async def prepare_reply_to_comment_request(
        self,
        comment_urn: str,
        reply_text: str
    ) -> tuple[str, Dict[str, Any]]:
        """
        Prepare the URL and payload for replying to a comment.
        
        Args:
            comment_urn: The URN of the comment to reply to
            reply_text: The text content of the reply
            
        Returns:
            Tuple of (url, payload) ready for execution
            
        Raises:
            ValueError: If comment URN is invalid
        """
        logger.info(f"[PREPARE REPLY] Processing comment URN: {comment_urn}")
        
        # Validate comment URN format
        if not comment_urn or not comment_urn.startswith('urn:li:'):
            raise ValueError(f'Invalid comment URN: {comment_urn}')
        
        # Extract the post ID and comment ID from the fsd_comment URN
        # Format can be: "urn:li:fsd_comment:(COMMENT_ID,urn:li:activity:ACTIVITY_ID)"
        #            or: "urn:li:fsd_comment:(COMMENT_ID,urn:li:ugcPost:UGC_POST_ID)"
        # We need to convert this to: "urn:li:comment:(activity:ACTIVITY_ID,COMMENT_ID)"
        #                         or: "urn:li:comment:(ugcPost:UGC_POST_ID,COMMENT_ID)"
        
        import re
        match = re.search(r'urn:li:fsd_comment:\((\d+),urn:li:(activity|ugcPost):(\d+)\)', comment_urn)
        if not match:
            raise ValueError(f'Could not parse comment URN: {comment_urn}')
        
        comment_id = match.group(1)
        post_type = match.group(2)  # 'activity' or 'ugcPost'
        post_id = match.group(3)
        
        # Construct the threadUrn for the reply
        thread_urn = f"urn:li:comment:({post_type}:{post_id},{comment_id})"
        
        logger.info(f"[PREPARE REPLY] Extracted comment_id: {comment_id}, post_type: {post_type}, post_id: {post_id}")
        logger.info(f"[PREPARE REPLY] Constructed threadUrn: {thread_urn}")
        
        # Construct the request URL
        url = f"{self.VOYAGER_BASE_URL}/voyagerSocialDashNormComments?decorationId=com.linkedin.voyager.dash.deco.social.NormComment-43"
        
        # Construct the payload
        payload = {
            "commentary": {
                "text": reply_text,
                "attributesV2": [],
                "$type": "com.linkedin.voyager.dash.common.text.TextViewModel"
            },
            "threadUrn": thread_urn
        }
        
        return url, payload

