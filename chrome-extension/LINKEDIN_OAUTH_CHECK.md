# LinkedIn OAuth Configuration Check

## Feature Overview

The extension automatically checks if LinkedIn OAuth credentials are configured on **custom servers only** and enables/disables the LinkedIn login button accordingly.

**Main/Dev servers:** LinkedIn OAuth is always assumed to be configured (no checking).
**Custom servers:** Checked every 10 seconds to detect configuration changes.

## How It Works

### Backend Endpoint

**Endpoint:** `GET /auth/linkedin/config-status`

**Response:**
```json
{
  "is_configured": true,
  "has_client_id": true,
  "has_client_secret": true,
  "setup_instructions": null
}
```

**When not configured:**
```json
{
  "is_configured": false,
  "has_client_id": false,
  "has_client_secret": false,
  "setup_instructions": "LinkedIn OAuth is not configured. Missing: LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET.\n\nTo enable LinkedIn authentication:\n1. Go to https://www.linkedin.com/developers/apps\n..."
}
```

### Frontend Behavior

#### For Main Server
- **No OAuth checking** - LinkedIn is always assumed configured
- Button is always enabled (after server health check)
- No polling occurs

#### For Custom Servers
1. **On server selection:** Immediately checks LinkedIn OAuth configuration
2. **Polling:** Checks every 10 seconds if credentials are configured
3. **Button state:** 
   - **Configured:** Button enabled, normal appearance
   - **Not configured:** Button disabled, grayed out, warning message shown
4. **When switching away from custom:** Polling stops, button re-enabled

### Visual States

#### When OAuth IS Configured ✅
- LinkedIn login button: **Enabled**
- Appearance: Normal colors, clickable
- Message: None

#### When OAuth NOT Configured ❌
- LinkedIn login button: **Disabled**
- Appearance: 50% opacity, grayscale filter, not-allowed cursor
- Message: "LinkedIn OAuth not configured on this server. Please configure LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET."

## Implementation Details

### Variables
```javascript
let linkedinConfigured = true; // Default to true, will be checked
let linkedinConfigCheckInterval = null;
```

### Functions

#### `checkLinkedInConfig()`
- Fetches `/auth/linkedin/config-status` from current server
- Updates `linkedinConfigured` variable
- Calls `updateLinkedInButtonState()` to update UI
- Has 5-second timeout
- On error: assumes configured (fail-safe approach)

#### `startLinkedInConfigPolling()`
- Sets up interval to check every 10 seconds (10000ms)
- Clears any existing interval first
- Logs polling start

#### `stopLinkedInConfigPolling()`
- Clears the polling interval
- Called on page unload to clean up

#### `updateLinkedInButtonState(isConfigured, instructions)`
- Updates button visual state:
  - **Enabled:** opacity 1, cursor pointer, no filter
  - **Disabled:** opacity 0.5, cursor not-allowed, grayscale filter
- Shows/hides warning message
- Uses `oauth-warning` class to track OAuth-specific messages

## Error Handling

### Network Errors
If the configuration check fails (network error, server down):
- **Defaults to configured** (fail-safe)
- User can still attempt to click login button
- Better UX than blocking user when server is temporarily unavailable

### Server Errors (4xx, 5xx)
If server returns error status:
- **Defaults to configured** (fail-safe)
- Logs warning but doesn't block user

## User Experience

### Scenario 1: Using Main Server
1. User selects "Main Server" (default)
2. LinkedIn button is enabled immediately (no OAuth check)
3. No polling occurs
4. User can login with LinkedIn

### Scenario 2: Custom Server Without OAuth
1. User selects "Custom Server"
2. Enters custom URL and connects
3. OAuth check starts immediately
4. Button shows disabled with warning message
5. Every 10 seconds, checks if admin configured OAuth
6. Once configured, button automatically enables

### Scenario 3: Admin Configures OAuth on Custom Server
1. User on login page with custom server selected
2. Button is disabled with warning
3. Admin adds `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` to `.env`
4. Admin restarts backend: `docker compose restart backend`
5. Within 10 seconds, extension detects configuration
6. Button automatically enables, warning disappears
7. User can now login with LinkedIn

### Scenario 4: Switching Between Servers
1. User selects "Custom Server" → OAuth checking starts
2. User switches to "Main Server" → OAuth checking stops, button enabled
3. User switches back to "Custom Server" → OAuth checking resumes

