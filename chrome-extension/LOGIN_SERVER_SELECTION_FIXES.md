# Login Server Selection and Health Check Fixes

## Issues Fixed

### 1. Main Server Shows "Online" When Offline
**Problem:** When selecting the Main server (which is currently offline), the health indicator still showed "online" and allowed login attempts.

**Root Cause:** The `handleServerSelectChange()` function was:
- Always enabling the login button for MAIN server (line 148: `updateLoginButtonState(true)`)
- Not properly waiting for health check results before enabling login

**Fix:** 
- Changed MAIN server handling to disable login button initially
- Login button is only enabled after successful health check
- Both MAIN and CUSTOM servers now follow the same health check flow

### 2. Custom Server URL Not Saved While Typing
**Problem:** When typing a custom server URL, the value was not being saved to storage until the user clicked login.

**Fix:** Added real-time saving in `handleCustomUrlInput()`:
```javascript
// Save custom URL immediately to storage
if (url) {
    chrome.storage.local.set({ customApiUrl: url }, () => {
        logger.info('Custom URL saved to storage');
    });
}
```

### 3. Custom Server URL Not Loaded When Switching Back
**Problem:** When switching from MAIN to CUSTOM and back to CUSTOM, the previously entered URL was not restored.

**Fix:** Modified `handleServerSelectChange()` to load saved custom URL:
```javascript
if (serverType === 'CUSTOM') {
    showCustomFields();
    
    // Load saved custom URL if exists
    chrome.storage.local.get(['customApiUrl'], (result) => {
        if (result.customApiUrl && customApiInput) {
            customApiInput.value = result.customApiUrl;
        }
        // ... then check health
    });
}
```

### 4. Server Type Not Saved Immediately on Selection
**Problem:** Server type was only saved when clicking login, not when selecting from dropdown.

**Fix:** 
- Added new `saveServerType()` helper function
- Called immediately in `handleServerSelectChange()` when dropdown value changes
- This ensures the selection is persisted even if user doesn't proceed to login

### 5. Login Button Enabled for Offline Main Server
**Problem:** The login button remained enabled for the Main server even when health check failed.

**Fix:** Updated `checkServerHealth()` to disable login for ALL servers when offline:
```javascript
} else {
    // Server responded but with error
    isServerOnline = false;
    // ...
    // Disable login button for ALL servers when offline
    updateLoginButtonState(false);
}
```

### 6. Login Allowed Despite Offline Server
**Problem:** `handleLoginClick()` only checked server health for CUSTOM servers.

**Fix:** Updated to check for ALL servers:
```javascript
// Check if server is online for ALL servers
if (!isServerOnline) {
    const serverType = serverSelect ? serverSelect.value : 'MAIN';
    const serverName = serverType === 'CUSTOM' ? 'Custom server' : 'Main server';
    showMessage(`Cannot login: ${serverName} is offline. Please check the server status.`, 'error');
    return;
}
```

## Behavior After Fixes

### Main Server Selection
1. User selects "Main Server (Cloud)" from dropdown
2. Server type is immediately saved to storage
3. Login button is disabled with "Checking server..." indicator
4. Health check runs against `https://lg.ainnovate.tech/health`
5. If **online**: 
   - Indicator shows green "Server is online"
   - Login button is enabled
6. If **offline**:
   - Indicator shows red "Server is offline"
   - Login button remains disabled
   - Attempting to click shows error message

### Custom Server Selection
1. User selects "Your Private Server" from dropdown
2. Server type is immediately saved to storage
3. Custom URL input field appears
4. If previously saved URL exists, it's automatically loaded
5. As user types:
   - Each keystroke saves the URL to storage (for persistence)
   - After 500ms of no typing, health check runs
6. Health check validates:
   - URL format (shows "Invalid URL format" if bad)
   - Server availability (GET request to `/health`)
7. Login button only enabled if server is online

### Switching Between Servers
- **MAIN → CUSTOM**: Custom field appears with previously saved URL (if any)
- **CUSTOM → MAIN**: Custom field hides, health check runs for main server
- **CUSTOM → CUSTOM**: Previously entered URL is preserved and restored

## Files Modified

1. **chrome-extension/src-v2/pages/auth/login.js**
   - Added `saveServerType()` helper function
   - Modified `handleServerSelectChange()` to:
     - Save server type immediately
     - Load saved custom URL when switching to CUSTOM
     - Disable login for MAIN until health check completes
   - Modified `handleCustomUrlInput()` to save URL on every keystroke
   - Modified `checkServerHealth()` to disable login for ALL servers when offline
   - Modified `handleLoginClick()` to check server health for ALL servers

## Storage Keys Used

- `serverType`: 'MAIN' or 'CUSTOM'
- `customApiUrl`: The custom server URL (e.g., 'https://my-server.com')

## Testing Checklist

### Main Server Tests
- [ ] Select Main Server → health check runs automatically
- [ ] Main server offline → shows red indicator, login disabled
- [ ] Main server online → shows green indicator, login enabled
- [ ] Cannot click login when main server is offline

### Custom Server Tests
- [ ] Select Custom Server → input field appears
- [ ] Type URL → saved to storage immediately
- [ ] Valid URL → health check runs after 500ms
- [ ] Invalid URL → shows "Invalid URL format"
- [ ] Custom server offline → shows red indicator, login disabled
- [ ] Custom server online → shows green indicator, login enabled
- [ ] Cannot click login when custom server is offline

### Persistence Tests
- [ ] Enter custom URL → switch to Main → switch back to Custom → URL is restored
- [ ] Select Main → refresh page → Main is still selected
- [ ] Select Custom with URL → refresh page → Custom is selected and URL is restored
- [ ] Type partial URL → refresh page → partial URL is restored

### Edge Cases
- [ ] Empty custom URL → login disabled, no health check
- [ ] Malformed URL → shows "Invalid URL format"
- [ ] Server timeout (5s) → shows "Server is offline"
- [ ] Server returns 500 error → shows "Server returned an error"
- [ ] Network error → shows "Server is offline"

## Technical Notes

### Debouncing
- Health checks for custom URLs are debounced by 500ms
- This prevents excessive API calls while user is typing
- Timeout is cleared and reset on each keystroke

### Health Check Endpoint
- All servers must respond to `GET /health` endpoint
- Expected response: HTTP 200 OK
- Timeout: 5 seconds
- Any non-200 response or timeout = server offline

### Storage Strategy
- Server type saved immediately on dropdown change
- Custom URL saved immediately on every keystroke
- This ensures no data loss even if user closes page without logging in

