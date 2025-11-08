# Connections API Backward Compatibility Fix

## Issue
The connections endpoints were returning 422 errors because the client was sending `profile_id` but the API expected `profile_identifier`.

## Root Cause
The initial implementation used `profile_identifier` as the field name, but the existing client code (old app) uses `profile_id`.

## Solution
Updated the request models to use `profile_id` as the primary field name with backward compatibility:

### Changes Made

1. **Updated Request Models** (`backend/app/api/v1/connections.py` and `messages.py`):
   - Changed primary field name from `profile_identifier` to `profile_id`
   - Added `alias="profile_identifier"` to maintain forward compatibility
   - Added `Config` class with `populate_by_name = True` to accept both field names

2. **Field Definition Pattern**:
```python
class SimpleConnectionRequest(BaseModel):
    profile_id: str = Field(
        ..., 
        description="LinkedIn profile ID or profile URL",
        alias="profile_identifier"
    )
    api_key: str = Field(..., description="The user's full API key")
    server_call: bool = Field(False, description="If true, execute on server; if false, use proxy via extension")
    
    class Config:
        populate_by_name = True  # Allows both profile_id and profile_identifier
```

### Supported Request Formats

**Works with `profile_id` (old app format)**:
```json
{
    "profile_id": "https://www.linkedin.com/in/tania-tsoneva-cfa/",
    "api_key": "LKG_...",
    "server_call": true
}
```

**Also works with `profile_identifier` (new format)**:
```json
{
    "profile_identifier": "https://www.linkedin.com/in/tania-tsoneva-cfa/",
    "api_key": "LKG_...",
    "server_call": true
}
```

### API Key Handling
- API key is sent in the request body (not headers)
- This matches the pattern used in other endpoints (feed, profiles)
- Validated using `validate_api_key_string(request_data.api_key, db)`

### Simple Connection Request
- Does NOT require a `message` field
- Only `ConnectionWithMessageRequest` requires the `message` field
- Minimal payload:
```json
{
    "profile_id": "profile-id-or-url",
    "api_key": "your-api-key"
}
```

### Profile ID Extraction
Both endpoints support:
- Direct profile IDs: `"john-doe-123"`
- Profile URLs: `"https://www.linkedin.com/in/john-doe"`

The `extract_profile_id` utility automatically:
1. Checks if input is already a profile ID (returns as-is)
2. Extracts vanity name from URL pattern `/in/{vanity_name}`
3. Fetches the profile page and parses the profile ID from HTML

## Endpoints Updated

1. **POST /api/v1/connections/simple** - Send simple connection request
2. **POST /api/v1/connections/with-message** - Send connection request with message
3. **POST /api/v1/messages/send** - Send direct message

## Testing

```bash
# Simple connection (matches old app format)
curl -X POST http://localhost:8000/api/v1/connections/simple \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "https://www.linkedin.com/in/tania-tsoneva-cfa/",
    "api_key": "LKG_BPqOmcPRhPJkGPm4_EXOp9KQmz6ggD5DINUba-Pect2uwNjNJvEGLrF1DgN4"
  }'
```

### Response Format

**Success Response:**
```json
{
    "success": true
}
```

**Error Responses:**

*LinkedIn Session Expired (401):*
```json
{
    "detail": "LinkedIn session expired or invalid. Please refresh your LinkedIn cookies and try again."
}
```

*Duplicate Connection Request (409):*
```json
{
    "detail": "Connection request already sent to this profile. Please wait before sending again."
}
```

*Other Errors:*
Standard FastAPI error format with appropriate HTTP status codes.

## Status
✅ Fixed - API now accepts both `profile_id` and `profile_identifier` field names
✅ Backward compatible with old app
✅ Forward compatible with new naming convention
✅ Simplified response - only returns success status
✅ No breaking changes

