"""
LinkedIn User Comments API service.

Fetches comments made by a specific user profile, including the posts they commented on
and parent comments if the comment was a reply.
"""
from typing import List, Dict, Any, Optional, Tuple, Set
from urllib.parse import quote, urlparse, parse_qs, unquote
import logging
import json
from pathlib import Path

from .base import LinkedInServiceBase
from .comments import LinkedInCommentsService
from ..utils.profile_id_extractor import extract_profile_id

logger = logging.getLogger(__name__)

# Debug mode - set to True to save debug data
DEBUG_PARENT_RESOLUTION = True
DEBUG_OUTPUT_DIR = Path("logs_debug/user_comments_debug")
SAVE_RAW_API_RESPONSES = True  # Set to False when problem is fixed

class LinkedInUserCommentsService(LinkedInServiceBase):
    """Service for fetching user profile comments."""
    
    USER_COMMENTS_QUERY_ID = 'voyagerFeedDashProfileUpdates.8f05a4e5ad12d9cb2b56eaa22afbcab9'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _save_debug_data(self, filename: str, data: Any) -> None:
        """Save debug data to file for analysis."""
        if not DEBUG_PARENT_RESOLUTION:
            return

        try:
            DEBUG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            filepath = DEBUG_OUTPUT_DIR / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"[DEBUG] Saved debug data to {filepath}")
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to save debug data: {e}")

    def _extract_commenter_details(self, comment: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract commenter name, headline, and profile ID from a comment object.

        Args:
            comment: Comment object from LinkedIn API

        Returns:
            Tuple of (commenter_name, commenter_headline, commenter_profile_id)
        """
        if not isinstance(comment, dict):
            return None, None, None

        commenter = comment.get('commenter', {})
        if not isinstance(commenter, dict):
            return None, None, None

        # Extract name from title
        name = None
        title_obj = commenter.get('title', {})
        if isinstance(title_obj, dict):
            name = self._extract_text_value(title_obj)

        # Extract headline from subtitle
        headline = commenter.get('subtitle')
        if isinstance(headline, dict):
            headline = self._extract_text_value(headline)
        elif not isinstance(headline, str):
            headline = None

        # Extract profile ID
        profile_id = None
        commenter_profile_id = commenter.get('commenterProfileId')
        if commenter_profile_id:
            profile_id = commenter_profile_id
        else:
            # Try to extract from actor
            actor = commenter.get('actor', {})
            if isinstance(actor, dict):
                profile_urn = actor.get('*profileUrn')
                if profile_urn and ':' in profile_urn:
                    # Extract ID from URN like "urn:li:fsd_profile:ACoAABkVEvgBp3i06XxDrVLz2rUjmE4TqHNSPGI"
                    profile_id = profile_urn.split(':')[-1]

        logger.debug(f"[EXTRACT_COMMENTER] Extracted - Name: {name}, Headline: {headline[:50] if headline else None}, ProfileId: {profile_id}")
        return name, headline, profile_id

    async def _fetch_parent_comment_details(self, parent_urn: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full parent comment details when the parent is returned as a stub.

        LinkedIn's user comments API returns parent comments (by other people) as stubs
        with only entityUrn. We need to fetch the full comment data separately.

        Args:
            parent_urn: Parent comment URN (e.g. "urn:li:fsd_comment:(7389689646349193216,urn:li:ugcPost:7389218381553631232)")

        Returns:
            Full comment object with commenter details and commentary, or None if fetch fails
        """
        if not parent_urn:
            return None

        try:
            # Parse the parent URN to extract post ID and comment ID
            post_id, comment_id = self._parse_comment_ids_from_urn(parent_urn)

            if not post_id or not comment_id:
                logger.warning(f"[FETCH_PARENT] Could not parse post/comment IDs from URN: {parent_urn}")
                return None

            logger.info(f"[FETCH_PARENT] Fetching parent comment {comment_id} from post {post_id}")

            # Use the CommentsService to fetch comments for this post
            from .comments import LinkedInCommentsService
            comments_service = LinkedInCommentsService(
                session=self.session,
                csrf_token=self.csrf_token
            )

            # Fetch comments for the post
            post_comments_response = await comments_service.get_comments_for_post(
                post_id=post_id,
                sort_order='RELEVANCE',
                count=100  # Should be enough to find the parent
            )

            if not post_comments_response or 'included' not in post_comments_response:
                logger.warning(f"[FETCH_PARENT] No comments data returned for post {post_id}")
                return None

            # Search for the parent comment in the response
            included = post_comments_response.get('included', [])
            for item in included:
                if item.get('$type') != 'com.linkedin.voyager.dash.social.Comment':
                    continue

                # Check if this is our parent comment
                item_post_id, item_comment_id = self._parse_comment_ids_from_urn(item.get('entityUrn', ''))
                if item_comment_id == comment_id:
                    logger.info(f"[FETCH_PARENT] Found parent comment {comment_id}")

                    # Verify it has full data
                    has_commentary = 'commentary' in item and item['commentary']
                    has_commenter = 'commenter' in item and item['commenter']

                    if has_commentary and has_commenter:
                        logger.info(f"[FETCH_PARENT] Parent comment has full data")
                        return item
                    else:
                        logger.warning(f"[FETCH_PARENT] Parent comment found but missing data - commentary: {has_commentary}, commenter: {has_commenter}")
                        return item  # Return even if incomplete

            logger.warning(f"[FETCH_PARENT] Parent comment {comment_id} not found in post {post_id} comments")
            return None

        except Exception as e:
            logger.error(f"[FETCH_PARENT] Error fetching parent comment details: {e}", exc_info=True)
            return None

    def _extract_text_value(self, value: Any) -> str:
        """
        Normalize LinkedIn text payloads (which often wrap strings in nested structures)
        into plain strings that can be returned in the API response.
        """
        if isinstance(value, str):
            return value
        
        if isinstance(value, dict):
            # Common LinkedIn pattern: {"text": "..."} or {"text": {"text": "..."}}.
            text_candidate = value.get('text')
            if text_candidate is not None:
                extracted = self._extract_text_value(text_candidate)
                if extracted:
                    return extracted
            
            # Some payloads use "value" instead of "text".
            value_candidate = value.get('value')
            if value_candidate is not None:
                extracted = self._extract_text_value(value_candidate)
                if extracted:
                    return extracted
        
        return ''

    def _get_item_type(self, item: Dict[str, Any]) -> str:
        """
        Extract the LinkedIn $type value, tolerating cases where the key cannot be
        accessed directly via item['$type'] (observed in normalized API responses).
        """
        if not isinstance(item, dict):
            return ''

        item_type = item.get('$type')
        if isinstance(item_type, str) and item_type:
            return item_type

        for key, value in item.items():
            if (
                isinstance(key, str)
                and key.endswith('type')
                and isinstance(value, str)
                and value.startswith('com.linkedin.')
            ):
                return value

        return ''

    def _parse_comment_ids_from_urn(self, urn: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract post reference (with prefix) and comment ID from LinkedIn comment URNs.

        Supports voyager (urn:li:comment) and fsd (urn:li:fsd_comment) formats.
        """
        if not urn or not isinstance(urn, str):
            return None, None

        try:
            if urn.startswith('urn:li:comment:(') and urn.endswith(')'):
                inner = urn[len('urn:li:comment:('):-1]
                parts = inner.split(',', 1)
                if len(parts) == 2:
                    post_part = parts[0].strip()
                    comment_part = parts[1].strip()
                    return post_part, comment_part

            if urn.startswith('urn:li:fsd_comment:(') and urn.endswith(')'):
                inner = urn[len('urn:li:fsd_comment:('):-1]
                parts = inner.split(',', 1)
                if len(parts) == 2:
                    comment_id = parts[0].strip()
                    post_part = parts[1].strip()
                    if post_part.startswith('urn:li:'):
                        post_part = post_part[len('urn:li:'):]
                    return post_part, comment_id
        except Exception:
            pass

        return None, None

    def _canonical_comment_urn(self, comment: Dict[str, Any]) -> Optional[str]:
        """
        Build a canonical voyager-style comment URN for lookup.
        """
        urn = comment.get('urn')
        if isinstance(urn, str) and urn:
            return urn

        entity_urn = comment.get('entityUrn')
        post_ref, comment_id = self._parse_comment_ids_from_urn(entity_urn)
        if post_ref and comment_id:
            return f"urn:li:comment:({post_ref},{comment_id})"

        permalink = comment.get('permalink')
        if isinstance(permalink, str) and permalink:
            try:
                parsed = urlparse(permalink)
                params = parse_qs(parsed.query)
                for key in ('replyUrn', 'commentUrn', 'dashCommentUrn'):
                    for value in params.get(key, []):
                        try:
                            decoded = unquote(value)
                        except Exception:
                            decoded = value
                        ref, cid = self._parse_comment_ids_from_urn(decoded)
                        if ref and cid:
                            return f"urn:li:comment:({ref},{cid})"
            except Exception:
                pass

        return None

    def _build_comment_entity_urn(self, post_ref: Optional[str], comment_id: Optional[str]) -> Optional[str]:
        """
        Construct the fsd comment entity URN from post/comment IDs.
        """
        if not post_ref or not comment_id:
            return None
        if not post_ref.startswith('urn:li:'):
            post_ref = f'urn:li:{post_ref}'
        return f"urn:li:fsd_comment:({comment_id},{post_ref})"

    def _extract_parent_id_from_permalink(self, permalink: str) -> Optional[Tuple[str, str]]:
        """
        Extract parent comment ID and URN from permalink.

        Returns:
            Tuple of (parent_urn, parent_comment_id) or (None, None)
        """
        if not permalink or not isinstance(permalink, str):
            logger.debug("[EXTRACT_PARENT_ID] No permalink provided")
            return None, None

        try:
            parsed_url = urlparse(permalink)
            params = parse_qs(parsed_url.query)

            logger.info(f"[EXTRACT_PARENT_ID] Permalink params: {list(params.keys())}")

            # Check if this is a reply (has replyUrn parameter)
            reply_urn_values = params.get('replyUrn', [])
            if not reply_urn_values:
                logger.debug("[EXTRACT_PARENT_ID] No replyUrn - this is a root comment, not a reply")
                return None, None

            # Get parent from commentUrn
            comment_urn_values = params.get('commentUrn', [])
            if not comment_urn_values:
                logger.warning("[EXTRACT_PARENT_ID] Has replyUrn but no commentUrn - unexpected structure")
                return None, None

            parent_urn = unquote(comment_urn_values[0])
            logger.info(f"[EXTRACT_PARENT_ID] Parent URN (from commentUrn): {parent_urn}")

            # Parse parent comment ID
            _, parent_comment_id = self._parse_comment_ids_from_urn(parent_urn)

            if not parent_comment_id:
                logger.warning(f"[EXTRACT_PARENT_ID] Could not parse parent comment ID from URN: {parent_urn}")
                return None, None

            logger.info(f"[EXTRACT_PARENT_ID] Extracted parent comment ID: {parent_comment_id}")
            return parent_urn, parent_comment_id

        except Exception as e:
            logger.error(f"[EXTRACT_PARENT_ID] Error parsing permalink: {e}", exc_info=True)
            return None, None

    def _find_parent_in_maps(
        self,
        parent_urn: str,
        parent_comment_id: str,
        parent_post_ref: Optional[str],
        comment_by_entity: Dict[str, Dict[str, Any]],
        comment_by_urn: Dict[str, Dict[str, Any]],
        comment_by_id: Dict[str, Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Search for parent comment in lookup maps.

        Args:
            parent_urn: The full parent URN
            parent_comment_id: The parent comment ID
            parent_post_ref: The post reference
            comment_by_entity: Entity URN lookup map
            comment_by_urn: URN lookup map
            comment_by_id: Comment ID lookup map

        Returns:
            Parent comment object if found, None otherwise
        """
        logger.info(f"[FIND_PARENT] Looking for parent comment ID: {parent_comment_id}")
        logger.info(f"[FIND_PARENT] Parent URN: {parent_urn}")
        logger.info(f"[FIND_PARENT] Available lookup maps sizes: entity={len(comment_by_entity)}, urn={len(comment_by_urn)}, id={len(comment_by_id)}")

        # Strategy 1: Try by full URN
        parent = comment_by_urn.get(parent_urn)
        if parent:
            logger.info(f"[FIND_PARENT] ✓ Found parent by URN: {parent_urn}")
            return parent
        else:
            logger.debug(f"[FIND_PARENT] ✗ Not found by URN: {parent_urn}")

        # Strategy 2: Try by comment ID only
        parent = comment_by_id.get(parent_comment_id)
        if parent:
            logger.info(f"[FIND_PARENT] ✓ Found parent by comment ID: {parent_comment_id}")
            return parent
        else:
            logger.debug(f"[FIND_PARENT] ✗ Not found by comment ID: {parent_comment_id}")

        # Strategy 3: Try by entity URN
        if parent_post_ref and parent_comment_id:
            entity_urn = self._build_comment_entity_urn(parent_post_ref, parent_comment_id)
            if entity_urn:
                logger.debug(f"[FIND_PARENT] Trying entity URN: {entity_urn}")
                parent = comment_by_entity.get(entity_urn)
                if parent:
                    logger.info(f"[FIND_PARENT] ✓ Found parent by entity URN: {entity_urn}")
                    return parent
                else:
                    logger.debug(f"[FIND_PARENT] ✗ Not found by entity URN: {entity_urn}")

        # Save debug data
        if DEBUG_PARENT_RESOLUTION:
            debug_data = {
                'parent_urn': parent_urn,
                'parent_comment_id': parent_comment_id,
                'parent_post_ref': parent_post_ref,
                'available_urns_sample': list(comment_by_urn.keys())[:10],
                'available_entity_urns_sample': list(comment_by_entity.keys())[:10],
                'available_ids_sample': list(comment_by_id.keys())[:10]
            }
            self._save_debug_data(f'parent_not_found_{parent_comment_id}.json', debug_data)

        logger.warning(f"[FIND_PARENT] ✗ Parent comment {parent_comment_id} NOT FOUND in any lookup map")
        return None

    def _get_comment_parent_from_permalink(
        self,
        comment: Dict[str, Any],
        comment_by_entity: Dict[str, Dict[str, Any]],
        comment_by_urn: Dict[str, Dict[str, Any]],
        comment_by_id: Dict[str, Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve parent comment using permalink query parameters.

        LinkedIn permalink structure for replies:
        - commentUrn: The PARENT comment URN
        - replyUrn: The SUB-COMMENT (reply) URN
        - dashCommentUrn: The PARENT comment in fsd format
        - dashReplyUrn: The SUB-COMMENT in fsd format

        This method extracts the parent comment ID from commentUrn and locates it.
        """
        permalink = comment.get('permalink')
        comment_entity_urn = comment.get('entityUrn', '')

        logger.info(f"[GET_PARENT] Processing comment: {comment_entity_urn}")
        logger.info(f"[GET_PARENT] Permalink: {permalink}")

        # Extract parent info from permalink
        parent_urn, parent_comment_id = self._extract_parent_id_from_permalink(permalink)

        if not parent_urn or not parent_comment_id:
            logger.debug(f"[GET_PARENT] No parent found for comment {comment_entity_urn}")
            return None

        # Parse parent post reference
        parent_post_ref, _ = self._parse_comment_ids_from_urn(parent_urn)

        # Find parent in lookup maps
        parent = self._find_parent_in_maps(
            parent_urn,
            parent_comment_id,
            parent_post_ref,
            comment_by_entity,
            comment_by_urn,
            comment_by_id
        )

        if parent:
            logger.info(f"[GET_PARENT] ✓ Successfully resolved parent for {comment_entity_urn}")
        else:
            logger.warning(f"[GET_PARENT] ✗ Failed to resolve parent for {comment_entity_urn}")

        return parent

    async def _augment_parent_comment_details(self, comments: List[Dict[str, Any]]) -> None:
        """
        Fetch missing parent comment metadata (text, commenter) when parent is returned as a stub.

        LinkedIn's user comments API returns parent comments (by other people) as stubs.
        We need to fetch the full comment data using a separate API call.
        """
        logger.info(f"[PARENT_AUGMENT] Starting parent augmentation for {len(comments)} comments")

        augmented_count = 0
        stub_count = 0

        for comment in comments:
            if not comment.get('isReply'):
                continue

            # Check if parent data is missing
            parent_urn = comment.get('parentCommentId')
            missing_text = not comment.get('parentCommentText')
            missing_name = not comment.get('parentCommenterName')

            if not parent_urn or (not missing_text and not missing_name):
                continue

            stub_count += 1
            logger.info(f"[PARENT_AUGMENT] Fetching parent comment details for URN: {parent_urn}")

            # Fetch full parent comment details
            full_parent = await self._fetch_parent_comment_details(parent_urn)

            if not full_parent:
                logger.warning(f"[PARENT_AUGMENT] Could not fetch parent comment: {parent_urn}")
                continue

            # Extract text from full parent
            if missing_text:
                parent_commentary = full_parent.get('commentary', {})
                parent_text = self._extract_text_value(
                    parent_commentary.get('text') if isinstance(parent_commentary, dict) else parent_commentary
                )
                if parent_text:
                    comment['parentCommentText'] = parent_text
                    logger.info(f"[PARENT_AUGMENT] ✓ Fetched parent comment text ({len(parent_text)} chars)")

            # Extract commenter details from full parent
            if missing_name:
                parent_name, parent_headline, parent_profile_id = self._extract_commenter_details(full_parent)
                if parent_name:
                    comment['parentCommenterName'] = parent_name
                    logger.info(f"[PARENT_AUGMENT] ✓ Fetched parent commenter name: {parent_name}")
                if parent_headline:
                    comment['parentCommenterHeadline'] = parent_headline
                if parent_profile_id:
                    comment['parentCommenterProfileId'] = parent_profile_id

            augmented_count += 1

        logger.info(f"[PARENT_AUGMENT] Augmented {augmented_count}/{stub_count} parent comments")
    
    def _build_user_comments_url(
        self,
        profile_id: str,
        start: int = 0,
        count: int = 20,
        pagination_token: Optional[str] = None
    ) -> str:
        """
        Build the LinkedIn GraphQL URL for fetching user comments.
        
        Args:
            profile_id: LinkedIn profile ID (e.g., "ACoAABkVEvgBp3i06XxDrVLz2rUjmE4TqHNSPGI")
            start: Starting index for pagination
            count: Number of items to fetch
            pagination_token: Optional pagination token from previous response
            
        Returns:
            Full LinkedIn GraphQL API URL
            
        Raises:
            ValueError: If profile_id is invalid
        """
        if not profile_id or not isinstance(profile_id, str):
            raise ValueError('Profile ID is required and must be a string')
        
        logger.info(f"[BUILD_URL] Building URL for profile: {profile_id}")
        
        # Build profile URN - manually encode colons like other profile endpoints
        encoded_profile_urn = f"urn%3Ali%3Afsd_profile%3A{profile_id}"
        
        # Build variables string - MUST match exact order
        variables_parts = [
            f"count:{count}",
            f"start:{start}",
            f"profileUrn:{encoded_profile_urn}"
        ]
        
        # Add pagination token if present
        if pagination_token:
            # URL-encode the pagination token (it often contains = signs)
            encoded_token = quote(pagination_token, safe='')
            variables_parts.append(f"paginationToken:{encoded_token}")
            logger.info(f"[BUILD_URL] Using pagination token: {pagination_token}")
        
        variables_str = ",".join(variables_parts)
        
        url = (
            f"{self.GRAPHQL_BASE_URL}?variables="
            f"({variables_str})"
            f"&queryId={self.USER_COMMENTS_QUERY_ID}"
        )
        
        logger.info(f"[BUILD_URL] ===== FULL URL BEING SENT =====")
        logger.info(f"[BUILD_URL] {url}")
        logger.info(f"[BUILD_URL] ================================")
        logger.info(f"[BUILD_URL] Profile ID input: {profile_id}")
        logger.info(f"[BUILD_URL] Encoded profile URN: {encoded_profile_urn}")
        logger.info(f"[BUILD_URL] Variables string: {variables_str}")
        return url
    
    def _build_lookup_maps(self, included: List[Dict[str, Any]]) -> tuple[Dict, Dict, Dict, Dict]:
        """
        Build lookup maps from the included array for efficient data access.

        Following LinkedIn's sideloaded API pattern:
        - Updates contain post data
        - Comments contain comment/reply data

        Args:
            included: The 'included' array from API response

        Returns:
            Tuple of (update_map, comment_map_by_entity_urn, comment_map_by_urn, comment_map_by_comment_id)
        """
        update_map = {}
        comment_map_by_entity_urn = {}
        comment_map_by_urn = {}
        comment_map_by_comment_id = {}

        comment_debug_info = []  # For debugging

        for item in included:
            if not isinstance(item, dict):
                continue

            item_type = self._get_item_type(item)
            entity_urn = item.get('entityUrn', '')
            urn = item.get('urn', '')

            is_update = (
                item_type in (
                    'com.linkedin.voyager.dash.feed.Update',
                    'com.linkedin.voyager.feed.render.UpdateV2',
                )
                or (isinstance(entity_urn, str) and 'fsd_update' in entity_urn)
            )

            is_comment = (
                item_type == 'com.linkedin.voyager.dash.social.Comment'
                or (isinstance(entity_urn, str) and 'fsd_comment' in entity_urn)
                or (isinstance(urn, str) and urn.startswith('urn:li:comment:'))
            )

            # Update objects (posts)
            if is_update:
                if entity_urn:
                    update_map[entity_urn] = item

            # Comment objects
            elif is_comment:
                if entity_urn:
                    comment_map_by_entity_urn[entity_urn] = item

                candidate_urns = set()
                if isinstance(urn, str) and urn:
                    candidate_urns.add(urn)

                canonical_urn = self._canonical_comment_urn(item)
                if canonical_urn:
                    candidate_urns.add(canonical_urn)

                # Add URNs derived from permalink query parameters
                # IMPORTANT: Only add URNs that refer to THIS comment, not parent/child comments
                permalink = item.get('permalink')
                if isinstance(permalink, str) and permalink:
                    try:
                        parsed = urlparse(permalink)
                        params = parse_qs(parsed.query)

                        # Extract THIS comment's ID from entity_urn
                        _, this_comment_id = self._parse_comment_ids_from_urn(entity_urn)

                        # Only add permalink URNs that match THIS comment's ID
                        for key in ('commentUrn', 'replyUrn', 'dashCommentUrn', 'dashReplyUrn'):
                            for value in params.get(key, []):
                                try:
                                    decoded = unquote(value)
                                except Exception:
                                    decoded = value

                                if decoded:
                                    # Check if this URN refers to this comment
                                    _, urn_comment_id = self._parse_comment_ids_from_urn(decoded)
                                    if urn_comment_id == this_comment_id:
                                        candidate_urns.add(decoded)
                    except Exception:
                        pass

                # Include entity URN variants
                if isinstance(entity_urn, str) and entity_urn:
                    candidate_urns.add(entity_urn)
                    post_ref, comment_id = self._parse_comment_ids_from_urn(entity_urn)
                    canonical_from_entity = self._canonical_comment_urn({'urn': None, 'entityUrn': entity_urn})
                    if canonical_from_entity:
                        candidate_urns.add(canonical_from_entity)
                    if post_ref and comment_id:
                        candidate_urns.add(f"urn:li:comment:({post_ref},{comment_id})")

                # Track by comment ID for fallback lookup
                for candidate in list(candidate_urns):
                    post_ref, comment_id = self._parse_comment_ids_from_urn(candidate)
                    if comment_id:
                        comment_map_by_comment_id[comment_id] = item
                        entity_variant = self._build_comment_entity_urn(post_ref, comment_id)
                        if entity_variant:
                            candidate_urns.add(entity_variant)

                for candidate in candidate_urns:
                    if candidate and candidate not in comment_map_by_urn:
                        comment_map_by_urn[candidate] = item

                # Save debug info for this comment
                if DEBUG_PARENT_RESOLUTION:
                    _, comment_id = self._parse_comment_ids_from_urn(entity_urn)
                    if comment_id:
                        comment_debug_info.append({
                            'comment_id': comment_id,
                            'entity_urn': entity_urn,
                            'urn': urn,
                            'permalink': permalink,
                            'all_candidate_urns': list(candidate_urns),
                            'has_commentary': 'commentary' in item
                        })

        logger.info(
            f"[BUILD_MAPS] Built lookup maps - Updates: {len(update_map)}, "
            f"Comments (by entity): {len(comment_map_by_entity_urn)}, "
            f"Comments (by urn): {len(comment_map_by_urn)}, "
            f"Comments (by id): {len(comment_map_by_comment_id)}"
        )

        # Save debug data
        if DEBUG_PARENT_RESOLUTION and comment_debug_info:
            self._save_debug_data('comment_lookup_maps.json', {
                'total_comments': len(comment_debug_info),
                'comment_details': comment_debug_info,
                'entity_urn_keys': list(comment_map_by_entity_urn.keys()),
                'urn_keys_sample': list(comment_map_by_urn.keys())[:20],
                'id_keys': list(comment_map_by_comment_id.keys())
            })

        return update_map, comment_map_by_entity_urn, comment_map_by_urn, comment_map_by_comment_id
    
    def _extract_reply_urn_from_social_detail(self, social_detail_urn: str) -> Optional[str]:
        """
        Extract reply URN from socialDetail URN string.
        
        Format: urn:li:fsd_socialDetail:(POST_URN,COMMENT_URN,REPLY_URN)
        
        Args:
            social_detail_urn: The socialDetail URN string
            
        Returns:
            Reply URN if found, None otherwise
        """
        if not social_detail_urn:
            return None
        
        try:
            open_paren = social_detail_urn.find('(')
            close_paren = social_detail_urn.rfind(')')
            if open_paren == -1 or close_paren == -1 or close_paren <= open_paren:
                return None

            inner = social_detail_urn[open_paren + 1:close_paren]
            parts = []
            buffer = []
            depth = 0

            for char in inner:
                if char == ',' and depth == 0:
                    segment = ''.join(buffer).strip()
                    if segment:
                        parts.append(segment)
                    buffer = []
                    continue

                buffer.append(char)
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth = max(depth - 1, 0)

            # Append the final segment
            segment = ''.join(buffer).strip()
            if segment:
                parts.append(segment)

            if len(parts) >= 3:
                reply_urn = parts[2].strip()
                if reply_urn != 'urn:li:highlightedReply:-' and reply_urn.startswith('urn:li:comment:'):
                    return reply_urn
        except Exception as e:
            logger.warning(f"[EXTRACT_REPLY_URN] Error parsing socialDetail: {e}")
        
        return None
    
    def _extract_post_url_from_update(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Extract post URL from update object.
        
        Args:
            update: Update object from included array
            
        Returns:
            Post URL if found, None otherwise
        """
        try:
            social_content = update.get('socialContent', {})
            if isinstance(social_content, dict):
                share_url = social_content.get('shareUrl')
                if share_url:
                    return share_url
            
            # Check for permalink
            permalink = update.get('permalink')
            if permalink:
                return permalink
            
            # Try to construct from entity URN
            entity_urn = update.get('entityUrn', '')
            if 'activity:' in entity_urn:
                activity_id = entity_urn.split('activity:')[-1].rstrip(')')
                return f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"
            elif 'ugcPost:' in entity_urn:
                ugc_id = entity_urn.split('ugcPost:')[-1].rstrip(')')
                return f"https://www.linkedin.com/feed/update/urn:li:ugcPost:{ugc_id}"
        
        except Exception as e:
            logger.warning(f"[EXTRACT_POST_URL] Error extracting URL: {e}")
        
        return None
    
    def _process_user_comments_batch(
        self,
        included: List[Dict[str, Any]],
        elements: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of user comments with full context.
        
        Extracts:
        - User's comment text
        - Post text and URL the comment was on
        - Parent comment (if reply) with text and ID
        
        Args:
            included: The 'included' array from API response
            elements: List of update URNs from main data
            
        Returns:
            List of user comment detail objects
        """
        if not isinstance(included, list) or not isinstance(elements, list):
            logger.error('[PROCESS_BATCH] Invalid input data')
            return []
        
        # Build lookup maps
        update_map, comment_by_entity, comment_by_urn, comment_by_id = self._build_lookup_maps(included)
        
        results = []
        seen_comment_ids: set[str] = set()
        
        for update_urn in elements:
            try:
                # Get the update object
                update = update_map.get(update_urn)
                if not update:
                    logger.warning(f"[PROCESS_BATCH] Update not found: {update_urn}")
                    continue
                
                # Get post text
                post_commentary = update.get('commentary', {})
                post_text = self._extract_text_value(post_commentary.get('text') if isinstance(post_commentary, dict) else post_commentary)
                post_url = self._extract_post_url_from_update(update)
                
                # Get header to determine scenario
                header_obj = update.get('header', {})
                header_text = ''
                if isinstance(header_obj, dict):
                    # The actual text is inside a nested 'text' object
                    header_text_obj = header_obj.get('text', {})
                    header_text = self._extract_text_value(header_text_obj)
                
                # Get highlighted comment
                highlighted_comments = update.get('*highlightedComments', [])
                if not highlighted_comments:
                    logger.warning(f"[PROCESS_BATCH] No highlighted comments in update: {update_urn}")
                    continue
                
                highlighted_comment_urn = highlighted_comments[0]
                highlighted_comment = comment_by_entity.get(highlighted_comment_urn)

                if not highlighted_comment:
                    logger.warning(f"[PROCESS_BATCH] Highlighted comment not found: {highlighted_comment_urn}")
                    continue
                
                # Scenario A: User commented on post (no parent)
                if 'commented on' in header_text.lower():
                    highlighted_commentary = highlighted_comment.get('commentary', {})
                    user_comment_text = self._extract_text_value(
                        highlighted_commentary.get('text') if isinstance(highlighted_commentary, dict) else highlighted_commentary
                    )
                    comment_id = (
                        highlighted_comment.get('urn')
                        or self._canonical_comment_urn(highlighted_comment)
                        or highlighted_comment.get('entityUrn', '')
                    )
                    
                    # Check if there's a reply to this comment
                    social_detail_urn = highlighted_comment.get('*socialDetail', '')
                    reply_urn = self._extract_reply_urn_from_social_detail(social_detail_urn)
                    
                    reply_text = None
                    reply_id = None
                    if reply_urn:
                        reply_comment = comment_by_urn.get(reply_urn)
                        if not reply_comment:
                            _, reply_comment_id_lookup = self._parse_comment_ids_from_urn(reply_urn)
                            if reply_comment_id_lookup:
                                reply_comment = comment_by_id.get(reply_comment_id_lookup)
                        if reply_comment:
                            reply_commentary = reply_comment.get('commentary', {})
                            reply_text = self._extract_text_value(
                                reply_commentary.get('text') if isinstance(reply_commentary, dict) else reply_commentary
                            )
                            reply_id = (
                                reply_comment.get('urn')
                                or self._canonical_comment_urn(reply_comment)
                                or reply_comment.get('entityUrn', '')
                            )
                    
                    if comment_id:
                        if comment_id in seen_comment_ids:
                            continue
                        seen_comment_ids.add(comment_id)
                    
                    results.append({
                        'commentText': user_comment_text,
                        'commentId': comment_id,
                        'postText': post_text,
                        'postUrl': post_url,
                        'parentCommentText': None,
                        'parentCommentId': None,
                        'parentCommenterName': None,
                        'parentCommenterHeadline': None,
                        'parentCommenterProfileId': None,
                        'isReply': False,
                        'replyToUserCommentText': reply_text,
                        'replyToUserCommentId': reply_id
                    })
                
                # Scenario B: User replied to a comment
                elif 'replied to' in header_text.lower():
                    logger.info(f"[PROCESS_BATCH][SCENARIO_B] Processing 'replied to' scenario for update {update_urn}")

                    # IMPORTANT: Check if highlighted_comment has commentary
                    # If it has commentary, it's the REPLY (user's comment)
                    # If it doesn't have commentary, it's the PARENT (the comment you replied to)
                    highlighted_commentary = highlighted_comment.get('commentary')
                    highlighted_has_text = highlighted_commentary and (
                        isinstance(highlighted_commentary, str) or
                        (isinstance(highlighted_commentary, dict) and highlighted_commentary.get('text'))
                    )

                    logger.info(f"[PROCESS_BATCH][SCENARIO_B] Highlighted comment has commentary: {highlighted_has_text}")

                    if highlighted_has_text:
                        # Case 1: highlighted_comment is the user's REPLY - use permalink to find parent
                        reply_comment = highlighted_comment
                        reply_entity_urn = reply_comment.get('entityUrn', '')
                        logger.info(f"[PROCESS_BATCH][SCENARIO_B] Case 1: Highlighted comment IS the reply - {reply_entity_urn}")

                        # Find parent using permalink
                        parent_comment = self._get_comment_parent_from_permalink(
                            reply_comment,
                            comment_by_entity,
                            comment_by_urn,
                            comment_by_id
                        )

                        if not parent_comment:
                            logger.warning(f"[PROCESS_BATCH][SCENARIO_B] Could not find parent for reply via permalink")
                            continue

                    else:
                        # Case 2: highlighted_comment IS THE PARENT (no commentary)
                        # The reply is the user's comment - find it via socialDetail
                        logger.info(f"[PROCESS_BATCH][SCENARIO_B] Case 2: Highlighted comment IS the parent (no commentary)")
                        parent_comment = highlighted_comment

                        # Find the reply via socialDetail
                        social_detail_urn = highlighted_comment.get('*socialDetail', '')
                        reply_urn = self._extract_reply_urn_from_social_detail(social_detail_urn)

                        if not reply_urn:
                            logger.warning(f"[PROCESS_BATCH][SCENARIO_B] Could not extract reply URN from socialDetail")
                            continue

                        reply_comment = comment_by_urn.get(reply_urn)
                        if not reply_comment:
                            _, reply_comment_id = self._parse_comment_ids_from_urn(reply_urn)
                            if reply_comment_id:
                                reply_comment = comment_by_id.get(reply_comment_id)

                        if not reply_comment:
                            logger.warning(f"[PROCESS_BATCH][SCENARIO_B] Could not find reply comment: {reply_urn}")
                            continue

                        reply_entity_urn = reply_comment.get('entityUrn', '')
                        logger.info(f"[PROCESS_BATCH][SCENARIO_B] Found reply comment via socialDetail: {reply_entity_urn}")

                    # Now we have BOTH reply_comment and parent_comment
                    logger.info(f"[PROCESS_BATCH][SCENARIO_B] Reply comment entity URN: {reply_comment.get('entityUrn', '')}")
                    logger.info(f"[PROCESS_BATCH][SCENARIO_B] Parent comment entity URN: {parent_comment.get('entityUrn', '')}")

                    # Extract user's reply text and ID
                    reply_commentary = reply_comment.get('commentary', {})
                    user_comment_text = self._extract_text_value(
                        reply_commentary.get('text') if isinstance(reply_commentary, dict) else reply_commentary
                    )
                    comment_id = (
                        reply_comment.get('urn')
                        or self._canonical_comment_urn(reply_comment)
                        or reply_comment.get('entityUrn', '')
                    )

                    logger.info(f"[PROCESS_BATCH][SCENARIO_B] User's reply comment ID: {comment_id}")
                    logger.info(f"[PROCESS_BATCH][SCENARIO_B] User's reply text: {user_comment_text[:100]}...")

                    # parent_comment is already set above in Case 1 or Case 2
                    # Verify parent_comment is valid and not the same as reply_comment
                    parent_comment_entity_urn = parent_comment.get('entityUrn', '') if isinstance(parent_comment, dict) else ''
                    reply_comment_entity_urn = reply_comment.get('entityUrn', '')

                    if parent_comment_entity_urn == reply_comment_entity_urn:
                        logger.error(f"[PROCESS_BATCH][SCENARIO_B] CRITICAL ERROR: Parent and reply are the same comment! {parent_comment_entity_urn}")
                        logger.error(f"[PROCESS_BATCH][SCENARIO_B] This should never happen. Skipping this reply.")
                        continue

                    # Extract parent comment details
                    parent_commentary = parent_comment.get('commentary', {}) if isinstance(parent_comment, dict) else {}
                    parent_comment_text = self._extract_text_value(
                        parent_commentary.get('text') if isinstance(parent_commentary, dict) else parent_commentary
                    )

                    # Check if parent is a stub (has entityUrn but no commentary/commenter)
                    parent_is_stub = (
                        isinstance(parent_comment, dict) and
                        parent_comment.get('entityUrn') and
                        not parent_comment.get('commentary') and
                        not parent_comment.get('commenter')
                    )

                    if parent_is_stub:
                        logger.warning(f"[PROCESS_BATCH][SCENARIO_B] Parent comment is a STUB (LinkedIn API limitation) - will fetch full details later")
                    elif not parent_comment_text:
                        logger.warning(f"[PROCESS_BATCH][SCENARIO_B] Parent comment has NO TEXT (unexpected)")

                    parent_comment_id = (
                        parent_comment.get('urn')
                        or self._canonical_comment_urn(parent_comment)
                        or parent_comment.get('entityUrn', '')
                        if isinstance(parent_comment, dict) else ''
                    )

                    # Extract parent commenter details (will be empty for stubs)
                    parent_commenter_name, parent_commenter_headline, parent_commenter_profile_id = self._extract_commenter_details(parent_comment)

                    logger.info(f"[PROCESS_BATCH][SCENARIO_B] Found parent comment ID: {parent_comment_id}")
                    logger.info(f"[PROCESS_BATCH][SCENARIO_B] Parent comment text length: {len(parent_comment_text)} chars")
                    logger.info(f"[PROCESS_BATCH][SCENARIO_B] Parent commenter: {parent_commenter_name} (Profile ID: {parent_commenter_profile_id})")

                    if comment_id:
                        if comment_id in seen_comment_ids:
                            logger.debug(f"[PROCESS_BATCH][SCENARIO_B] Skipping duplicate comment {comment_id}")
                            continue
                        seen_comment_ids.add(comment_id)

                    results.append({
                        'commentText': user_comment_text,
                        'commentId': comment_id,
                        'postText': post_text,
                        'postUrl': post_url,
                        'parentCommentText': parent_comment_text,
                        'parentCommentId': parent_comment_id,
                        'parentCommenterName': parent_commenter_name,
                        'parentCommenterHeadline': parent_commenter_headline,
                        'parentCommenterProfileId': parent_commenter_profile_id,
                        'isReply': True,
                        'replyToUserCommentText': None,
                        'replyToUserCommentId': None
                    })

                    logger.info(f"[PROCESS_BATCH][SCENARIO_B] ✓ Successfully processed reply comment")
                
            except Exception as e:
                logger.error(f"[PROCESS_BATCH] Error processing update: {str(e)}")
                continue
        
        logger.info(f"[PROCESS_BATCH] Extracted {len(results)} user comments from batch")
        return results
    
    def _parse_user_comments_response(
        self,
        data: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], Optional[str], Optional[int]]:
        """
        Parse LinkedIn API response to extract user comment details.
        
        Args:
            data: Raw JSON response from LinkedIn API
            
        Returns:
            Tuple of (list of comment details, pagination token, total count)
        """
        logger.info(f"[PARSE_RESPONSE] Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        pagination_token = None
        total_count = None
        
        # Navigate to the main data
        elements = []
        if 'data' in data and isinstance(data['data'], dict):
            data_section = data['data']
            if 'data' in data_section and isinstance(data_section['data'], dict):
                feed_data = data_section['data'].get('feedDashProfileUpdatesByMemberComments', {})
                if isinstance(feed_data, dict):
                    # Get pagination token
                    metadata = feed_data.get('metadata', {})
                    if isinstance(metadata, dict):
                        pagination_token = metadata.get('paginationToken')
                        if pagination_token:
                            logger.info(f"[PARSE_RESPONSE] Found pagination token: {pagination_token}")
                    
                    # Get paging info
                    paging = feed_data.get('paging', {})
                    if isinstance(paging, dict):
                        total_count = paging.get('total', 0)
                        logger.info(f"[PARSE_RESPONSE] Paging - total: {total_count}")
                    
                    # Get elements (list of update URNs)
                    elements = feed_data.get('*elements', [])
                    if isinstance(elements, list):
                        logger.info(f"[PARSE_RESPONSE] Found {len(elements)} elements")
        
        # Get included array
        included = data.get('included', [])
        
        if not included or not elements:
            logger.info('[PARSE_RESPONSE] No data to process')
            return [], pagination_token, total_count
        
        logger.info(f"[PARSE_RESPONSE] Processing {len(elements)} updates with {len(included)} included items")

        # Save full raw response for debugging (with timestamp to avoid overwriting)
        if SAVE_RAW_API_RESPONSES:
            import time
            timestamp = int(time.time())
            self._save_debug_data(f'raw_api_response_{timestamp}.json', {
                'elements': elements,
                'included': included
            })
            logger.info(f"[DEBUG] Saved raw API response with timestamp {timestamp}")

        # Process the batch
        user_comments = self._process_user_comments_batch(included, elements)
        
        return user_comments, pagination_token, total_count
    
    async def fetch_user_comments(
        self,
        profile_id_or_url: str,
        start: int = 0,
        count: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetch comments made by a specific user profile.
        
        Args:
            profile_id_or_url: LinkedIn profile ID or URL
            start: Starting index for pagination
            count: Number of comments to fetch
            
        Returns:
            List of user comment detail objects
            
        Raises:
            ValueError: If parameters are invalid
            httpx.HTTPStatusError: If the API request fails
        """
        # Input validation
        if not profile_id_or_url or not isinstance(profile_id_or_url, str):
            raise ValueError('Profile ID or URL is required and must be a string')
        
        if not isinstance(start, int) or start < 0:
            raise ValueError(f'Invalid start index: {start}. Must be non-negative integer.')
        
        if not isinstance(count, int) or count <= 0:
            raise ValueError(f'Invalid count: {count}. Must be positive integer.')
        
        # Extract profile ID from URL if needed (same as other profile endpoints)
        logger.info(f"[FETCH_USER_COMMENTS] Extracting profile ID from: {profile_id_or_url}")
        profile_id = await extract_profile_id(
            profile_input=profile_id_or_url,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        logger.info(f"[FETCH_USER_COMMENTS] Extracted profile ID: {profile_id}")
        
        # Build URL
        url = self._build_user_comments_url(profile_id, start, count)
        
        # Make the request
        data = await self._make_request(url)
        
        # Parse and return
        user_comments, _, _ = self._parse_user_comments_response(data)
        await self._augment_parent_comment_details(user_comments)
        return user_comments
