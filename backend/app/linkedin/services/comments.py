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
    
    @staticmethod
    def _extract_comment_id_from_urn(urn: str) -> Optional[str]:
        """
        Extract comment ID from various URN formats.
        
        Supports:
        - urn:li:fsd_comment:(COMMENT_ID,urn:li:ugcPost:POST_ID)
        - urn:li:fsd_comment:(COMMENT_ID,urn:li:activity:ACTIVITY_ID)
        - urn:li:comment:(ugcPost:POST_ID,COMMENT_ID)
        - urn:li:comment:(activity:ACTIVITY_ID,COMMENT_ID)
        
        Args:
            urn: The URN string to parse
            
        Returns:
            Comment ID as string, or None if parsing fails
        """
        if not urn:
            return None
        
        # Try fsd_comment format: urn:li:fsd_comment:(COMMENT_ID,...)
        match = re.search(r'urn:li:fsd_comment:\((\d+),', urn)
        if match:
            return match.group(1)
        
        # Try comment format: urn:li:comment:(...,COMMENT_ID)
        match = re.search(r'urn:li:comment:\([^,]+,(\d+)\)', urn)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_parent_from_permalink(self, permalink: str) -> Optional[str]:
        """
        Extract parent comment ID from permalink URL query parameters.
        
        Permalinks for replies contain both commentUrn (parent) and replyUrn (child).
        Example: ?commentUrn=urn%3Ali%3Acomment%3A%28ugcPost%3A...%2C7387421530831568896%29&replyUrn=...
        
        Args:
            permalink: The permalink URL string
            
        Returns:
            Parent comment ID if this is a reply, None otherwise
        """
        if not permalink:
            return None
        
        # Look for both replyUrn and commentUrn in the URL
        # If replyUrn exists, then commentUrn points to the parent
        if 'replyUrn' in permalink or 'dashReplyUrn' in permalink:
            # Extract the commentUrn parameter value
            # Pattern: commentUrn=urn%3Ali%3Acomment%3A%28ugcPost%3A<POST_ID>%2C<PARENT_ID>%29
            import urllib.parse
            
            # Try to parse query parameters
            try:
                # Extract query string
                if '?' in permalink:
                    query_string = permalink.split('?', 1)[1]
                    params = urllib.parse.parse_qs(query_string)
                    
                    # Get commentUrn parameter
                    comment_urn_encoded = params.get('commentUrn', [None])[0]
                    if comment_urn_encoded:
                        # Decode and extract ID
                        comment_urn = urllib.parse.unquote(comment_urn_encoded)
                        parent_id = self._extract_comment_id_from_urn(comment_urn)
                        return parent_id
            except Exception as e:
                logger.warning(f"[EXTRACT_PARENT] Failed to parse permalink: {e}")
        
        return None
    
    def _build_comment_relationships(
        self, 
        comments: List[Dict[str, Any]], 
        social_details: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build parent/child relationships from SocialDetail objects AND permalink analysis.
        
        Uses two signals:
        1. SocialDetail.threadUrn (parent) and SocialDetail.comments.elements (children)
        2. Comment permalink URL parameters (commentUrn=parent, replyUrn=child)
        
        Args:
            comments: List of comment objects (already processed)
            social_details: List of SocialDetail objects from the response
            
        Returns:
            Dictionary mapping comment_id -> {'parent': parent_id, 'children': [child_ids]}
        """
        relationships = {}
        
        logger.info(f"[BUILD_RELATIONSHIPS] Processing {len(comments)} comments and {len(social_details)} SocialDetail objects")
        
        # STEP 1: Extract parent/child from permalink URLs (secondary signal)
        for comment in comments:
            comment_urn = comment.get('commentUrn')
            permalink = comment.get('permalink', '')
            
            if not comment_urn:
                continue
                
            comment_id = self._extract_comment_id_from_urn(comment_urn)
            if not comment_id:
                continue
            
            # Initialize entry
            if comment_id not in relationships:
                relationships[comment_id] = {'parent': None, 'children': []}
            
            # Check if this is a reply by parsing permalink
            parent_id = self._extract_parent_from_permalink(permalink)
            if parent_id:
                relationships[comment_id]['parent'] = parent_id
                logger.debug(f"[BUILD_RELATIONSHIPS] From permalink: {comment_id} -> parent: {parent_id}")
                
                # Also add to parent's children list
                if parent_id not in relationships:
                    relationships[parent_id] = {'parent': None, 'children': []}
                if comment_id not in relationships[parent_id]['children']:
                    relationships[parent_id]['children'].append(comment_id)
        
        # STEP 2: Process SocialDetail objects (canonical signal - overrides permalink if different)
        for social_detail in social_details:
            if not isinstance(social_detail, dict):
                continue
            
            # Extract parent comment ID from threadUrn
            thread_urn = social_detail.get('threadUrn', '')
            parent_id = self._extract_comment_id_from_urn(thread_urn)
            
            if not parent_id:
                continue
            
            # Initialize relationship entry for parent if not exists
            if parent_id not in relationships:
                relationships[parent_id] = {'parent': None, 'children': []}
            
            # Extract child comment IDs from comments.elements
            comments_data = social_detail.get('comments', {})
            if isinstance(comments_data, dict):
                elements = comments_data.get('elements', [])
                if isinstance(elements, list):
                    for child_urn in elements:
                        if isinstance(child_urn, str):
                            child_id = self._extract_comment_id_from_urn(child_urn)
                            if child_id:
                                logger.debug(f"[BUILD_RELATIONSHIPS] From SocialDetail: {child_id} -> parent: {parent_id}")
                                
                                # Add to parent's children list (avoid duplicates)
                                if child_id not in relationships[parent_id]['children']:
                                    relationships[parent_id]['children'].append(child_id)
                                
                                # Set child's parent (SocialDetail is canonical, so override)
                                if child_id not in relationships:
                                    relationships[child_id] = {'parent': None, 'children': []}
                                relationships[child_id]['parent'] = parent_id
        
        logger.info(f"[BUILD_RELATIONSHIPS] Built relationships for {len(relationships)} comments")
        
        # Log summary
        parents_with_children = sum(1 for r in relationships.values() if r['children'])
        children_with_parents = sum(1 for r in relationships.values() if r['parent'])
        logger.info(f"[BUILD_RELATIONSHIPS] Summary: {parents_with_children} parents with children, {children_with_parents} children with parents")
        
        return relationships
    
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
    ) -> tuple[List[Dict[str, Any]], Optional[str], Optional[int], Optional[str], List[Dict[str, Any]]]:
        """
        Parse the LinkedIn API response to extract commenter details and pagination info.
        
        Args:
            data: Raw JSON response from LinkedIn API
            include_replies: If True, include reply comments; if False, only direct comments
            
        Returns:
            Tuple of (list of commenter detail objects, pagination token or None, total comments count or None, ugcPost URN or None, list of SocialDetail objects)
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
        
        # Extract ugcPost URN and SocialDetail objects from included data
        included = data.get('included', [])
        social_details = []
        
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
                    
                    # Check entityUrn field
                    entity_ugc_match = re.search(r'(urn:li:ugcPost:\d+)', entity_urn) if entity_urn else None
                    if entity_ugc_match and not ugc_post_urn:
                        ugc_post_urn = entity_ugc_match.group(1)
                        logger.info(f"[PARSE_RESPONSE] ✓ Found ugcPost URN in entityUrn: {ugc_post_urn}")
                    
                    # Collect SocialDetail objects for relationship building
                    item_type = item.get('$type', '')
                    if item_type == 'com.linkedin.voyager.dash.social.SocialDetail':
                        social_details.append(item)
        
        logger.info(f"[PARSE_RESPONSE] Extracted {len(social_details)} SocialDetail objects for relationship building")
        
        # Process response
        if not included or len(included) == 0:
            logger.info(f'[PARSE_RESPONSE] No items in "included" array (empty batch or end of results)')
            return [], pagination_token, total_comments, ugc_post_urn, social_details
        
        logger.info(f"[PARSE_RESPONSE] Found 'included' with {len(included)} items")
        commenters = self._process_comment_batch(included, include_replies)
        logger.info(f"[PARSE_RESPONSE] Successfully extracted {len(commenters)} commenter details (include_replies={include_replies})")
        
        return commenters, pagination_token, total_comments, ugc_post_urn, social_details
    
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
                'connectionLevel': str or None,
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
        
        # Parse and return (ignore pagination token, total, ugcPost URN, and social details for this simple method)
        # Include replies based on num_replies parameter
        include_replies = (num_replies > 0)
        commenters, _, _, _, _ = self._parse_commenters_response(data, include_replies)
        return commenters
    
    def _process_comment_batch(
        self, 
        included_data: List[Dict[str, Any]], 
        include_replies: bool = True,
        relationships: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of response data to extract commenter details.
        
        Distinguishes between direct comments and replies based on permalink.
        - Direct Comment: permalink does NOT contain 'replyUrn' or 'dashReplyUrn'
        - Reply: permalink DOES contain 'replyUrn' or 'dashReplyUrn'
        
        Args:
            included_data: The 'included' array from the API response
            include_replies: If True, include reply comments; if False, only direct comments
            relationships: Optional dict mapping comment_id -> {'parent': parent_id, 'children': [child_ids]}
            
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
                
                # Extract connection level from supplementaryActorInfo
                supplementary_info = commenter.get('supplementaryActorInfo', {})
                connection_level = None
                if isinstance(supplementary_info, dict):
                    connection_text = supplementary_info.get('text', '')
                    if connection_text:
                        # Clean up the connection level text (e.g., " • 3rd+" -> "3rd+")
                        connection_level = connection_text.strip().lstrip('•').strip()
                
                # Extract comment URN for replying
                # Use entityUrn (preferred) or fall back to urn
                comment_urn = comment.get('entityUrn') or comment.get('urn')
                
                # Ensure we have core details
                if user_id and user_name:
                    # Extract comment ID for relationship lookup
                    comment_id = self._extract_comment_id_from_urn(comment_urn) if comment_urn else None
                    
                    # Build base commenter detail
                    commenter_detail = {
                        'userId': user_id,
                        'userName': user_name,
                        'userTitle': user_title if user_title else None,
                        'connectionLevel': connection_level,
                        'commentText': comment_text,
                        'commentUrn': comment_urn,  # URN for replying to this comment
                        'isReply': is_reply,  # Mark if this is a reply
                        'permalink': permalink  # Store permalink for relationship extraction
                    }
                    
                    # Add relationship data if available
                    if relationships and comment_id and comment_id in relationships:
                        rel_data = relationships[comment_id]
                        commenter_detail['parentCommentId'] = rel_data.get('parent')
                        children = rel_data.get('children', [])
                        commenter_detail['childCommentIds'] = children if children else None
                    else:
                        commenter_detail['parentCommentId'] = None
                        commenter_detail['childCommentIds'] = None
                    
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