### Scenario 5: Network Issues
1. User on custom server
2. Network connectivity issues prevent check
3. Button remains enabled (fail-safe)
4. User can still attempt login
5. OAuth flow will fail naturally if credentials really aren't configured

## Testing

### Test Main Server (Default)

1. **Open extension login page**
2. **Select "Main Server"** (should be default)
3. **Observe:**
   - ✅ LinkedIn button is enabled
   - ✅ No OAuth warnings
   - ✅ No polling in console logs
   
4. **Console should NOT show:**
   - ❌ No "Checking LinkedIn OAuth config" messages
   - ❌ No OAuth-related polling

### Test Custom Server Without OAuth

1. **Select "Custom Server"**
2. **Enter your custom URL** (e.g., `https://your-server.com`)
3. **Click "Connect Server"**
4. **If OAuth not configured:**
   - ❌ LinkedIn button disabled (grayed out)
   - ⚠️ Warning message appears
   - Console logs: `LinkedIn OAuth configured: false`
   - Every 10 seconds, check runs again

### Test Custom Server With OAuth

1. **Add OAuth credentials to your custom server:**
   ```bash
   # SSH to your custom server
   # Edit deployment/.env
   LINKEDIN_CLIENT_ID=your_client_id_here
   LINKEDIN_CLIENT_SECRET=your_client_secret_here
   
   # Restart backend
   cd deployment
   docker compose restart backend
   ```

2. **In extension:**
   - Select "Custom Server"
   - Enter URL and connect
   - Within 10 seconds:
     - ✅ Button automatically enables
     - ✅ Warning disappears
     - Console logs: `LinkedIn OAuth configured: true`

### Test Server Switching

1. **Select "Custom Server"** (without OAuth)
   - Button disabled, polling starts
   
2. **Switch to "Main Server"**
   - ✅ Button immediately enabled
   - ✅ Warning disappears
   - ✅ Polling stops (check console)
   
3. **Switch back to "Custom Server"**
   - ❌ Button disabled again
   - ⚠️ Warning reappears
   - ✅ Polling resumes

### Test Real-Time Configuration

1. Open login page on custom server (OAuth not configured)
2. Observe disabled button
3. Configure OAuth in backend and restart
4. Watch button automatically enable within 10 seconds
5. No page refresh needed!

## API Endpoint Implementation

The backend endpoint checks:

```python
# Check if credentials are set and not placeholder values
has_client_id = bool(
    settings.LINKEDIN_CLIENT_ID and 
    settings.LINKEDIN_CLIENT_ID != "..." and
    len(settings.LINKEDIN_CLIENT_ID) >= 10
)

has_client_secret = bool(
    settings.LINKEDIN_CLIENT_SECRET and 
    settings.LINKEDIN_CLIENT_SECRET != "..." and
    len(settings.LINKEDIN_CLIENT_SECRET) >= 10
)

is_configured = has_client_id and has_client_secret
```

**Validation criteria:**
- Not empty
- Not placeholder `"..."`
- At least 10 characters long (reasonable minimum)

## Performance Impact

**Minimal:**
- 1 HTTP request every 10 seconds
- ~100-200ms per request (depends on network)
- Endpoint is lightweight (no database queries)
- Uses `AbortController` with 5-second timeout

**Network usage:**
- ~6 requests per minute
- ~360 requests per hour (if user stays on login page)
- Negligible bandwidth (~1KB per request)

## Cleanup

The interval is properly cleaned up:
- `beforeunload` event listener stops polling
- Prevents memory leaks
- Stops unnecessary requests when page is closed

## Future Enhancements

Potential improvements:
1. Show detailed setup instructions in UI (not just console)
2. Add a "Refresh" button to manually trigger check
3. Exponential backoff if multiple checks fail
4. Visual indicator showing "checking configuration..."
5. Link to LinkedIn Developers portal in error message

## Configuration

**Polling interval:** 10 seconds (10000ms)
- Can be adjusted by changing the interval in `startLinkedInConfigPolling()`

**Timeout:** 5 seconds
- Can be adjusted by changing timeout in `checkLinkedInConfig()`

**Fail-safe behavior:** Enabled by default
- On error, assumes OAuth is configured
- Prevents false-positive blocks due to temporary issues

