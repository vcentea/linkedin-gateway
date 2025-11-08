"""
Utilities to retrieve the authenticated user's LinkedIn profile ID using
LinkedIn's GraphQL API via the meMenu signature.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _find_authenticated_user_urn(json_data: Dict[str, Any]) -> Optional[str]:
    """
    Locate the authenticated user's URN by finding the meMenu.*profile field.

    Returns the full URN (e.g., "urn:li:fsd_profile:<PROFILE_ID>") or None.
    """
    try:
        primary_items = (
            json_data["data"]["data"]["feedDashGlobalNavs"]["primaryItems"]
        )
        for nav_item in primary_items:
            me_menu = nav_item.get("meMenu")
            if me_menu:
                user_urn = me_menu.get("*profile")
                if user_urn:
                    return user_urn
    except (KeyError, TypeError):
        return None
    return None


async def get_my_profile_id_via_service(service_like) -> str:
    """
    Centralized wrapper to fetch profile ID via a given LinkedInServiceBase-like object.
    The object must expose: GRAPHQL_BASE_URL, _make_request(), and logging-compatible headers.
    """
    url = (
        f"{service_like.GRAPHQL_BASE_URL}"
        f"?includeWebMetadata=true&variables=()"
        f"&queryId=voyagerFeedDashGlobalNavs.998834f8daa4cbca25417843e04f16b1"
    )
    logger.info("Fetching authenticated user's profile ID via GraphQL meMenu (service)")
    data = await service_like._make_request(url)

    user_urn = _find_authenticated_user_urn(data) or ''
    match = re.search(r"urn:li:fsd_profile:([A-Za-z0-9_-]+)", user_urn)
    if not match:
        raise ValueError("Could not locate meMenu.*profile URN in GraphQL response")
    profile_id = match.group(1)
    logger.info(f"Retrieved authenticated user's profile ID: {profile_id}")
    return profile_id


async def get_my_profile_id_with_fallbacks(
    db: AsyncSession,
    user_id: UUID,
    service,
    ws_handler=None,
    use_proxy: bool = False
) -> str:
    """
    Get authenticated user's profile ID using robust method with fallbacks.

    This is the SOLID implementation extracted from /my-id endpoint.
    It includes:
    - Cache check
    - Method 2: voyagerFeedDashGlobalNavs with recursive Profile type search
    - Method 3: voyagerIdentityDashProfiles fallback
    - Session refresh on 401/403/302
    - Auto-caching on success

    Args:
        db: Database session
        user_id: User UUID
        service: LinkedInServiceBase instance
        ws_handler: WebSocket handler (required if use_proxy=True)
        use_proxy: If True, use proxy mode via browser extension

    Returns:
        The authenticated user's LinkedIn profile ID

    Raises:
        ValueError: If profile ID cannot be extracted after all methods
    """
    from app.linkedin.utils.my_profile_id_cache import (
        get_cached_my_profile_id,
        set_cached_my_profile_id,
    )

    mode = "PROXY" if use_proxy else "SERVER_CALL"
    user_id_str = str(user_id)

    # First: try cache
    cached_id = await get_cached_my_profile_id(db, user_id)
    if cached_id:
        logger.info(f"[MY_PROFILE_ID][{mode}] ✓ Returning cached profile ID: {cached_id}")
        return cached_id

    logger.info(f"[MY_PROFILE_ID][{mode}] No cached profile ID, attempting to fetch from LinkedIn...")

    # Method 2: Try voyagerFeedDashGlobalNavs GraphQL endpoint
    graphql_url = (
        f"{service.GRAPHQL_BASE_URL}"
        f"?includeWebMetadata=true&variables=()"
        f"&queryId=voyagerFeedDashGlobalNavs.998834f8daa4cbca25417843e04f16b1"
    )
    logger.info(f"[MY_PROFILE_ID][{mode}] Method 2: Trying voyagerFeedDashGlobalNavs endpoint")

    try:
        for attempt in range(2):
            if not use_proxy:
                # SERVER_CALL mode
                headers = {
                    **service.headers,
                    'Referer': 'https://www.linkedin.com/feed/',
                    'x-li-lang': 'en_US',
                    'x-li-track': '{"clientVersion":"1.13.0"}',
                }
                response_data = await service._make_request(
                    url=graphql_url,
                    method='GET',
                    headers=headers
                )
            else:
                # PROXY mode
                from app.linkedin.helpers import proxy_http_request, refresh_linkedin_session
                headers = {
                    **service.headers,
                    'Referer': 'https://www.linkedin.com/feed/',
                    'x-li-lang': 'en_US',
                    'x-li-track': '{"clientVersion":"1.13.0"}',
                }
                headers.pop('cookie', None)
                proxy_response = await proxy_http_request(
                    ws_handler=ws_handler,
                    user_id=user_id_str,
                    url=graphql_url,
                    method="GET",
                    headers=headers,
                    response_type="json",
                    include_credentials=True,
                    timeout=60.0,
                instance_id=api_key.instance_id  # Route to correct browser instance
                )
                if proxy_response['status_code'] >= 400:
                    if proxy_response['status_code'] in (401, 403, 302) and attempt == 0:
                        logger.warning(f"[MY_PROFILE_ID][{mode}] {proxy_response['status_code']} -> refreshing session and retrying")
                        await refresh_linkedin_session(ws_handler, db, api_key)
                        # Re-get service with refreshed cookies
                        from app.linkedin.helpers import get_linkedin_service
                        from app.linkedin.services.messages import LinkedInMessageService
                        service = await get_linkedin_service(db, user_id, LinkedInMessageService)
                        continue
                    raise ValueError(f"LinkedIn API returned status {proxy_response['status_code']}")
                response_data = json.loads(proxy_response['body'])

            # Recursively search for Profile type and extract entityUrn
            def find_profile_urn(obj, depth=0):
                """Recursively search for com.linkedin.voyager.dash.identity.profile.Profile type"""
                if depth > 20:  # Prevent infinite recursion
                    return None

                if isinstance(obj, dict):
                    # Check if this object is a Profile type
                    obj_type = obj.get('_type') or obj.get('$type')
                    if obj_type in ['com.linkedin.voyager.dash.identity.profile.Profile',
                                   'com.linkedin.voyager.identity.profile.Profile']:
                        entity_urn = obj.get('entityUrn')
                        if entity_urn:
                            logger.debug(f"[MY_PROFILE_ID][{mode}] Found Profile type at depth {depth}")
                            return entity_urn

                    # Recursively search all dict values
                    for key, value in obj.items():
                        result = find_profile_urn(value, depth + 1)
                        if result:
                            return result

                elif isinstance(obj, list):
                    # Recursively search all list items
                    for item in obj:
                        result = find_profile_urn(item, depth + 1)
                        if result:
                            return result

                return None

            try:
                entity_urn = find_profile_urn(response_data)

                if entity_urn:
                    m = re.search(r'urn:li:fsd_profile:([A-Za-z0-9_-]+)', entity_urn)
                    if m:
                        profile_id = m.group(1)
                        logger.info(f"[MY_PROFILE_ID][{mode}] ✓ Method 2 SUCCESS: {profile_id}")
                        # Save to cache
                        await set_cached_my_profile_id(db, user_id, profile_id)
                        return profile_id
                    else:
                        logger.warning(f"[MY_PROFILE_ID][{mode}] Found entityUrn but regex match failed")
                else:
                    logger.warning(f"[MY_PROFILE_ID][{mode}] Method 2 failed: No Profile type found")

            except Exception as parse_err:
                logger.error(f"[MY_PROFILE_ID][{mode}] Method 2 parse error: {parse_err}", exc_info=True)

        # Method 3: Try voyagerIdentityDashProfiles endpoint (fallback)
        logger.info(f"[MY_PROFILE_ID][{mode}] Method 3: Trying voyagerIdentityDashProfiles endpoint...")
        try:
            identity_url = (
                f"{service.GRAPHQL_BASE_URL}"
                f"?variables=(count:1)"
                f"&queryId=voyagerIdentityDashProfiles.4d88ce24d04a54f7dd0542ea529a69d0"
            )

            if not use_proxy:
                headers = {**service.headers, 'Referer': 'https://www.linkedin.com/feed/'}
                identity_response = await service._make_request(url=identity_url, method='GET', headers=headers)
            else:
                from app.linkedin.helpers import proxy_http_request
                headers = {**service.headers, 'Referer': 'https://www.linkedin.com/feed/'}
                headers.pop('cookie', None)
                proxy_resp = await proxy_http_request(
                    ws_handler=ws_handler, user_id=user_id_str, url=identity_url, method="GET",
                    headers=headers, response_type="json", include_credentials=True, timeout=60.0,
                instance_id=api_key.instance_id  # Route to correct browser instance
                )
                if proxy_resp['status_code'] >= 400:
                    logger.warning(f"[MY_PROFILE_ID][{mode}] Method 3: Proxy returned {proxy_resp['status_code']}")
                    identity_response = None
                else:
                    identity_response = json.loads(proxy_resp['body'])

            # Try to extract profile ID from identity response using same recursive approach
            if identity_response:
                entity_urn = find_profile_urn(identity_response)

                if entity_urn:
                    m = re.search(r'urn:li:fsd_profile:([A-Za-z0-9_-]+)', entity_urn)
                    if m:
                        profile_id = m.group(1)
                        logger.info(f"[MY_PROFILE_ID][{mode}] ✓ Method 3 SUCCESS: {profile_id}")
                        await set_cached_my_profile_id(db, user_id, profile_id)
                        return profile_id
                    else:
                        logger.warning(f"[MY_PROFILE_ID][{mode}] Method 3: Entity URN found but regex failed")
                else:
                    logger.warning(f"[MY_PROFILE_ID][{mode}] Method 3: No Profile type found")
        except Exception as identity_err:
            logger.error(f"[MY_PROFILE_ID][{mode}] Method 3 error: {identity_err}", exc_info=True)

        logger.error(f"[MY_PROFILE_ID][{mode}] ✗ All methods failed to retrieve profile ID")
        raise ValueError("Could not retrieve profile ID. Please ensure LinkedIn session is valid and try again.")

    except ValueError:
        raise
    except Exception as e:
        logger.exception(f"[MY_PROFILE_ID][{mode}] Unexpected error: {e}")
        raise ValueError(f"Failed to retrieve profile ID: {str(e)}")


