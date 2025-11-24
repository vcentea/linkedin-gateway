# LinkedIn Server-Side API Call Implementation

## Overview
This document describes the implementation of server-side LinkedIn API calls, allowing the backend to directly communicate with LinkedIn's API when `server_call=true` is specified in requests.

## Implementation Status
✅ **Phase 1: LinkedIn Services Module** - COMPLETE
✅ **Phase 2: Update API Endpoints** - COMPLETE  
✅ **Phase 3: CSRF Token Retrieval** - COMPLETE

---

## Architecture

### Directory Structure
```
backend/app/
├── linkedin/
│   ├── __init__.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── base.py          # Base service with HTTP client
│   │   ├── feed.py           # Feed operations
│   │   └── comments.py       # Comment operations
│   └── utils/
│       ├── __init__.py
│       └── parsers.py        # URL parsing utilities
```

### Key Components

#### 1. **Base Service** (`linkedin/services/base.py`)
- Common HTTP client setup using `httpx`
- Standard LinkedIn API headers
- Error handling and logging
- CSRF token management

**Key Features:**
- Timeout handling (30s default)
- Automatic retry logic
- Comprehensive error logging

#### 2. **Feed Service** (`linkedin/services/feed.py`)
- Mirrors `chrome-extension/src-v2/content/linkedin/feed.js`
- `fetch_posts_from_feed(start_index, count)` method
- Extracts post details, author info, engagement metrics

**Returns:**
```python
[{
    'postId': str,
    'postUrl': str,
    'authorName': str,
    'authorProfileId': str,
    'authorJobTitle': str,
    'authorConnectionDegree': str,
    'postContent': str,
    'likes': int,
    'comments': int,
    'timestamp': str
}]
```

#### 3. **Comments Service** (`linkedin/services/comments.py`)
- Mirrors `chrome-extension/src-v2/content/linkedin/comments.js`
- `fetch_commenters_for_post(post_url, start, count, num_replies)` method
- Uses LinkedIn GraphQL API

**Returns:**
```python
[{
    'userId': str,
    'userName': str,
    'userTitle': str | None,
    'commentText': str
}]
```

#### 4. **URL Parser** (`linkedin/utils/parsers.py`)
- `parse_linkedin_post_url(post_url)` function
- Extracts URN from various LinkedIn URL formats
- Handles: `urn:li:activity:X`, `activity:X`, `activity-X`

---

## API Changes

### 1. Posts Endpoint (`/api/v1/posts/request-feed`)

**Request Schema Update:**
```python
class FeedRequest(BaseModel):
    start_index: int
    count: int
    api_key: str
    server_call: bool = False  # NEW PARAMETER
```

**Behavior:**
- `server_call=false` (default): Uses WebSocket client (existing behavior)
- `server_call=true`: Executes directly on server

**Example Request:**
```json
{
    "start_index": 0,
    "count": 10,
    "api_key": "LKG_abc123_xyz789",
    "server_call": true
}
```

### 2. Comments Endpoint (`/api/v1/posts/get-commenters`)

**Request Schema Update:**
```python
class GetCommentersRequest(BaseModel):
    post_url: str
    start: int = 0
    count: int = 10
    num_replies: int = 1
    api_key: str
    server_call: bool = False  # NEW PARAMETER
```

**Example Request:**
```json
{
    "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:123",
    "start": 0,
    "count": 10,
    "num_replies": 1,
    "api_key": "LKG_abc123_xyz789",
    "server_call": true
}
```

---

## CSRF Token Management

### New CRUD Function
**File:** `backend/app/crud/api_key.py`

```python
async def get_csrf_token_for_user(db: AsyncSession, user_id: UUID) -> Optional[str]:
    """
    Retrieve the CSRF token for a user's active API key.
    Returns None if no active key or no token stored.
    """
```

### Token Storage
- CSRF tokens are stored in `api_keys.csrf_token` column
- Updated automatically when LinkedIn status is checked on client
- Retrieved server-side when `server_call=true`

---

## Error Handling

