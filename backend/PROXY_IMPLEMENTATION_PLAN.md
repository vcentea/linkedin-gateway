# Proxy Implementation Plan for All Endpoints

## Current Status

### ✅ Already Implemented
- `/api/v1/feed/posts` - Feed posts endpoint with transparent HTTP proxy

### 🔄 Need Proxy Implementation

1. **Profile Endpoints** (`profiles.py`):
   - `/api/v1/profiles/scrape` - Scrape profile basic info
   - `/api/v1/profiles/experiences` - Scrape profile experiences
   - `/api/v1/profiles/recommendations` - Scrape profile recommendations

2. **Posts Endpoints** (`posts.py`):
   - `/api/v1/posts/profile-posts` - Get posts from a profile
   - `/api/v1/posts/request-feed` - Legacy feed endpoint (can be deprecated?)

3. **Comments Endpoints** (`comments.py`):
   - `/api/v1/posts/get-commenters` - Get commenters for a post

## Implementation Pattern

For each endpoint, we need to:

1. **Keep the server-side path** (`server_call=True`)
2. **Replace WebSocket path** with transparent HTTP proxy (`server_call=False`)
3. **Remove old WebSocket message sending**
4. **Use `proxy_http_request()` helper**

### Code Pattern (from feed.py)

```python
# --- SERVER-SIDE EXECUTION PATH ---
if request_data.server_call:
    logger.info(f"[ENDPOINT][SERVER_CALL] Executing on server")
    # Use LinkedIn service directly
    service = await get_linkedin_service(db, user_id, ServiceClass)
    result = await service.method(params)
    # Process result
    
# --- PROXY EXECUTION PATH (DEFAULT) ---
else:
    logger.info(f"[ENDPOINT][PROXY] Executing via HTTP proxy")
    
    # Get service to build URL and parse response
    service = await get_linkedin_service(db, user_id, ServiceClass)
    
    # Build the exact LinkedIn URL
    url = service._build_url(params)
    
    # Build headers from the service
    headers = service.headers
    
    # Execute the proxy request
    proxy_response = await proxy_http_request(
        ws_handler=ws_handler,
        user_id=user_id_str,
        url=url,
        method="GET",  # or "POST"
        headers=headers,
        body=None,  # or JSON body for POST
        response_type="json",
        include_credentials=True,
        timeout=60.0
    )
    
    # Check for HTTP errors
    if proxy_response['status_code'] >= 400:
        # Handle error
        
    # Parse the raw JSON body
    raw_json_data = json.loads(proxy_response['body'])
    result = service._parse_response(raw_json_data)
```

## Required Service Updates

For each LinkedIn service, we need:

1. **URL Builder Method**: `_build_[operation]_url(params)` - Returns the full LinkedIn API URL
2. **Response Parser Method**: `_parse_[operation]_response(data)` - Parses raw JSON response

### Example Service Structure

```python
class LinkedInProfileService(LinkedInServiceBase):
    
    def _build_profile_url(self, profile_id: str) -> str:
        """Build URL for profile scraping"""
        # Convert profile_id to URN if needed
        # Return full LinkedIn API URL
        
    def _parse_profile_response(self, data: Dict) -> Dict:
        """Parse profile API response"""
        # Extract and transform data
        # Return structured profile data
        
    async def scrape_profile(self, profile_id: str) -> Dict:
        """High-level method that uses _build and _parse"""
        url = self._build_profile_url(profile_id)
        data = await self._make_request(url)
        return self._parse_profile_response(data)
```

## Implementation Order

1. **Profile Scrape** (`/api/v1/profiles/scrape`)
   - Most important
   - Used frequently
   - Relatively simple

2. **Profile Experiences** (`/api/v1/profiles/experiences`)
   - Similar to profile scrape
   - Same service class

3. **Profile Recommendations** (`/api/v1/profiles/recommendations`)
   - Similar to profile scrape
   - Same service class

4. **Get Commenters** (`/api/v1/posts/get-commenters`)
   - Comments service
   - Different data structure

5. **Profile Posts** (`/api/v1/posts/profile-posts`)
   - Posts service
   - More complex pagination

## Benefits

- **Consistent Architecture**: All endpoints use the same proxy pattern
- **Easier Maintenance**: Single place to update LinkedIn API calls
- **Better Cookie Handling**: Browser manages cookies automatically
- **Cleaner Code**: No WebSocket message complexity
- **Easier Testing**: Test via API Tester with proxy toggle

## Testing Checklist

For each endpoint:
- [ ] Server-side mode works (`server_call=true`)
- [ ] Proxy mode works (`server_call=false`)
- [ ] Parameters are correctly extracted
- [ ] Response is correctly parsed
- [ ] Errors are properly handled
- [ ] API Tester shows correct toggle state
- [ ] No console errors in extension

