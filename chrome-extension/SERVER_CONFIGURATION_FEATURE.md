# Server Configuration Feature

## Overview
This document describes the server configuration feature that allows users to switch between different backend servers (Main/Production or Custom) for the LinkedIn Gateway extension.

## Key Design Decisions

1. **WebSocket URL Auto-Derivation**: WebSocket URLs are automatically derived from the API URL (e.g., `https://example.com` → `wss://example.com/ws`). Users only need to provide the base server URL.

2. **Main + Custom Only**: Only two server options are available:
   - **Main Server (Production)**: `https://lg.ainnovate.tech`
   - **Your Server (Custom)**: User-defined URL
   
   The development server can be added as a custom server if needed.

3. **Offline-Capable Login**: The login page is fully static and doesn't require server connectivity to load. Server health checks run in the background without blocking the UI.

## Features Implemented

### 1. **Documentation Link in Getting Started** ✅
- Added link to API documentation at `https://ainnovate.tech/lg-api-docs/`
- Located in the "Getting Started" card on the dashboard
- Opens in a new tab with proper security attributes

### 2. **Server Settings Dashboard Card** ✅
- New "Settings" card on the dashboard
- Dropdown to select server type:
  - **Main Server (Production)**: `https://lg.ainnovate.tech`
  - **Your Server (Custom)**: User-defined URL
- Custom server field for base URL (WebSocket auto-derived)
- Displays current active server
- Save button with warning about logout

### 3. **Login Page Server Selection** ✅
- Server selection dropdown added to login page
- Same two options as dashboard (Main and Custom)
- Custom URL field appears when "Your Server" is selected
- Settings are saved to localStorage when user clicks login
- Pre-populated with previously saved settings
- **Server Health Indicator**: Visual indicator showing server status (online/offline/checking)
- Login page loads fully offline - server checks run in background

### 4. **Automatic Logout on Server Change** ✅
- When user changes server settings in dashboard and clicks "Save Settings":
  - Settings are saved to localStorage
  - User is automatically logged out
  - Authentication data is cleared
  - User is redirected to login page
- This ensures clean state when switching servers

### 5. **Dynamic Configuration Loading** ✅
- `app.config.js` updated with `getServerUrls()` function
- Reads server configuration from localStorage
- Falls back to environment variables or defaults if not set
- All API and WebSocket calls use dynamic URLs
- **WebSocket URL Auto-Derivation**: `getWebSocketUrl()` function automatically converts API URL to WebSocket URL

### 6. **Manifest Permissions** ✅
- Updated `manifest.v2.json` to allow any HTTPS and WSS URLs:
  ```json
  "host_permissions": [
    "https://lgdev.ainnovate.tech/*",
    "https://lg.ainnovate.tech/*",
    "https://api2.helplink.in/*",
    "https://www.linkedin.com/*",
    "https://*/*",
    "wss://*/*"
  ]
  ```
- This allows users to connect to any custom server

### 7. **Offline-Capable Login Page** ✅
- Login page is fully static HTML/CSS/JS
- No server dependency for initial page load
- Server health check runs asynchronously in background
- Errors are handled silently - page remains functional
- Health indicator shows visual feedback without blocking UI

## Technical Implementation

### Files Modified

1. **`chrome-extension/src-v2/pages/dashboard/index.js`**
   - Added ServerSettings component import
   - Added "Settings" card with server settings container
   - Added documentation link to Getting Started card

2. **`chrome-extension/src-v2/pages/components/dashboard/ServerSettings.js`** (NEW)
   - Complete server settings component
   - Handles server selection, custom URL input, validation
   - Saves settings to localStorage
   - Implements logout and redirect on save

3. **`chrome-extension/src-v2/pages/auth/login.html`**
   - Added server selection dropdown
   - Added custom URL input fields
   - Added CSS styling for server selection UI

4. **`chrome-extension/src-v2/pages/auth/login.js`**
   - Added server selection logic
   - Loads saved settings on page load
   - Saves settings before login
   - Validates custom URLs
   - Uses dynamic server URLs for authentication

5. **`chrome-extension/src-v2/shared/config/app.config.js`**
   - Added `SERVER_CONFIGS` constant
   - Added `getServerUrls()` async function
   - Reads from localStorage with fallback to defaults
   - Exported function for use across the extension

6. **`chrome-extension/manifest.v2.json`**
   - Added wildcard host permissions for HTTPS and WSS

## Data Storage

Settings are stored in Chrome's `localStorage` with the following keys:

- `serverType`: `'MAIN'` or `'CUSTOM'`
- `customApiUrl`: Custom server URL (only if serverType is CUSTOM)

**Note**: WebSocket URL is automatically derived from `customApiUrl` using the pattern: `wss://[hostname]/ws`

## User Flow

### First Time Setup
1. User opens extension and lands on login page
2. User selects desired server (defaults to Test Server)
3. If "Your Server" is selected, user enters custom URLs
4. User clicks login button
5. Settings are saved and authentication proceeds

### Changing Server Settings (Dashboard)
1. User navigates to dashboard
2. User clicks on "Settings" card
3. User selects new server or enters custom URLs
4. User clicks "Save Settings"
5. User is logged out and redirected to login page
6. User logs in again with new server settings

### Changing Server Settings (Login Page)
1. User is on login page (not logged in)
2. User selects different server or enters custom URLs
3. User clicks login button
4. Settings are saved and authentication proceeds with new server

## Security Considerations

1. **URL Validation**: Custom URLs are validated before saving
2. **Origin Checking**: OAuth callback checks origin against configured server
3. **HTTPS Only**: Only HTTPS and WSS protocols are allowed
4. **Clean Logout**: All auth data is cleared when switching servers

## Default Behavior

- **Default Server**: Main Server (Production) - `https://lg.ainnovate.tech`
- **Fallback**: If localStorage is empty, uses environment variables from webpack build
- **Build-time Injection**: Production builds can still use webpack DefinePlugin for defaults
- **Health Check Endpoint**: `/health` endpoint on the server
- **Health Check Timeout**: 5 seconds
- **Visual Indicators**:
  - 🟠 Orange (pulsing): Checking server status
  - 🟢 Green: Server is online
  - 🔴 Red: Server is offline or unreachable

## Testing Checklist

- [ ] Login with Main Server
- [ ] Login with Custom Server (valid URL)
- [ ] Custom Server validation (invalid URL)
- [ ] Change server in dashboard → logout → redirect
- [ ] Server settings persist across extension reload
- [ ] Custom URL is saved and loaded correctly
- [ ] Documentation link opens in new tab
- [ ] All API calls use correct server URL
- [ ] WebSocket connections use correct auto-derived URL
- [ ] Login page loads when server is offline
- [ ] Health indicator shows correct status (online/offline/checking)
- [ ] Health check doesn't block login page UI
- [ ] Changing server selection triggers new health check

## Future Enhancements

1. ~~Add server health check before login~~ ✅ **Implemented**
2. ~~Show server status indicator (online/offline)~~ ✅ **Implemented**
3. Allow multiple custom server profiles (save/load presets)
4. Add server nickname/label for custom servers
5. Export/import server configurations
6. Auto-retry health check on failure
7. Show server latency/ping time