### Client Errors (4xx)
- **400**: No CSRF token found
- **401**: Invalid API key
- **404**: WebSocket not connected (only when `server_call=false`)
- **408**: Request timeout (only when `server_call=false`)

### Server Errors (5xx)
- **500**: LinkedIn API call failed
- **503**: WebSocket service unavailable (only when `server_call=false`)

### Error Response Format
```json
{
    "detail": "Error message describing what went wrong"
}
```

---

## Execution Flow Comparison

### Client-Side Execution (`server_call=false`)
```
API Request → Backend → WebSocket → Chrome Extension → LinkedIn API → Response
```

### Server-Side Execution (`server_call=true`)
```
API Request → Backend → LinkedIn API → Response
```

---

## Logging

All server-side calls include `[SERVER_CALL]` prefix in logs:

```
[SERVER_CALL] Executing feed request on server for user {user_id}
[SERVER_CALL] Retrieved CSRF token for user {user_id}
[SERVER_CALL] Successfully fetched {count} posts from LinkedIn
[SERVER_CALL] Returning {count} processed/saved posts
```

---

## Testing

### Test Server-Side Posts
```bash
curl -X POST "http://localhost:8000/api/v1/posts/request-feed" \
  -H "Content-Type: application/json" \
  -d '{
    "start_index": 0,
    "count": 5,
    "api_key": "YOUR_API_KEY",
    "server_call": true
  }'
```

### Test Server-Side Comments
```bash
curl -X POST "http://localhost:8000/api/v1/posts/get-commenters" \
  -H "Content-Type: application/json" \
  -d '{
    "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:123",
    "api_key": "YOUR_API_KEY",
    "server_call": true
  }'
```

---

## Benefits

1. **Backward Compatible**: Default behavior unchanged (`server_call=false`)
2. **Clean Architecture**: Small, focused files mirroring client-side structure
3. **Easy to Extend**: Adding new operations follows same pattern
4. **Reduced Client Load**: Heavy operations can run on server
5. **Better Reliability**: Server has stable network connection
6. **Easier Debugging**: All logging on server side

---

## Adding New LinkedIn Operations

To add a new LinkedIn operation:

1. **Create service file**: `backend/app/linkedin/services/new_operation.py`
   - Extend `LinkedInServiceBase`
   - Implement operation methods
   - Mirror client-side JavaScript logic

2. **Update endpoint**: Add `server_call` parameter to request schema

3. **Add routing logic**:
   ```python
   if request_data.server_call:
       # Server-side execution
       csrf_token = await get_csrf_token_for_user(db, user_id)
       service = NewLinkedInService(csrf_token)
       result = await service.new_operation(...)
       return result
   else:
       # WebSocket execution (existing)
       ...
   ```

---

## Dependencies

All required dependencies are already in `requirements/base.txt`:
- `httpx==0.28.1` - HTTP client for LinkedIn API calls

---

## Next Steps

Potential enhancements:
1. Add rate limiting for server-side calls
2. Implement response caching
3. Add metrics/monitoring for LinkedIn API usage
4. Create admin dashboard for monitoring API health
5. Add retry logic with exponential backoff

---

## Files Modified/Created

### Created:
- `backend/app/linkedin/__init__.py`
- `backend/app/linkedin/services/__init__.py`
- `backend/app/linkedin/services/base.py`
- `backend/app/linkedin/services/feed.py`
- `backend/app/linkedin/services/comments.py`
- `backend/app/linkedin/utils/__init__.py`
- `backend/app/linkedin/utils/parsers.py`

### Modified:
- `backend/app/crud/api_key.py` - Added `get_csrf_token_for_user()`
- `backend/app/api/v1/posts.py` - Added `server_call` parameter and logic
- `backend/app/api/v1/comments.py` - Added `server_call` parameter and logic
- `backend/app/schemas/post.py` - Added `server_call` to request schemas

---

## Maintenance Notes

- Keep LinkedIn service methods synchronized with client-side JavaScript
- Monitor LinkedIn API changes and update accordingly
- Test both execution paths (client and server) when making changes
- Update logging if new error cases are discovered
- Document any LinkedIn API quirks or special handling needed

