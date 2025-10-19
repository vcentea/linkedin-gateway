# LinkedIn Session Expired Error Handling

## Problem

When LinkedIn cookies expire or become invalid, the profile ID extraction fails when trying to fetch profile pages. This previously resulted in a generic 500 Internal Server Error with unclear error messages.

## Root Cause

The `extract_profile_id` utility function:
1. Extracts the vanity name from the LinkedIn profile URL
2. Calls LinkedIn's GraphQL API to get the profile ID
3. When cookies are expired/invalid, LinkedIn returns a 401/403 error or empty response
4. The function raises a `ValueError` when it cannot find the profile ID
5. This error is now properly caught and translated to a user-friendly 401 response

## Solution

Added specific error handling in all three endpoints to catch profile ID extraction failures and return a clear, actionable error message.

### Updated Endpoints

1. **POST /api/v1/connections/simple**
2. **POST /api/v1/connections/with-message**
3. **POST /api/v1/messages/send**

### Error Detection

The code now catches `ValueError` exceptions and checks if they're related to profile ID extraction:

```python
try:
    response_data = await service.method(profile_identifier)
except ValueError as e:
    # Check if it's a profile ID extraction error
    if "extract profile ID" in str(e).lower() or "could not extract" in str(e).lower():
        logger.error(f"[ENDPOINT][{mode}] LinkedIn authentication likely expired: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="LinkedIn session expired or invalid. Please refresh your LinkedIn cookies and try again."
        )
    raise  # Re-raise if it's a different ValueError
```

### Error Response

**Status Code:** `401 Unauthorized`

**Response Body:**
```json
{
    "detail": "LinkedIn session expired or invalid. Please refresh your LinkedIn cookies and try again."
}
```

### User Experience

**Before:**
```
ERROR: 500 Internal Server Error
{
    "detail": "Execution failed: Failed to extract profile ID from URL '...' "
}
```

**After:**
```
ERROR: 401 Unauthorized
{
    "detail": "LinkedIn session expired or invalid. Please refresh your LinkedIn cookies and try again."
}
```

## Testing

To test the error handling:

1. Use expired LinkedIn cookies
2. Send a connection request with a profile URL:
```bash
curl -X POST http://localhost:8000/api/v1/connections/simple \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "https://www.linkedin.com/in/john-doe",
    "api_key": "your-api-key",
    "server_call": true
  }'
```

3. Expect response:
```json
{
    "detail": "LinkedIn session expired or invalid. Please refresh your LinkedIn cookies and try again."
}
```
With status code: `401`

## Duplicate Connection Request Error

### Problem
When attempting to send a connection request to someone you've already sent a request to, LinkedIn returns:
```json
{
  "data": {
    "code": "CANT_RESEND_YET",
    "status": 400
  }
}
```

### Solution
Added specific error handling for the `CANT_RESEND_YET` error code:

**Status Code:** `409 Conflict`

**Response Body:**
```json
{
    "detail": "Connection request already sent to this profile. Please wait before sending again."
}
```

This applies to both server_call and proxy modes.

## When Errors Occur

### Session Expired (401)
- LinkedIn session cookies have expired (typically after ~1 year)
- LinkedIn cookies are invalid or corrupted
- LinkedIn has logged out the user
- Cookies were manually deleted or cleared
- User is in server_call mode (not using extension proxy)

### Duplicate Connection Request (409)
- Connection request was already sent to this profile
- LinkedIn prevents duplicate requests within a certain timeframe
- Applies to both server_call and proxy modes

## Resolution

Users need to:
1. Log in to LinkedIn in their browser
2. Copy fresh LinkedIn cookies from their browser
3. Update cookies in the application/database
4. Retry the request

## Implementation Files

- `backend/app/api/v1/connections.py` - Added error handling for both endpoints
- `backend/app/api/v1/messages.py` - Added error handling for messages endpoint
- `backend/CONNECTIONS_AND_MESSAGES_IMPLEMENTATION.md` - Updated documentation
- `backend/CONNECTIONS_API_FIX.md` - Updated documentation

## Notes

- This only applies to `server_call=True` mode (direct server execution)
- Proxy mode (`server_call=False`) uses browser cookies directly and won't have this issue
- The error is logged at ERROR level for easier debugging
- Other `ValueError` exceptions are re-raised to preserve existing error handling

