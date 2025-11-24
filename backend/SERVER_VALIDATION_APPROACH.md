# Server Validation Approach

## Overview
This document explains how the LinkedInGateway backend validates whether it's running as the main/default production server or a custom private server.

## The Problem
We need to restrict server-side execution (`server_call=true`) to only custom private servers. The default production server should only allow proxy mode to reduce load and ensure security.

## The Solution: Self-Check Validation

### How It Works

1. **Hardcoded Main Server URL**
   - The main server URL (`https://lg.ainnovate.tech`) is hardcoded in the validation module
   - This is the same URL hardcoded in the client configuration
   - No environment variables needed!

2. **Unique Instance ID**
   - Each server instance generates a unique UUID when it starts
   - This ID is stored in memory: `SERVER_INSTANCE_ID`

3. **Self-Check Process**
   - When validation is needed, the server makes an HTTP call to: `{MAIN_SERVER_URL}/api/v1/server/instance-id`
   - The `/instance-id` endpoint returns the server's instance ID
   - If the returned ID matches our own ID, we called ourselves = we're the main server
   - If the IDs don't match or we get an error, we're a custom server

4. **Caching**
   - The result is cached to avoid repeated HTTP calls
   - The check only happens once per server lifetime

### Security Benefits

✅ **No Environment Variable Confusion**
   - No need to set `IS_DEFAULT_SERVER=false` on custom servers
   - Can't be misconfigured by mistake

✅ **Self-Verifying**
   - The server proves its identity by actually calling the main server
   - Network-level verification is harder to fake

✅ **Fail-Safe Default**
   - If the check fails (network error, etc.), assumes custom server
   - This is the safer default (allows server_call)

✅ **Simple for Custom Servers**
   - Custom servers don't need any special configuration
   - They just work™

### Implementation Details

#### Endpoints

1. **`GET /api/v1/server/instance-id`**
   - Returns: `{"instance_id": "uuid-here"}`
   - Used for the self-check validation
   - No authentication required (public endpoint)

2. **`GET /api/v1/server/info`**
   - Returns server information including restrictions
   - Automatically detects server type using self-check
   - Adjusts restrictions/announcements accordingly

#### Validation Flow

```python
async def validate_server_call_permission(server_call: bool):
    if not server_call:
        return  # No validation needed
    
    # Check if we're the main server
    is_main = await check_if_main_server()
    
    if is_main:
        raise HTTPException(403, "Server-side execution not available on main server")
```

#### Check Algorithm

```python
async def check_if_main_server() -> bool:
    # Return cached result if available
    if cache exists:
        return cache
    
    try:
        # Call the main server's instance-id endpoint
        response = GET(f"{MAIN_SERVER_URL}/api/v1/server/instance-id")
        
        if response.ok:
            remote_id = response.json()["instance_id"]
            is_main = (remote_id == SERVER_INSTANCE_ID)
            cache = is_main
            return is_main
        else:
            # Can't reach main server, assume we're custom
            cache = False
            return False
    except Exception:
        # Network error, assume we're custom
        cache = False
        return False
```

### Example Scenarios

#### Scenario 1: Main Server Startup
1. Server starts at `https://lg.ainnovate.tech`
2. Generates instance ID: `a1b2c3d4-...`
3. First request with `server_call=true` arrives
4. Server calls `https://lg.ainnovate.tech/api/v1/server/instance-id`
5. Response: `{"instance_id": "a1b2c3d4-..."}`
6. IDs match! ✓ We're the main server
7. Request is rejected with 403

#### Scenario 2: Custom Server Startup
1. Server starts at `https://my-custom-server.com`
2. Generates instance ID: `x9y8z7w6-...`
3. First request with `server_call=true` arrives
4. Server calls `https://lg.ainnovate.tech/api/v1/server/instance-id`
5. Response: `{"instance_id": "a1b2c3d4-..."}`
6. IDs don't match! ✗ We're a custom server
7. Request is allowed

#### Scenario 3: Offline/Network Issues
1. Custom server starts at `https://my-server.com`
2. First request with `server_call=true` arrives
3. Server tries to call `https://lg.ainnovate.tech/api/v1/server/instance-id`
4. Network error (timeout, DNS failure, etc.)
5. Assumes custom server (safer default)
6. Request is allowed

### Testing

To test if a server thinks it's the main server:

```bash
# On any server, check its instance ID
curl https://your-server.com/api/v1/server/instance-id

# Check if it considers itself the main server
curl https://your-server.com/api/v1/server/info | jq .is_default_server

# Try a server_call request (should fail on main, succeed on custom)
curl -X POST https://your-server.com/api/v1/feed/posts \
  -H "Content-Type: application/json" \
  -d '{"api_key": "...", "server_call": true, "start_index": 0, "count": 10}'
```

### Maintenance

**Updating the Main Server URL:**
If the main server URL changes, update it in two places:
1. `backend/app/api/v1/server_validation.py` - `MAIN_SERVER_URL`
2. `chrome-extension/src-v2/shared/config/app.config.js` - `SERVER_CONFIGS.MAIN.apiUrl`

**No other configuration needed!**

## Advantages Over Environment Variables

| Aspect | Environment Variable | Self-Check |
|--------|---------------------|------------|
| Configuration Required | Yes, on every custom server | No |
| Misconfiguration Risk | High | None |
| Verification Method | Trust the config | Actual network call |
| Default Behavior | Unsafe (allows all) | Safe (allows custom) |
| Ease of Deployment | Must set env vars | Just deploy |
| Security | Trust-based | Proof-based |

## Conclusion

The self-check approach is:
- **More secure** - Network-level proof vs configuration
- **Easier to use** - No configuration needed for custom servers
- **Fail-safe** - Safe default behavior on errors
- **Self-documenting** - The code shows exactly what it does
- **Harder to misconfigure** - No environment variables to forget

This is the recommended approach for server validation in production.

