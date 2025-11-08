# LinkedIn API Endpoint Implementation Guide

**Based on proven patterns from Comments and Reactions endpoints**

This guide documents the essential patterns and best practices for implementing new LinkedIn API endpoints that work reliably in both server-call and proxy modes.

---

## 🎯 Core Principles

1. **Study Working Endpoints First** - Always reference `comments.py`, `reactions.py`, or `user_comments.py` as gold standards
2. **Check Base Class for Utilities** - Don't duplicate code; common functions live in `LinkedInServiceBase`
3. **URL Encoding is Critical** - LinkedIn's GraphQL API is sensitive to exact encoding
4. **Profile ID Extraction Required** - Accept URLs or IDs, always extract using `extract_profile_id` utility
5. **Manual Profile URN Encoding** - Use `urn%3Ali%3Afsd_profile%3A{id}` format, NOT `quote()` on full URN
6. **Activity → UGCPost Conversion** - Many endpoints require `ugcPost` URNs, not `activity` URNs
7. **Dual Mode Support** - Every endpoint must support both `server_call=true` and `server_call=false`
8. **Unified Response Parsing** - Same parsing logic regardless of execution mode
9. **Proper Error Handling** - Handle HTTP errors gracefully with informative messages
10. **API Path Matters** - Use `/profile/`, `/posts/`, `/users/` (plural) to avoid extension filtering

---

## 📁 File Structure Pattern

Every LinkedIn API feature needs these files:

```
backend/app/
├── linkedin/services/
│   └── {feature}.py          # Service class with URL building and parsing
├── api/v1/
│   └── {feature}.py          # FastAPI endpoint with dual-mode execution
├── schemas/
│   └── post.py               # Add request/response models
└── main.py                   # Register router
```

---

## 🔧 Service Class Implementation

### Template Structure

```python
"""LinkedIn {Feature} API service."""
from typing import List, Dict, Any, Optional
from urllib.parse import quote
import logging
import re

from .base import LinkedInServiceBase
from ..utils.parsers import parse_linkedin_post_url

logger = logging.getLogger(__name__)

class LinkedIn{Feature}Service(LinkedInServiceBase):
    """Service for LinkedIn {feature} operations."""
    
    {FEATURE}_QUERY_ID = 'voyager....'  # Get from network inspector
```

### 1. URL Building Method

**Critical Pattern:**

```python
async def _build_{feature}_url(  # NOTE: async if conversion needed!
    self,
    post_url: str,
    start: int = 0,
    count: int = 10,
    pagination_token: Optional[str] = None
) -> str:
    """Build the LinkedIn GraphQL URL."""
    
    logger.info(f"[BUILD_URL] Received post_url: {post_url}")
    
    # STEP 1: Parse post URN from URL
    post_urn = parse_linkedin_post_url(post_url)
    if not post_urn:
        raise ValueError(f'Could not parse Post URN from URL: {post_url}')
    
    logger.info(f"[BUILD_URL] Parsed post URN: {post_urn}")
    
    # STEP 2: Convert activity URN to ugcPost if needed (CRITICAL for some endpoints!)
    # This method is in the base class - DON'T duplicate it!
    if post_urn.startswith("urn:li:activity:"):
        activity_id = post_urn.split(":")[-1]
        logger.info(f"[BUILD_URL] Activity post detected, converting to ugcPost...")
        try:
            post_urn = await self._get_ugc_post_urn_from_activity(activity_id)
            logger.info(f"[BUILD_URL] Converted to ugcPost URN: {post_urn}")
        except Exception as e:
            logger.warning(f"[BUILD_URL] Could not convert: {e}")
            # Continue with activity URN (may fail for some endpoints)
    
    logger.info(f"[BUILD_URL] Using post URN: {post_urn}")
    
    # STEP 3: URL encode the URN (CRITICAL!)
    encoded_post_urn = quote(post_urn, safe='')
    
    # STEP 4: Build variables string
    variables_parts = [
        f"count:{count}",
        f"start:{start}",
        f"threadUrn:{encoded_post_urn}"  # Use encoded version!
    ]
    
    # STEP 5: Add pagination token if present
    if pagination_token:
        variables_parts.append(f"paginationToken:{pagination_token}")
        logger.info(f"[BUILD_URL] Using pagination token: {pagination_token}")
    
    # STEP 6: Join and build final URL
    variables_str = ",".join(variables_parts)
    
    url = (
        f"{self.GRAPHQL_BASE_URL}?includeWebMetadata=true&variables="
        f"({variables_str})"
        f"&queryId={self.QUERY_ID}"
    )
    
    logger.info(f"[BUILD_URL] Constructed URL: {url}")
    return url
```

