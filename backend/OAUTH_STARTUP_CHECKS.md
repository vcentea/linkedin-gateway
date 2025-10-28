# OAuth Startup Checks Documentation

## Overview

The backend server now performs comprehensive OAuth configuration checks on startup and displays important setup information.

## Startup Checks

### 1. LinkedIn OAuth Credentials Validation

When the server starts, it checks for the following environment variables:
- `LINKEDIN_CLIENT_ID`
- `LINKEDIN_CLIENT_SECRET`

### 2. Missing Credentials Warning

If credentials are missing or set to placeholder values (`"..."`), you'll see:

```
⚠️  WARNING: Missing LinkedIn OAuth Credentials!
================================================================================
The following environment variables are not set in your .env file:
  ❌ LINKEDIN_CLIENT_ID
  ❌ LINKEDIN_CLIENT_SECRET

Please add them to your backend/.env file:
  LINKEDIN_CLIENT_ID=your_client_id_here
  LINKEDIN_CLIENT_SECRET=your_client_secret_here

Get your credentials from: https://www.linkedin.com/developers/apps
================================================================================
```

### 3. OAuth Callback URL Display

The server displays the callback URL that must be configured in LinkedIn Developer Portal:

```
📋 LinkedIn OAuth Configuration
================================================================================
Callback URL (Redirect URI): http://localhost:8000/auth/user/callback

⚙️  Add this URL to your LinkedIn Developer App:
   1. Go to: https://www.linkedin.com/developers/apps
   2. Select your app
   3. Go to 'Auth' tab
   4. Add this URL to 'Authorized redirect URLs for your app':
      http://localhost:8000/auth/user/callback

💡 For production, update this to your production domain:
      https://lg.ainnovate.tech/auth/user/callback
================================================================================
```

### 4. API Information

The server also displays where the API is accessible:

```
🌐 API will be available at: http://0.0.0.0:8000
📖 API Documentation: http://localhost:8000/docs
🔍 Health Check: http://localhost:8000/health
================================================================================
```

## Configuration

### Environment Variables

The OAuth configuration is loaded from `backend/.env`:

```env
# LinkedIn OAuth
LINKEDIN_CLIENT_ID=your_client_id_here
LINKEDIN_CLIENT_SECRET=your_client_secret_here

# Public URL Configuration (REQUIRED for LinkedIn OAuth)
PUBLIC_URL=https://your-domain-or-tunnel-url.com
BEHIND_PROXY=true
TUNNEL_SERVICE=cloudflare  # or ngrok, nginx, etc.
```

### ⚠️ HTTPS Requirement

**LinkedIn OAuth REQUIRES HTTPS for callback URLs.**

If you see a red warning on startup about HTTP, you MUST set up HTTPS using one of these methods:
- Cloudflare Tunnel (recommended, free)
- Ngrok
- Nginx with Let's Encrypt
- Cloud deployment

**📖 See [HTTPS_TUNNELING_GUIDE.md](./HTTPS_TUNNELING_GUIDE.md) for detailed setup instructions.**

### Default Values

The callback route is defined in `backend/app/auth/routes.py` at line 31:
```python
@router.get("/user/callback", name="user_callback_linkedin", tags=["Authentication"])
```

This means the full callback URL is: `{BASE_URL}/auth/user/callback`

### Production Configuration

For production deployments, the callback URL will be:

```
https://lg.ainnovate.tech/auth/user/callback
```

Or for development server:

```
https://lgdev.ainnovate.tech/auth/user/callback
```

**Note:** The `LINKEDIN_REDIRECT_URI` setting in `.env` is not actually used by the current implementation. The callback URL is dynamically generated using FastAPI's `request.url_for('user_callback_linkedin')` method.

## Setting Up LinkedIn OAuth

### Step 1: Create LinkedIn App

