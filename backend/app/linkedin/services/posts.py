"""
LinkedIn Posts API service.

Mirrors functionality from chrome-extension/src-v2/content/linkedin/posts.js
Provides server-side implementation of post extraction operations.
"""
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from .base import LinkedInServiceBase
from ..utils.profile_id_extractor import extract_profile_id
import logging
import re
import httpx
import asyncio
import random

logger = logging.getLogger(__name__)

class LinkedInPostsService(LinkedInServiceBase):
    """Service for LinkedIn post extraction operations."""
    
    POSTS_QUERY_ID = 'voyagerFeedDashProfileUpdates.418845c51162bcbbda12be537ccc7976'
    
    def _build_profile_posts_url(
        self,
        profile_id: str,
        start: int,
        count: int,
        pagination_token: Optional[str] = None
    ) -> str:
        """
        Build the LinkedIn GraphQL API URL for fetching profile posts.
        
        Args:
            profile_id: The LinkedIn profile ID
            start: Starting index for pagination
            count: Number of posts to fetch
            pagination_token: Optional pagination token from previous response
            
        Returns:
            Full LinkedIn GraphQL API URL
        """
        profile_urn = f"urn:li:fsd_profile:{profile_id}"
        encoded_profile_urn = quote(profile_urn, safe='')
        
        # Build variables with pagination token if available
        variables = f"(count:{count},start:{start},profileUrn:{encoded_profile_urn}"
        
        if pagination_token:
            # URL encode the pagination token
            encoded_token = quote(pagination_token, safe='')
            variables += f",paginationToken:{encoded_token}"
        
        variables += ")"
        
        url = (
            f"{self.GRAPHQL_BASE_URL}?variables={variables}"
            f"&queryId={self.POSTS_QUERY_ID}"
        )
        
        return url
    
    def _parse_profile_posts_response(
        self,
        data: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], Optional[str], bool, Optional[int]]:
        """
        Parse the LinkedIn API response for profile posts.
        
        Args:
            data: Raw JSON response from LinkedIn API
            
        Returns:
            Tuple of (posts list, pagination token, has_more, next_start)
        """
        # Process posts
        if not data.get('included') or not isinstance(data['included'], list):
            return [], None, False, None
        
        posts_batch = self._process_posts_batch(data['included'])
        
        # Extract pagination info from response
        metadata = data.get('data', {}).get('data', {}).get('feedDashProfileUpdatesByMemberShareFeed', {}).get('metadata', {})
        paging = data.get('data', {}).get('data', {}).get('feedDashProfileUpdatesByMemberShareFeed', {}).get('paging', {})
        
        # Get pagination token
        pagination_token = metadata.get('paginationToken') if metadata else None
        
        # Get next start value
        next_start = paging.get('start') if paging else None
        
        # Determine if more pages available
        has_more = (next_start is not None)
        
        return posts_batch, pagination_token, has_more, next_start
    
    async def fetch_posts_for_profile(
        self,
        profile_id_or_url: str,
        desired_count: int = 10
    ) -> Dict[str, Any]:
        """
        Fetch posts from a LinkedIn profile using GraphQL API with automatic pagination.
        
        Replicates the logic from the old project's collectProfilePosts function:
        - Uses fixed page size of 20
        - Automatically paginates using pagination tokens
        - Collects posts until desired count is reached
        
        Args:
            profile_id_or_url: The LinkedIn profile ID (e.g., 'ACoAAAKGenkB35cm2-J9PCRudJry_IOtwWCS40k') 
                              or profile URL (e.g., 'https://www.linkedin.com/in/username/')
            desired_count: The total number of posts to retrieve (default: 10)
            
        Returns:
            Dictionary containing:
            {
                'posts': List of post objects,
                'hasMore': bool,
                'paginationToken': str or None
            }
            
        Raises:
            ValueError: If parameters are invalid
            httpx.HTTPStatusError: If the API request fails
        """
        # Extract profile ID from URL if needed using shared utility
        profile_id = await extract_profile_id(
            profile_input=profile_id_or_url,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        
        # Input validation
        if not profile_id or not isinstance(profile_id, str):
            raise ValueError('Profile ID is required and must be a string')
        
        if not isinstance(desired_count, int) or desired_count <= 0:
            raise ValueError(f'Invalid count: {desired_count}. Must be positive integer.')
        
        # Fixed page size of 20 (like old project)
        page_size = 20
        max_pages = (desired_count + page_size - 1) // page_size  # Calculate required pages
        
        logger.info(f"Fetching {desired_count} posts for profile ID: {profile_id}")
        logger.info(f"Using fixed page size: {page_size}, max pages: {max_pages}")
        
        all_posts = []
        start = 0
        pagination_token = ""
        has_more = True
        session_page_count = 0
        empty_responses = 0
        
        while has_more and session_page_count < max_pages and len(all_posts) < desired_count:
            logger.info(f"Page {session_page_count + 1} API request:")
            logger.info(f"Pagination params: start={start}, count={page_size}{', using token' if pagination_token else ''}")
            
            # Build URL using helper method
            url = self._build_profile_posts_url(profile_id, start, page_size, pagination_token)
            
            # Make the request
            try:
                data = await self._make_request(url)
                logger.info(f"Received response for page {session_page_count + 1}")
                
                # Parse response using helper method
                posts_batch, new_pagination_token, has_more_pages, next_start = self._parse_profile_posts_response(data)
                
                logger.info(f"Processed {len(posts_batch)} posts from page {session_page_count + 1}")
                
                if len(posts_batch) == 0:
                    empty_responses += 1
                    if empty_responses >= 3:
                        logger.info(f"Stopping after {empty_responses} consecutive empty responses")
                        has_more = False
                        break
                    # Increment start and try next page
                    start += page_size
                    session_page_count += 1
                    continue
                else:
                    empty_responses = 0
                    all_posts.extend(posts_batch)
                
                # Update pagination token
                if new_pagination_token:
                    pagination_token = new_pagination_token
                    logger.info(f"Updated pagination token for next request")
                
                # Update start value for next page
                if next_start is not None:
                    old_start = start
                    start = next_start
                    
                    if start == old_start:
                        logger.warning(f"LinkedIn returned same start value ({start}). Forcing increment.")
                        start += page_size
                    
                    logger.info(f"Next page will use start={start}")
                else:
                    start += page_size
                    logger.info(f"No start value provided, incrementing to {start}")
                
                # Update has_more flag
                has_more = has_more_pages
                
                # Stop if we've collected enough posts
                if len(all_posts) >= desired_count:
                    logger.info(f"Stopping pagination: collected {len(all_posts)} posts (requested: {desired_count})")
                    has_more = False
                    break
                
                session_page_count += 1
                
                # Add random delay between pages to avoid rate limits (1-5 seconds)
                if has_more and session_page_count < max_pages:
                    delay = random.uniform(1, 5)
                    logger.info(f"Waiting {delay:.2f} seconds before next page to avoid rate limits...")
                    await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"Failed to fetch posts on page {session_page_count + 1}: {str(e)}")
                raise
        
        # Limit to desired count
        all_posts = all_posts[:desired_count]
        
        logger.info(f"Collection complete: {len(all_posts)} posts, {session_page_count} pages processed")
        
        return {
            'posts': all_posts,
            'hasMore': has_more,
            'paginationToken': pagination_token
        }
    
    def _process_posts_batch(self, included_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a batch of response data to extract post details.
        
        Mirrors processPostsBatch from posts.js
        
        Args:
            included_data: The 'included' array from the API response
            
        Returns:
            List of post detail objects
        """
        if not isinstance(included_data, list):
            logger.error('Invalid included_data: not a list')
            return []
        
        posts = []
        
        # Create maps for quick lookup
        social_detail_map = {}
        actor_map = {}
        content_map = {}
        social_activity_counts_map = {}
        
        # First pass: Build lookup maps
        for item in included_data:
            if not isinstance(item, dict):
                continue
                
            entity_urn = item.get('entityUrn', '')
            
            # Map social details (for metrics)
            if entity_urn and 'socialDetail' in entity_urn:
                social_detail_map[entity_urn] = item
                
            # Map actors (for author info)
            if entity_urn and 'actor' in entity_urn:
                actor_map[entity_urn] = item
                
            # Map content
            if 'content' in item:
                content_map[entity_urn] = item
                
            # Map social activity counts (likes/comments) - COMPREHENSIVE like old project
            item_type = item.get('$type', '')
            if 'SocialActivityCounts' in item_type or 'socialActivityCounts' in item_type:
                urn = item.get('urn') or entity_urn
                entity_urn_to_check = entity_urn or item.get('urn', '')
                
                # Extract activity ID
                urn_match = re.search(r'activity:(\d+)', urn) if urn else None
                entity_urn_match = re.search(r'activity:(\d+)', entity_urn_to_check) if entity_urn_to_check else None
                
                # Extract activity ID (PRIMARY for profile posts)
                if urn_match:
                    social_activity_counts_map[urn_match.group(1)] = item
                    logger.info(f"Mapped social activity counts for post ID {urn_match.group(1)}")
                elif entity_urn_match:
                    social_activity_counts_map[entity_urn_match.group(1)] = item
                    logger.info(f"Mapped social activity counts for post ID {entity_urn_match.group(1)} from entityUrn")
                
                # Extract ugcPost ID
                ugc_post_match = re.search(r'ugcPost:(\d+)', urn) if urn else None
                entity_ugc_post_match = re.search(r'ugcPost:(\d+)', entity_urn_to_check) if entity_urn_to_check else None
                
                if ugc_post_match:
                    social_activity_counts_map[ugc_post_match.group(1)] = item
                    logger.info(f"Mapped social activity counts for ugcPost ID {ugc_post_match.group(1)}")
                elif entity_ugc_post_match:
                    social_activity_counts_map[entity_ugc_post_match.group(1)] = item
                    logger.info(f"Mapped social activity counts for ugcPost ID {entity_ugc_post_match.group(1)} from entityUrn")
                
                # Extract article ID
                article_match = re.search(r'article:(\d+)', urn) if urn else None
                entity_article_match = re.search(r'article:(\d+)', entity_urn_to_check) if entity_urn_to_check else None
                
                if article_match:
                    social_activity_counts_map[article_match.group(1)] = item
                    logger.info(f"Mapped social activity counts for article ID {article_match.group(1)}")
                elif entity_article_match:
                    social_activity_counts_map[entity_article_match.group(1)] = item
                    logger.info(f"Mapped social activity counts for article ID {entity_article_match.group(1)} from entityUrn")
                
                # Extract videoAsset ID
                video_asset_match = re.search(r'videoAsset:(\d+)', urn) if urn else None
                entity_video_asset_match = re.search(r'videoAsset:(\d+)', entity_urn_to_check) if entity_urn_to_check else None
                
                if video_asset_match:
                    social_activity_counts_map[video_asset_match.group(1)] = item
                    logger.info(f"Mapped social activity counts for videoAsset ID {video_asset_match.group(1)}")
                elif entity_video_asset_match:
                    social_activity_counts_map[entity_video_asset_match.group(1)] = item
                    logger.info(f"Mapped social activity counts for videoAsset ID {entity_video_asset_match.group(1)} from entityUrn")
                
                # ALWAYS map by full URN for reliable lookups (not else-if!)
                if urn:
                    social_activity_counts_map[urn] = item
                if entity_urn_to_check and entity_urn_to_check != urn:
                    social_activity_counts_map[entity_urn_to_check] = item
                
                # Log if we have direct social metrics
                if 'numLikes' in item or 'numComments' in item:
                    logger.info(f"Direct social metrics - Likes: {item.get('numLikes')}, Comments: {item.get('numComments')}")
        
        logger.info(f"Built maps: social_details={len(social_detail_map)}, actors={len(actor_map)}, social_counts={len(social_activity_counts_map)}")
        
        # Second pass: Extract posts
        for item in included_data:
            if not isinstance(item, dict):
                continue
                
            # Look for items that appear to be posts
            # These have updateMetadata or are feed update types
            if not (item.get('updateMetadata') or item.get('$type', '').endswith('Update')):
                continue
                
            try:
                post_data = self._extract_post_details(item, actor_map, social_activity_counts_map, included_data)
                if post_data:
                    posts.append(post_data)
            except Exception as e:
                logger.error(f"Error extracting post details: {str(e)}")
                continue
        
        logger.info(f"Extracted {len(posts)} posts from batch")
        return posts
    
    def _extract_post_details(
        self, 
        item: Dict[str, Any], 
        actor_map: Dict[str, Any],
        social_activity_counts_map: Dict[str, Any],
        included_data: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract details from a single post item.
        
        Args:
            item: A single item from the LinkedIn API response
            actor_map: Map of actor entities
            social_activity_counts_map: Map of social activity counts
            
        Returns:
            Dictionary with post details or None if extraction fails
        """
        # Extract post ID (COMPREHENSIVE - like client-side)
        post_id = None
        ugc_post_id = None
        article_id = None
        video_asset_id = None
        entity_urn = item.get('entityUrn', '')
        update_metadata = item.get('updateMetadata', {})
        
        # Helper function to extract IDs from URNs
        def extract_ids_from_urn(urn: str):
            nonlocal post_id, ugc_post_id, article_id, video_asset_id
            if not urn:
                return
            
            # Extract activity ID
            activity_match = re.search(r'activity:(\d+)', urn)
            if activity_match and not post_id:
                post_id = activity_match.group(1)
            
            # Extract ugcPost ID
            ugc_match = re.search(r'ugcPost:(\d+)', urn)
            if ugc_match:
                ugc_post_id = ugc_match.group(1)
                if not post_id:
                    post_id = ugc_post_id
            
            # Extract article ID
            article_match = re.search(r'article:(\d+)', urn)
            if article_match:
                article_id = article_match.group(1)
                if not post_id:
                    post_id = article_id
            
            # Extract videoAsset ID
            video_match = re.search(r'videoAsset:(\d+)', urn)
            if video_match:
                video_asset_id = video_match.group(1)
                if not post_id:
                    post_id = video_asset_id
        
        # Extract from all possible locations
        extract_ids_from_urn(entity_urn)
        if update_metadata and update_metadata.get('urn'):
            extract_ids_from_urn(update_metadata['urn'])
        if item.get('activity'):
            extract_ids_from_urn(item['activity'])
        
        # Extract from content if present
        if item.get('content'):
            content = item['content']
            if content.get('linkedInVideoComponent'):
                video_comp = content['linkedInVideoComponent']
                if video_comp.get('videoUrn'):
                    extract_ids_from_urn(video_comp['videoUrn'])
                if video_comp.get('urn'):
                    extract_ids_from_urn(video_comp['urn'])
            if content.get('externalVideoComponent'):
                video_comp = content['externalVideoComponent']
                if video_comp.get('videoUrn'):
                    extract_ids_from_urn(video_comp['videoUrn'])
                if video_comp.get('urn'):
                    extract_ids_from_urn(video_comp['urn'])
            if content.get('shareUrn'):
                extract_ids_from_urn(content['shareUrn'])
            if content.get('backendUrn'):
                extract_ids_from_urn(content['backendUrn'])
        
        # Extract from metadata
        if item.get('metadata'):
            metadata = item['metadata']
            if metadata.get('shareUrn'):
                extract_ids_from_urn(metadata['shareUrn'])
            if metadata.get('backendUrn'):
                extract_ids_from_urn(metadata['backendUrn'])
            
        if not post_id:
            return None
        
        # Extract author info
        actor = item.get('actor', {})
        author_name = ""
        author_profile_id = ""
        author_job_title = None
        
        if actor:
            # Author name
            if isinstance(actor.get('name'), dict):
                author_name = actor['name'].get('text', '')
            elif isinstance(actor.get('name'), str):
                author_name = actor['name']
                
            # Profile ID
            if isinstance(actor.get('name'), dict) and actor['name'].get('attributes'):
                for attr in actor['name']['attributes']:
                    if '*miniProfile' in attr:
                        mini_profile = attr['*miniProfile']
                        urn_parts = mini_profile.split(':')
                        author_profile_id = urn_parts[-1] if urn_parts else ""
                        break
            
            # Job title
            if isinstance(actor.get('description'), dict):
                author_job_title = actor['description'].get('text')
            elif isinstance(actor.get('description'), str):
                author_job_title = actor['description']
        
        # Extract post content
        post_content = ""
        commentary = item.get('commentary', {})
        if isinstance(commentary.get('text'), dict):
            post_content = commentary['text'].get('text', '')
        elif isinstance(commentary.get('text'), str):
            post_content = commentary['text']
        
        # Extract timestamp
        timestamp = update_metadata.get('timestamp') if update_metadata else None
        
        # Extract likes and comments - comprehensive check (from old project)
        def extract_social_metrics(source: Dict[str, Any]) -> tuple[bool, int, int]:
            """
            Extract social metrics from an item (like old project's extractSocialMetrics).
            
            Returns:
                Tuple of (found, likes, comments)
            """
            item_likes = 0
            item_comments = 0
            found = False
            
            # Check direct numLikes and numComments properties
            if 'numLikes' in source:
                item_likes = source.get('numLikes', 0) or 0
                found = True
            if 'numComments' in source:
                item_comments = source.get('numComments', 0) or 0
                found = True
            
            # Check totalSocialActivityCounts
            if 'totalSocialActivityCounts' in source:
                total_counts = source['totalSocialActivityCounts']
                if 'numLikes' in total_counts:
                    item_likes = total_counts.get('numLikes', 0) or 0
                    found = True
                if 'numComments' in total_counts:
                    item_comments = total_counts.get('numComments', 0) or 0
                    found = True
            
            # Check reactions array
            if 'reactions' in source and isinstance(source.get('reactions'), list):
                total_reactions = sum(
                    reaction.get('count', 0) or 0 
                    for reaction in source['reactions']
                )
                if total_reactions > 0:
                    item_likes = total_reactions
                    found = True
            
            # Check reactionTypeCounts array
            if 'reactionTypeCounts' in source and isinstance(source.get('reactionTypeCounts'), list):
                total_reactions = sum(
                    reaction.get('count', 0) or 0 
                    for reaction in source['reactionTypeCounts']
                )
                if total_reactions > 0:
                    item_likes = total_reactions
                    found = True
            
            return found, item_likes, item_comments
        
        # Extract ALL possible IDs from this post (like old project does)
        all_post_ids = []
        
        # Add simple post ID
        simple_post_id = post_id.split(':')[-1] if ':' in post_id else post_id
        if simple_post_id:
            all_post_ids.append(simple_post_id)
        
        # Add UGC post ID if different
        if ugc_post_id and ugc_post_id != simple_post_id:
            all_post_ids.append(ugc_post_id)
        
        # Add full post ID
        if post_id and post_id != simple_post_id:
            all_post_ids.append(post_id)
        
        # Add entity URN if available
        if 'entityUrn' in item:
            all_post_ids.append(item['entityUrn'])
            # Extract any IDs from entity URN
            activity_match = re.search(r'activity:(\d+)', item['entityUrn'])
            if activity_match:
                all_post_ids.append(activity_match.group(1))
            ugc_match = re.search(r'ugcPost:(\d+)', item['entityUrn'])
            if ugc_match:
                all_post_ids.append(ugc_match.group(1))
        
        # Add URN from updateMetadata if available
        if update_metadata and 'urn' in update_metadata:
            all_post_ids.append(update_metadata['urn'])
            activity_match = re.search(r'activity:(\d+)', update_metadata['urn'])
            if activity_match:
                all_post_ids.append(activity_match.group(1))
        
        likes = 0
        comments = 0
        found_metrics = False
        
        # Method 1: Check directly on the update item itself
        found_metrics, likes, comments = extract_social_metrics(item)
        
        # Method 2: Try ALL post IDs in social activity counts map (like old project)
        if not found_metrics:
            for post_id_variant in all_post_ids:
                if post_id_variant in social_activity_counts_map:
                    found_metrics, likes, comments = extract_social_metrics(
                        social_activity_counts_map[post_id_variant]
                    )
                    if found_metrics:
                        break
        
        # Method 3: DEEP SEARCH - Look through ALL included items (like old project Method 7)
        if not found_metrics:
            logger.info(f"Deep search for metrics - checking all IDs: {', '.join(str(x) for x in all_post_ids)}")
            
            for included_item in included_data:
                # Skip items that don't have social metrics properties
                if (not included_item.get('numLikes') and not included_item.get('numComments') and 
                    not included_item.get('reactionTypeCounts') and not included_item.get('reactions') and 
                    not included_item.get('totalSocialActivityCounts')):
                    continue
                
                # Check if this item is related to our post
                is_related = False
                
                # Check if the item has any URNs that match our post
                item_urn = included_item.get('urn', '')
                item_entity_urn = included_item.get('entityUrn', '')
                
                for urn in all_post_ids:
                    urn_str = str(urn)
                    if (item_urn == urn_str or item_entity_urn == urn_str or 
                        (item_urn and urn_str in item_urn) or 
                        (item_entity_urn and urn_str in item_entity_urn)):
                        is_related = True
                        break
                
                # If not directly related by URN, check if it contains our post ID in its JSON
                if not is_related:
                    import json
                    item_str = json.dumps(included_item)
                    for post_id_variant in all_post_ids:
                        if str(post_id_variant) in item_str:
                            is_related = True
                            break
                
                if is_related:
                    found_metrics, likes, comments = extract_social_metrics(included_item)
                    if found_metrics:
                        logger.info(f"Found metrics via deep search: {likes} likes, {comments} comments")
                        break
        
        # Only return if we have essential fields
        if not post_id or not post_content:
            return None
        
        # Build post URL based on ID type (like client-side)
        if ugc_post_id:
            post_url = f"https://www.linkedin.com/feed/update/urn:li:ugcPost:{ugc_post_id}/"
        elif article_id:
            post_url = f"https://www.linkedin.com/pulse/article/{article_id}/"
        elif video_asset_id:
            post_url = f"https://www.linkedin.com/video/event/{video_asset_id}/"
        else:
            post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}/"
        
        # Extract date with multiple methods (like client-side)
        post_date = None
        raw_date_str = None
        
        # Method 1: Common date fields
        if item.get('publishedAt') or item.get('published') or item.get('createdAt'):
            from datetime import datetime
            date_value = item.get('publishedAt') or item.get('published') or item.get('createdAt')
            try:
                post_date = datetime.fromtimestamp(date_value / 1000).isoformat() if date_value else None
            except:
                pass
        
        # Method 2: updateMetadata timestamp
        if not post_date and update_metadata and update_metadata.get('publishedAt'):
            try:
                from datetime import datetime
                post_date = datetime.fromtimestamp(update_metadata['publishedAt'] / 1000).isoformat()
            except:
                pass
        
        # Method 3: Actor subDescription (for relative time)
        if not post_date and actor and actor.get('subDescription'):
            sub_desc = actor['subDescription']
            if isinstance(sub_desc, dict) and sub_desc.get('accessibilityText'):
                raw_date_str = sub_desc['accessibilityText']
            elif isinstance(sub_desc, dict) and sub_desc.get('text'):
                raw_date_str = sub_desc['text']
            elif isinstance(sub_desc, str):
                raw_date_str = sub_desc
        
        # Method 4: timeContext (for relative time)
        if not post_date and not raw_date_str and item.get('timeContext'):
            time_context = item['timeContext']
            if isinstance(time_context, dict) and time_context.get('accessibilityText'):
                raw_date_str = time_context['accessibilityText']
            elif isinstance(time_context, dict) and time_context.get('text'):
                raw_date_str = time_context['text']
        
        # Extract image URL (like client-side)
        image_url = None
        if item.get('content'):
            content = item['content']
            # Check imageComponent
            if content.get('imageComponent'):
                img_comp = content['imageComponent']
                if img_comp.get('images') and isinstance(img_comp['images'], list):
                    for img in img_comp['images']:
                        if img.get('attributes'):
                            for attr in img['attributes']:
                                if attr.get('vectorImage'):
                                    vec_img = attr['vectorImage']
                                    if vec_img.get('rootUrl') and vec_img.get('artifacts'):
                                        # Find largest artifact
                                        largest = max(
                                            vec_img['artifacts'],
                                            key=lambda x: x.get('width', 0) * x.get('height', 0),
                                            default=None
                                        )
                                        if largest and largest.get('fileIdentifyingUrlPathSegment'):
                                            image_url = vec_img['rootUrl'] + largest['fileIdentifyingUrlPathSegment']
                                            break
            
            # Check contentEntities for thumbnails
            if not image_url and content.get('contentEntities'):
                for entity in content['contentEntities']:
                    if entity.get('thumbnail'):
                        thumb = entity['thumbnail']
                        if isinstance(thumb, dict) and thumb.get('url'):
                            image_url = thumb['url']
                            break
        
        # Detect video content (like client-side)
        is_video = False
        has_video = False
        video_type = None
        
        if item.get('content'):
            content = item['content']
            
            # Check linkedInVideoComponent
            if content.get('linkedInVideoComponent'):
                is_video = True
                has_video = True
                video_type = 'linkedin'
            
            # Check externalVideoComponent
            elif content.get('externalVideoComponent'):
                is_video = True
                has_video = True
                video_type = 'external'
        
        # Check metadata.video
        if not has_video and item.get('metadata') and item['metadata'].get('video'):
            is_video = True
            has_video = True
            video_type = 'metadata'
        
        # Check video asset ID or URL
        if not has_video and (video_asset_id or (post_url and 'video' in post_url)):
            is_video = True
            has_video = True
            video_type = 'urn'
        
        # Check content entities for video indicators
        if not has_video and item.get('content') and item['content'].get('contentEntities'):
            for entity in item['content']['contentEntities']:
                if (entity.get('$type') and 'Video' in entity.get('$type', '')):
                    is_video = True
                    has_video = True
                    video_type = 'entity'
                    break
        
        return {
            'postId': post_id,
            'postUrl': post_url,
            'ugcPostId': ugc_post_id,
            'articleId': article_id,
            'videoAssetId': video_asset_id,
            'authorName': author_name,
            'authorProfileId': author_profile_id,
            'postContent': post_content,
            'postDate': post_date,
            'postAge': raw_date_str,
            'likes': likes,
            'comments': comments,
            'imageUrl': image_url,
            'isVideo': is_video,
            'hasVideo': has_video,
            'videoType': video_type
        }