**Key Requirements:**
- ✅ Always use `quote(post_urn, safe='')` to encode URNs
- ✅ Build variables as a comma-separated string
- ✅ Wrap variables in parentheses: `variables=(...)`
- ✅ Log each step for debugging
- ✅ Support pagination tokens

### 2. Response Parsing Method

**Critical Pattern:**

```python
def _parse_{feature}_response(
    self, 
    data: Dict[str, Any]
) -> tuple[List[Dict[str, Any]], Optional[str], Optional[int]]:
    """Parse LinkedIn API response."""
    
    logger.info(f"[PARSE_RESPONSE] Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    
    pagination_token = None
    total_count = None
    
    # Navigate response structure safely
    if 'data' in data and isinstance(data['data'], dict):
        data_section = data['data']
        if 'data' in data_section and isinstance(data_section['data'], dict):
            api_data = data_section['data'].get('socialDash{Feature}...', {})
            if isinstance(api_data, dict):
                # Extract pagination token
                metadata = api_data.get('metadata', {})
                if isinstance(metadata, dict):
                    pagination_token = metadata.get('paginationToken')
                
                # Extract paging info
                paging = api_data.get('paging', {})
                if isinstance(paging, dict):
                    total_count = paging.get('total', 0)
                    logger.info(f"[PARSE_RESPONSE] Paging - total: {total_count}")
    
    # Extract items from included array
    included = data.get('included', [])
    if not included:
        logger.info('[PARSE_RESPONSE] No items in included array')
        return [], pagination_token, total_count
    
    items = self._process_{feature}_batch(included)
    return items, pagination_token, total_count
```

**Key Requirements:**
- ✅ Always check `isinstance()` before accessing nested dicts
- ✅ Handle missing keys gracefully
- ✅ Return tuple with (items, pagination_token, total_count)
- ✅ Log all extraction steps

### 3. Batch Processing Method

**Critical Pattern:**

```python
def _process_{feature}_batch(
    self, 
    included_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Process batch of items from API response."""
    
    if not isinstance(included_data, list):
        logger.error('Invalid included_data: not a list')
        return []
    
    results = []
    
    # Filter for specific item type
    items = [
        item for item in included_data
        if isinstance(item, dict) and item.get('$type') == 'com.linkedin.voyager.dash.social.{Type}'
    ]
    
    logger.info(f"Found {len(items)} items (total: {len(included_data)})")
    
    for item in items:
        try:
            # Extract fields with safe navigation
            field1 = item.get('field1', {}).get('text')
            field2 = item.get('field2', {}).get('text')
            
            # Build result dict
            if field1 and field2:  # Validate required fields
                results.append({
                    'field1': field1,
                    'field2': field2 if field2 else None
                })
            else:
                logger.warning(f"Missing required fields in item")
                
        except Exception as e:
            logger.error(f"Error processing item: {str(e)}")
            continue
    
    logger.info(f"Extracted {len(results)} valid items")
    return results
```

**Key Requirements:**
- ✅ Filter by `$type` to identify correct items
- ✅ Use try/except for each item
- ✅ Validate required fields exist
- ✅ Log counts and warnings

---

## 🌐 API Endpoint Implementation

### Template Structure

```python
"""API endpoints for {feature}."""
import logging
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.post import Get{Feature}Request, Get{Feature}Response, {Item}Detail
from app.ws.events import WebSocketEventHandler
from app.db.dependencies import get_db
from app.api.dependencies import get_ws_handler
from app.auth.dependencies import validate_api_key_from_header_or_body
from app.linkedin.services.{feature} import LinkedIn{Feature}Service
from app.linkedin.helpers import get_linkedin_service, proxy_http_request
from app.core.linkedin_rate_limit import apply_pagination_delay

logger = logging.getLogger(__name__)
router = APIRouter()
```