1. Go to [LinkedIn Developers](https://www.linkedin.com/developers/apps)
2. Click "Create app"
3. Fill in required information:
   - App name
   - LinkedIn Page (company page)
   - Privacy policy URL
   - App logo
4. Click "Create app"

### Step 2: Get Credentials

1. In your app dashboard, go to "Auth" tab
2. Copy your **Client ID**
3. Copy your **Client Secret**
4. Add these to `backend/.env`:
   ```env
   LINKEDIN_CLIENT_ID=<your_client_id>
   LINKEDIN_CLIENT_SECRET=<your_client_secret>
   ```

### Step 3: Configure Redirect URIs

1. In the "Auth" tab, scroll to "Authorized redirect URLs for your app"
2. Click "Add redirect URL"
3. Add the callback URL shown in your server startup logs
4. For local development: `http://localhost:8000/auth/user/callback`
5. For production: `https://lg.ainnovate.tech/auth/user/callback`
6. Click "Update"

### Step 4: Request API Access

1. In the "Products" tab, request access to:
   - **Sign In with LinkedIn** (required for OAuth)
   - Other LinkedIn APIs as needed
2. Wait for approval (usually instant for Sign In with LinkedIn)

## Verification

### Test OAuth Flow

1. Start your backend server:
   ```bash
   cd backend
   python main.py
   ```

2. Check startup logs for confirmation:
   ```
   ✅ LinkedIn OAuth Credentials: Configured
   ```

3. Open your browser to:
   ```
   http://localhost:8000/auth/login/linkedin
   ```

4. You should be redirected to LinkedIn's login page
5. After login, you'll be redirected back to your callback URL

### Common Issues

#### Issue: "redirect_uri_mismatch"
**Cause**: The redirect URI in your code doesn't match what's configured in LinkedIn Developer Portal

**Solution**: 
1. Check the startup logs for the exact callback URL
2. Ensure it's added to LinkedIn Developer Portal
3. Check for trailing slashes (should match exactly)
4. Verify protocol (http vs https)

#### Issue: "invalid_client_id"
**Cause**: Client ID is incorrect or not set

**Solution**:
1. Verify `LINKEDIN_CLIENT_ID` in `.env` matches your LinkedIn app
2. Check for extra spaces or quotes
3. Restart the server after updating `.env`

#### Issue: "invalid_client_secret"
**Cause**: Client Secret is incorrect

**Solution**:
1. Verify `LINKEDIN_CLIENT_SECRET` in `.env`
2. Regenerate secret in LinkedIn Developer Portal if needed
3. Update `.env` and restart server

## File Structure

```
backend/
├── .env                          # Environment variables (OAuth credentials)
├── main.py                       # Startup checks implemented here
└── app/
    ├── core/
    │   └── config.py            # Settings class with OAuth config
    └── auth/
        └── routes.py            # OAuth login/callback endpoints
```

## Implementation Details

### Startup Event Handler

The startup checks are implemented in `backend/main.py`:

```python
@app.on_event("startup")
async def startup_event():
    """
    Startup event handler - display important configuration information.
    """
    # Check credentials
    missing_credentials = []
    if not settings.LINKEDIN_CLIENT_ID or settings.LINKEDIN_CLIENT_ID == "...":
        missing_credentials.append("LINKEDIN_CLIENT_ID")
    if not settings.LINKEDIN_CLIENT_SECRET or settings.LINKEDIN_CLIENT_SECRET == "...":
        missing_credentials.append("LINKEDIN_CLIENT_SECRET")
    
    # Display warnings or confirmations
    # Display callback URL
    # Display API information
```

### Settings Configuration

OAuth settings are defined in `backend/app/core/config.py`:

```python
class Settings(BaseSettings):
    # LinkedIn OAuth
    LINKEDIN_CLIENT_ID: str = Field(..., env="LINKEDIN_CLIENT_ID")
    LINKEDIN_CLIENT_SECRET: str = Field(..., env="LINKEDIN_CLIENT_SECRET")
    LINKEDIN_REDIRECT_URI: str = Field(
        default="http://localhost:8000/auth/callback/linkedin", 
        env="LINKEDIN_REDIRECT_URI"
    )
```

## Testing

### Manual Test

1. Delete or rename your `.env` file
2. Start the server
3. Verify you see the warning about missing credentials
4. Add credentials back to `.env`
5. Restart server
6. Verify you see the success confirmation

### Expected Output (Success)

```
================================================================================
🚀 LinkedIn Gateway API Starting Up
================================================================================

✅ LinkedIn OAuth Credentials: Configured

📋 LinkedIn OAuth Configuration
================================================================================
Callback URL (Redirect URI): http://localhost:8000/auth/callback/linkedin

⚙️  Add this URL to your LinkedIn Developer App:
   1. Go to: https://www.linkedin.com/developers/apps
   2. Select your app
   3. Go to 'Auth' tab
   4. Add this URL to 'Authorized redirect URLs for your app':
      http://localhost:8000/auth/callback/linkedin
================================================================================

🌐 API will be available at: http://0.0.0.0:8000
📖 API Documentation: http://localhost:8000/docs
🔍 Health Check: http://localhost:8000/health
================================================================================
```

