"""
Utilities to retrieve the authenticated user's LinkedIn profile ID using
LinkedIn's GraphQL API via the meMenu signature.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

import httpx

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


