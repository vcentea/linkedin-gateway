"""
Base service for LinkedIn API operations.

Provides common HTTP client setup, headers configuration,
and error handling for all LinkedIn API services.
"""
import httpx
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class LinkedInServiceBase:
    """
    Base class for LinkedIn API services.
    
    Provides common functionality for making authenticated
    requests to LinkedIn's Voyager API.
    """
    
    VOYAGER_BASE_URL = "https://www.linkedin.com/voyager/api"
    GRAPHQL_BASE_URL = "https://www.linkedin.com/voyager/api/graphql"
    TIMEOUT = 30.0  # Default timeout in seconds
    
    def __init__(self, csrf_token: str, linkedin_cookies: Optional[Dict[str, str]] = None):
        """
        Initialize the LinkedIn service with CSRF token and optional cookies.
        
        Args:
            csrf_token: The CSRF token from LinkedIn JSESSIONID cookie
            linkedin_cookies: Optional dictionary of ALL LinkedIn cookies from browser
        """
        if not csrf_token:
            raise ValueError("CSRF token is required")
        
        self.csrf_token = csrf_token
        self.linkedin_cookies = linkedin_cookies or {}
        self.headers = self._build_headers()
        
        logger.info(f"Initialized LinkedIn service with CSRF token: {csrf_token[:6]}...")
        if self.linkedin_cookies:
            logger.info(f"Using {len(self.linkedin_cookies)} LinkedIn cookies for authentication")
        else:
            logger.warning("No LinkedIn cookies provided - using CSRF token only (may fail)")
    
    def _build_headers(self) -> Dict[str, str]:
        """
        Build common headers for LinkedIn API requests.
        
        Uses all LinkedIn cookies if available, otherwise falls back to CSRF token only.
        
        Returns:
            Dictionary of HTTP headers
        """
        # Build cookie header from filtered cookies (avoid volatile ones)
        if self.linkedin_cookies and len(self.linkedin_cookies) > 0:
            # Filter cookies to avoid volatile tracking/analytics that expire quickly
            filtered_cookies = self._filter_stable_cookies(self.linkedin_cookies)
            
            cookie_parts = []
            for name, value in filtered_cookies.items():
                if name.upper() == "JSESSIONID":
                    unquoted = value.strip('"')
                    cookie_parts.append(f'{name}="{unquoted}"')
                else:
                    cookie_parts.append(f"{name}={value}")
            cookie_string = "; ".join(cookie_parts)
            logger.info(f"Built cookie header with {len(filtered_cookies)} filtered cookies (from {len(self.linkedin_cookies)} total)")
        else:
            # Fallback to CSRF token only (will likely fail LinkedIn auth)
            token_unquoted = self.csrf_token.strip('"')
            cookie_string = f'JSESSIONID="{token_unquoted}";'
            logger.warning("Using fallback CSRF-only cookie header")
        
        # Golden recipe headers (proven to work with LinkedIn API)
        return {
            # Core HTTP (standard browser behavior)
            'accept': 'application/vnd.linkedin.normalized+json+2.1',  # LinkedIn-specific format (needed for proper response structure)
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US,en;q=0.9',
            
            # LinkedIn authentication (must be current)
            'csrf-token': self.csrf_token.strip('"'),
            'x-restli-protocol-version': '2.0.0',
            
            # Browser legitimacy (static values)
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
            'sec-ch-ua': '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            
            # Security headers (key for legitimacy)
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'none',  # CRITICAL: 'none' not 'same-origin'
            
            # Cookies (filtered stable set)
            'cookie': cookie_string,
        }
    
    def _filter_stable_cookies(self, all_cookies: Dict[str, str]) -> Dict[str, str]:
        """
        Filter cookies to keep only ultra-stable ones, avoiding fast-expiring cookies.
        
        Based on systematic testing, we use ULTRA MINIMAL approach:
        - REQUIRED: li_at (auth token, ~1 year lifespan)
        - REQUIRED: JSESSIONID (session ID, hours/days lifespan)
        - OPTIONAL: liap (app flag, stable but not essential)
        
        We avoid ALL other cookies to prevent session breaks from:
        - Fast-expiring analytics (s_* cookies expire in minutes)
        - Tracking cookies (__cf_bm expires in 30min)
        - Session tokens (PLAY_SESSION, li_ep_auth_context expire quickly)
        - Even "stable" cookies like bcookie/bscookie to be ultra-safe
        
        Args:
            all_cookies: Dictionary of all browser cookies
            
        Returns:
            Dictionary with only the 2-3 most essential cookies
        """
        # ULTRA MINIMAL: Only the absolute essentials
        ultra_minimal = {'li_at', 'JSESSIONID'}
        
        # Optional: Add liap if available (LinkedIn app flag, stable)
        optional_stable = {'liap'}
        
        # Filter to ultra minimal set
        filtered = {}
        
        # Always include the absolute essentials
        for name in ultra_minimal:
            if name in all_cookies:
                filtered[name] = all_cookies[name]
        
        # Add optional stable cookies if available
        for name in optional_stable:
            if name in all_cookies:
                filtered[name] = all_cookies[name]
        
        # Log what we're filtering out (everything else)
        filtered_out = set(all_cookies.keys()) - set(filtered.keys())
        if filtered_out:
            logger.info(f"Filtered out {len(filtered_out)} potentially volatile cookies: {', '.join(sorted(filtered_out))}")
        
        # Ensure we have the absolute minimum
        if 'li_at' not in filtered:
            logger.error("CRITICAL: li_at cookie missing - authentication will fail")
        if 'JSESSIONID' not in filtered:
            logger.error("CRITICAL: JSESSIONID cookie missing - session will fail")
            
        logger.info(f"Ultra minimal cookie filtering: {len(all_cookies)} -> {len(filtered)} cookies (avoiding fast-expiring ones)")
        return filtered
    
    async def _get_ugc_post_urn_from_activity(self, activity_id: str) -> str:
        """
        Get the ugcPost URN from an activity ID using LinkedIn's GraphQL API.
        
        This is a shared utility method used by multiple services (comments, reactions, etc.)
        because some LinkedIn endpoints require ugcPost URN instead of activity URN.
        
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
    
    def _save_raw_response(self, url: str, response_data: Dict[str, Any], endpoint_type: str = "unknown"):
        """
        Save raw LinkedIn API response to disk for debugging.
        Only saves if DEBUG_LINKEDIN_RESPONSES environment variable is set to 'true'.
        
        Args:
            url: The URL that was requested
            response_data: The JSON response data
            endpoint_type: Type of endpoint (identity, contact, about_skills, etc.)
        """
        # Check if debug mode is enabled
        debug_enabled = os.getenv('DEBUG_LINKEDIN_RESPONSES', 'false').lower() == 'true'
        if not debug_enabled:
            return
        
        try:
            # Create debug directory if it doesn't exist
            debug_dir = os.path.join("backend", "debug_responses")
            os.makedirs(debug_dir, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{endpoint_type}_{timestamp}.json"
            filepath = os.path.join(debug_dir, filename)
            
            # Save response with metadata
            debug_data = {
                "timestamp": timestamp,
                "endpoint_type": endpoint_type,
                "url": url,
                "response": response_data
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[DEBUG] Saved raw response to: {filepath}")
            
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to save raw response: {e}")
    
    async def _make_request(
        self,
        url: str,
        method: str = 'GET',
        timeout: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None,
        debug_endpoint_type: str = "unknown",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request to LinkedIn API with error handling.
        
        Args:
            url: The full URL to request
            method: HTTP method (GET, POST, etc.)
            timeout: Request timeout in seconds (uses default if None)
            headers: Optional custom headers (overrides self.headers if provided)
            debug_endpoint_type: Type of endpoint for debug logging (identity, contact, etc.)
            **kwargs: Additional arguments to pass to httpx request
            
        Returns:
            JSON response data as dictionary
            
        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        timeout_value = timeout or self.TIMEOUT
        
        # Use custom headers if provided, otherwise use default headers
        request_headers = headers if headers is not None else self.headers
        
        logger.info(f"Making {method} request to LinkedIn API: {url[:100]}...")
        
        # Follow redirects and allow cookies like the browser does
        async with httpx.AsyncClient(
            timeout=timeout_value,
            follow_redirects=True
        ) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    **kwargs
                )
                
                logger.info(f"LinkedIn API response status: {response.status_code}")
                
                # Log response headers for debugging
                logger.debug(f"Response headers: {dict(response.headers)}")
                
                # Raise exception for HTTP errors
                response.raise_for_status()
                
                # Parse and return JSON
                data = response.json()
                
                # Save raw response for debugging
                self._save_raw_response(url, data, debug_endpoint_type)
                
                return data
                
            except httpx.HTTPStatusError as e:
                logger.error(f"LinkedIn API HTTP error: {e.response.status_code} - {e.response.text[:200]}")
                logger.error(f"Request headers sent: {dict(self.headers)}")
                raise
            except httpx.TimeoutException:
                logger.error(f"LinkedIn API request timed out after {timeout_value}s")
                raise
            except Exception as e:
                logger.error(f"LinkedIn API request failed: {str(e)}")
                raise