### Critical Execution Pattern

**MUST FOLLOW EXACTLY:**

```python
@router.post("/posts/get-{feature}", response_model=Get{Feature}Response, tags=["{feature}"])
async def get_post_{feature}(
    request_body: Get{Feature}Request = Body(...),
    ws_handler: WebSocketEventHandler = Depends(get_ws_handler),
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", include_in_schema=False)
):
    """Fetch {feature} for a LinkedIn post."""
    
    # 1. VALIDATE API KEY
    requesting_user_id = await validate_api_key_from_header_or_body(
        api_key_from_body=request_body.api_key,
        api_key_header=x_api_key,
        db=db
    )
    user_id_str = str(requesting_user_id)
    
    # 2. CHECK WEBSOCKET (proxy mode only)
    if not request_body.server_call:
        if not ws_handler or user_id_str not in ws_handler.connection_manager.active_connections:
            raise HTTPException(status_code=404, detail="WebSocket not connected")
    
    # 3. SETUP
    mode = "SERVER_CALL" if request_body.server_call else "PROXY"
    service = await get_linkedin_service(db, requesting_user_id, LinkedIn{Feature}Service)
    
    all_items = []
    start_index = 0
    pagination_token = None
    batch_size = 10
    
    # 4. PAGINATION LOOP
    while True:
        # Build URL
        url = service._build_{feature}_url(
            post_url=request_body.post_url,
            start=start_index,
            count=batch_size,
            pagination_token=pagination_token
        )
        
        # 5. EXECUTE (CRITICAL PATTERN!)
        if request_body.server_call:
            # Direct server-side call
            raw_json_data = await service._make_request(url)
        else:
            # Proxy via browser extension
            proxy_response = await proxy_http_request(
                ws_handler=ws_handler,
                user_id=user_id_str,
                url=url,
                method="GET",
                headers=service.headers,  # Use service.headers!
                body=None,
                response_type="json",
                include_credentials=True,
                timeout=60.0
            )
            
            # Check for errors
            if proxy_response['status_code'] >= 400:
                if all_items:
                    break  # Return what we have
                raise HTTPException(status_code=502, detail=f"LinkedIn API error: {proxy_response['status_code']}")
            
            # Parse JSON from proxy response
            raw_json_data = json.loads(proxy_response['body'])
        
        # 6. PARSE RESPONSE (unified)
        items, pagination_token, total = service._parse_{feature}_response(raw_json_data)
        
        if not items:
            break
        
        all_items.extend(items)
        start_index += batch_size
        
        if not pagination_token:
            break
        
        # 7. RATE LIMIT DELAY
        await apply_pagination_delay(
            min_delay=request_body.min_delay,
            max_delay=request_body.max_delay,
            operation_name=f"{feature.upper()}-{mode}"
        )
    
    # 8. VALIDATE AND RETURN
    validated_items = [{Item}Detail(**item) for item in all_items]
    return Get{Feature}Response(data=validated_items)
```

**Critical Requirements:**

### ✅ Proxy Function Call Pattern

**THIS IS THE CORRECT SIGNATURE - DO NOT DEVIATE:**

```python
proxy_response = await proxy_http_request(
    ws_handler=ws_handler,
    user_id=user_id_str,
    url=url,                          # NOT request_payload!
    method="GET",
    headers=service.headers,          # Use service.headers
    body=None,
    response_type="json",
    include_credentials=True,
    timeout=60.0
)
```

