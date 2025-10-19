# WebSocket and Logout Fixes

## Issues Fixed

### 1. WebSocket Connection Broken
**Problem:** WebSocket was showing "disconnected" in the dashboard because `websocket.config.js` was trying to access properties from `appConfig` that didn't exist.

**Root Cause:** When we simplified the config files, we removed the WebSocket reconnection properties from `app.config.js` but `websocket.config.js` was still trying to access them:
- `WS_INITIAL_RECONNECT_DELAY`
- `WS_MAX_RECONNECT_DELAY`
- `WS_RECONNECT_MULTIPLIER`
- `WS_PING_INTERVAL`
- `WS_PONG_TIMEOUT`

**Fix:** Added these properties back to `app.config.js` with proper default values:
```javascript
// WebSocket reconnection settings
WS_INITIAL_RECONNECT_DELAY: 1000, // 1 second
WS_MAX_RECONNECT_DELAY: 30000, // 30 seconds
WS_RECONNECT_MULTIPLIER: 1.5,
WS_PING_INTERVAL: 30000, // 30 seconds
WS_PONG_TIMEOUT: 5000, // 5 seconds
```

### 2. Server Settings Simplified
**Problem:** User requested to simplify the server settings UI to just show the current server URL and a message to log out to change it.

**Fix:** Modified `ServerSettings.js` to:
- Remove all input fields and server selection dropdowns
- Display only the current server URL
- Show message: "To change the server, please log out first."
- Removed all event listeners and save functionality

### 3. Incomplete Logout Cleanup
**Problem:** After logout, users were being redirected back to the dashboard instead of staying on the login page, indicating incomplete session cleanup.

**Root Cause:** The `clearAuthData()` function was only clearing the standard auth keys but not all possible session-related keys that might exist in storage.

**Fix:** Enhanced `clearAuthData()` in `storage.service.js` to clear ALL auth-related keys:
```javascript
// Clear authentication tokens
await removeLocalStorage(STORAGE_KEYS.ACCESS_TOKEN);
await removeLocalStorage(STORAGE_KEYS.USER_ID);
await removeLocalStorage(STORAGE_KEYS.TOKEN_EXPIRES_AT);

// Clear additional auth-related data that might exist
await removeLocalStorage('authToken');
await removeLocalStorage('userProfile');
await removeLocalStorage('apiKey');
await removeLocalStorage('user_id');
await removeLocalStorage('token_expires_at');
```

### 4. Logout Redirect Improved
**Problem:** Users could use the back button to return to the dashboard after logout.

**Fix:** Modified `Header.js` to use `location.replace()` instead of `location.href`:
- `window.location.replace(chrome.runtime.getURL('login.html'))`
- This prevents the dashboard page from being added to browser history
- Back button will not return to the authenticated dashboard

## Files Modified

1. **chrome-extension/src-v2/shared/config/app.config.js**
   - Added WebSocket reconnection properties

2. **chrome-extension/src-v2/pages/components/dashboard/ServerSettings.js**
   - Simplified UI to display-only mode
   - Removed server selection and save functionality

3. **chrome-extension/src-v2/background/services/storage.service.js**
   - Enhanced `clearAuthData()` to clear all auth-related keys
   - Added comprehensive logging

4. **chrome-extension/src-v2/pages/components/common/Header.js**
   - Changed logout redirect to use `location.replace()`
   - Updated redirect path to use correct extension URL

## Testing Checklist

- [ ] WebSocket connection shows "connected" in dashboard
- [ ] WebSocket ping/pong mechanism working
- [ ] Server Settings card shows current server URL
- [ ] Server Settings card shows "To change the server, please log out first." message
- [ ] Logout button clears all storage
- [ ] After logout, login page is displayed
- [ ] After logout, cannot use back button to return to dashboard
- [ ] After logout, accessing dashboard URL redirects to login
- [ ] Can log in again after logout
- [ ] WebSocket reconnects after logout and login

## Notes

- Server configuration (serverType, customApiUrl) is NOT cleared on logout
- This allows users to maintain their server preference across sessions
- To change server, users must log out first (as indicated in the UI)