**Common Mistakes to Avoid:**
- ❌ Using `request_payload` parameter (doesn't exist!)
- ❌ Using `service._build_headers()` instead of `service.headers`
- ❌ Passing timeout without other required params
- ❌ Not parsing `proxy_response['body']` as JSON

### ✅ Response Handling Pattern

```python
# Check status
if proxy_response['status_code'] >= 400:
    error_msg = f"LinkedIn API returned status {proxy_response['status_code']}"
    if all_items:
        logger.warning(f"Returning {len(all_items)} items collected before error")
        break
    raise HTTPException(status_code=502, detail=error_msg)

# Parse body
raw_json_data = json.loads(proxy_response['body'])
```

---

## 📋 Schema Implementation

### Request Model

```python
class Get{Feature}Request(BaseModel):
    """Request model for fetching {feature}."""
    post_url: str = Field(..., description="The full URL of the LinkedIn post.")
    count: int = Field(-1, description="Number to fetch. Use -1 for all.")
    api_key: Optional[str] = Field(default=None, description="API key (optional if via header)")
    server_call: bool = Field(False, description="If true, execute on server")
    min_delay: Optional[float] = Field(2.0, ge=0, le=30, description="Min delay between requests")
    max_delay: Optional[float] = Field(5.0, ge=0, le=60, description="Max delay between requests")
```

### Response Model

```python
class {Item}Detail(BaseModel):
    """Detail about an individual {item}."""
    userId: str = Field(..., description="Unique ID")
    userName: str = Field(..., description="Full name")
    userTitle: Optional[str] = Field(None, description="Job title/headline")
    connectionLevel: Optional[str] = Field(None, description="Connection level (1st, 2nd, 3rd+)")

class Get{Feature}Response(BaseModel):
    """Response model."""
    data: List[{Item}Detail] = Field(..., description="List of {items}")
```

---

## 🔍 Debugging Checklist

When endpoint fails with 400/500 errors:

1. **URL Encoding**
   - [ ] Is the URN properly encoded with `quote(urn, safe='')`?
   - [ ] Are colons encoded as `%3A`?
   - [ ] Check the constructed URL in logs

2. **Proxy Function Call**
   - [ ] Using correct parameter names (`url`, not `request_payload`)?
   - [ ] Using `service.headers` not `service._build_headers()`?
   - [ ] Parsing `proxy_response['body']` as JSON?

3. **Response Parsing**
   - [ ] Checking `isinstance()` before accessing dicts?
   - [ ] Using correct path to data (check response structure)?
   - [ ] Handling missing keys gracefully?

4. **Pagination**
   - [ ] Incrementing `start_index` by batch size?
   - [ ] Checking for empty results to break loop?
   - [ ] Checking for missing pagination token?

---

## 🎓 Key Lessons Learned

### From Comments Implementation
1. URL encoding is non-negotiable for LinkedIn GraphQL
2. SocialDetail objects contain parent/child relationships
3. Replies need special handling via permalink analysis
4. Total count only appears in first response

### From Reactions Implementation
1. Different query IDs but same URL structure pattern
2. `includeWebMetadata=true` parameter needed
3. Simple `threadUrn` instead of wrapped `socialDetailUrn`
4. Reaction type comes from `$type` filtering
5. **CRITICAL:** Reactions endpoint requires `ugcPost` URN, not `activity` URN
6. Must convert activity URLs to ugcPost URNs using `_get_ugc_post_urn_from_activity()`

### Activity-to-UGCPost Conversion (CRITICAL!)
Many LinkedIn endpoints (comments, reactions) **only work with ugcPost URNs**, not activity URNs:

```python
# Check if conversion is needed
if post_urn.startswith("urn:li:activity:"):
    activity_id = post_urn.split(":")[-1]
    post_urn = await self._get_ugc_post_urn_from_activity(activity_id)
```

This method is now in the **base class** (`LinkedInServiceBase`) - don't duplicate it!

### Code Deduplication
- Common functions belong in `LinkedInServiceBase`
- Don't duplicate utility methods across services
- Check base class before implementing new helper methods
- Example: `_get_ugc_post_urn_from_activity` is shared by all services

### General Best Practices
1. Always study working endpoint first (use `comments.py` as reference)
2. Check base class for existing utility methods before creating new ones
3. Log extensively during development (URL construction, URN conversion, etc.)
4. Test both server_call and proxy modes
5. Handle pagination gracefully with configurable delays
6. Return partial results on errors if possible
7. Use proper type hints and validation
8. Make URL building methods `async` if they need to convert URNs

---

## 🎓 Critical Lessons Learned

### Profile ID Handling (User Comments Endpoint)

**Problem:** Passing profile URLs directly to LinkedIn API causes 400 errors.

**Solution:** Always extract profile ID from URL first using the utility function.

```python
from app.linkedin.utils.profile_id_extractor import extract_profile_id

# In service class
profile_id = await extract_profile_id(
    profile_input=profile_id_or_url,
    headers=self.headers,
    timeout=self.TIMEOUT
)
```

**Key Points:**
- Accept BOTH profile URLs (`https://www.linkedin.com/in/username/`) AND profile IDs (`ACoAABkVEvg...`)
- Always call `extract_profile_id` before building API URLs
- Use correct function signature: `profile_input`, `headers`, `timeout`
- Update schema descriptions to indicate both formats are accepted

### Profile URN Encoding

**Problem:** Using `quote()` on full URN string causes malformed requests.

**Wrong:**
```python
profile_urn = f"urn:li:fsd_profile:{profile_id}"
encoded_profile_urn = quote(profile_urn, safe='')  # ❌ Wrong!
```

**Correct:**
```python
# Manually encode colons like other profile endpoints
encoded_profile_urn = f"urn%3Ali%3Afsd_profile%3A{profile_id}"  # ✅ Correct!
```

**Why:** LinkedIn expects colons to be encoded as `%3A` within the variables string, but the overall structure must remain intact. Double-encoding or wrong encoding breaks the request.

### Pagination Token Encoding

**Pagination tokens often contain `=` signs that MUST be URL-encoded:**

```python
if pagination_token:
    encoded_token = quote(pagination_token, safe='')
    variables_parts.append(f"paginationToken:{encoded_token}")
```

### Parameter Order Matters

**Always match the exact parameter order from working example URLs:**

```python
# Example from user comments endpoint - order must match LinkedIn's expectation
variables_parts = [
    f"count:{count}",
    f"start:{start}",
    f"profileUrn:{encoded_profile_urn}"
]
# Then optionally add paginationToken
```

**Why:** While not always required, maintaining LinkedIn's expected order reduces risk of edge cases.

### API Path and Extension Filtering

**Problem:** Endpoint not appearing in Chrome Extension's API tester.

**Cause:** The extension filters paths to show only relevant endpoints:
- ❌ Blocks: `/api/v1/user/*` (singular "user" for management endpoints)
- ✅ Allows: `/api/v1/users/*` (plural) or `/api/v1/profile/*`

**Solution:** Use appropriate path prefixes:
- Profile-related endpoints: `/api/v1/profile/{action}`
- Post-related endpoints: `/api/v1/posts/{action}`
- User data endpoints: `/api/v1/users/{action}` (plural)

**Example:**
```python
@router.post("/profile/comments", ...)  # ✅ Good - appears in extension
@router.post("/user/comments", ...)     # ❌ Bad - filtered out
```

### Sideloaded Response Parsing

**Pattern for LinkedIn's "sideloaded" API responses:**

1. **Build lookup maps first:**
```python
def _build_lookup_maps(self, included: List[Dict[str, Any]]) -> tuple[Dict, Dict, Dict]:
    update_map = {}
    comment_map_by_entity_urn = {}
    comment_map_by_urn = {}
    
    for item in included:
        item_type = item.get('$type', '')
        if item_type == 'com.linkedin.voyager.dash.feed.Update':
            update_map[item.get('entityUrn')] = item
        elif item_type == 'com.linkedin.voyager.dash.social.Comment':
            comment_map_by_entity_urn[item.get('entityUrn')] = item
            comment_map_by_urn[item.get('urn')] = item
    
    return update_map, comment_map_by_entity_urn, comment_map_by_urn
```

2. **Then iterate through elements and use maps for lookups**

3. **Check text indicators to determine scenarios** (e.g., "commented on" vs "replied to")

---

## 📝 Checklist for New Endpoint

### Before Implementation
- [ ] Study `comments.py` as reference
- [ ] Check `LinkedInServiceBase` for existing utility methods
- [ ] Identify which LinkedIn GraphQL endpoint to use
- [ ] Test endpoint URL in browser network tab
- [ ] Identify response structure and data paths

### Service Implementation
- [ ] Service class created in `linkedin/services/`
- [ ] Inherits from `LinkedInServiceBase`
- [ ] Profile ID extraction added if endpoint accepts profile URLs (use `extract_profile_id` from utils)
- [ ] URL building uses correct encoding (manual for profile URNs: `urn%3Ali%3Afsd_profile%3A{id}`)
- [ ] Pagination token encoding uses `quote(token, safe='')` if present
- [ ] Activity-to-ugcPost conversion added if needed (use base class method!)
- [ ] URL building method is `async` if it calls conversion or profile extraction
- [ ] Response parsing handles nested structures safely
- [ ] Batch processing filters by correct `$type`
- [ ] No duplicate code from other services

### API Endpoint Implementation
- [ ] API endpoint created in `api/v1/`
- [ ] Supports both execution modes (server_call and proxy)
- [ ] Proxy call uses correct function signature
- [ ] URL building awaited properly (if async)
- [ ] Pagination implemented correctly
- [ ] Error handling returns informative messages
- [ ] Logging added for debugging

### Integration
- [ ] Schemas defined in `post.py`
- [ ] Router registered in `main.py`
- [ ] Imports added correctly

### Testing & Documentation
- [ ] Tested with real LinkedIn session (both modes)
- [ ] Tested with activity and ugcPost URLs
- [ ] Tested pagination
- [ ] Documentation updated
- [ ] No linter errors

---

## 🚀 Quick Reference

**Working Example URLs:**

Comments:
```
{GRAPHQL_BASE_URL}?variables=(count:10,numReplies:1,socialDetailUrn:urn%3Ali%3Afsd_socialDetail%3A%28urn%3Ali%3AugcPost%3A123%2Curn%3Ali%3AugcPost%3A123%2Curn%3Ali%3AhighlightedReply%3A-%29,sortOrder:RELEVANCE,start:0)&queryId=voyagerSocialDashComments.95ed44bc87596acce7c460c70934d0ff
```

Reactions:
```
{GRAPHQL_BASE_URL}?includeWebMetadata=true&variables=(count:10,start:0,threadUrn:urn%3Ali%3AugcPost%3A123)&queryId=voyagerSocialDashReactions.41ebf31a9f4c4a84e35a49d5abc9010b
```

User Comments:
```
{GRAPHQL_BASE_URL}?variables=(count:20,start:0,profileUrn:urn%3Ali%3Afsd_profile%3AACoAABkVEvg...)&queryId=voyagerFeedDashProfileUpdates.8f05a4e5ad12d9cb2b56eaa22afbcab9
```

**Key Differences to Note:**
- Comments: `socialDetailUrn` with triple URN wrapper
- Reactions: `threadUrn` with single URN (ugcPost)
- User Comments: `profileUrn` with manually encoded profile URN
- Comments: `sortOrder:RELEVANCE` parameter
- Reactions: `includeWebMetadata=true` parameter
- User Comments: Uses sideloaded response pattern with lookup maps

---

## 📚 Reference Files

### Gold Standards
- **Post Comments (Classic):** `backend/app/api/v1/comments.py` + `backend/app/linkedin/services/comments.py`
- **Post Reactions:** `backend/app/api/v1/reactions.py` + `backend/app/linkedin/services/reactions.py`
- **User Comments (Sideloaded):** `backend/app/api/v1/user_comments.py` + `backend/app/linkedin/services/user_comments.py`

### Utilities
- **Proxy Helper:** `backend/app/linkedin/helpers.py`
- **Profile ID Extractor:** `backend/app/linkedin/utils/profile_id_extractor.py`
- **Base Service:** `backend/app/linkedin/services/base.py`
- **Schemas:** `backend/app/schemas/post.py`

---

**Remember:** When in doubt, copy the exact pattern from working endpoints and adapt it. Don't innovate on the core structure - it's proven to work!

**For profile-related endpoints:** Always use `extract_profile_id` utility and follow the pattern from `user_comments.py`.

