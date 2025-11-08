# Quick Fix: Extension Shows Server Offline

## Your Situation
- Server deployed at: `https://lg.ainnovate.tech`
- Extension shows: "Server is offline"
- Backend `/health` endpoint should work

## Most Likely Cause: CORS Configuration

The Chrome extension needs CORS headers to connect to your server. Without these headers, the browser blocks the connection.

---

## 🚀 Quick Fix (5 minutes)

### Step 1: Check Your `.env` File

SSH to your server and check:

```bash
cd /path/to/LinkedinGateway-SaaS/deployment
cat .env | grep CORS_ORIGINS
```

**It should show:**
```bash
CORS_ORIGINS=chrome-extension://*
```

**Or for development (less secure):**
```bash
CORS_ORIGINS=*
```

### Step 2: Update `.env` If Needed

If CORS is not set correctly, edit:

```bash
nano deployment/.env
```

**Add or update these lines:**
```bash
# Your public URL (required!)
PUBLIC_URL=https://lg.ainnovate.tech

# CORS - Allow extension access
CORS_ORIGINS=chrome-extension://*
```

**Save and exit** (Ctrl+X, Y, Enter)

### Step 3: Restart Backend

```bash
cd deployment
docker compose restart backend
```

Wait 10 seconds for the backend to fully restart.

### Step 4: Verify Backend is Accessible

```bash
# Test from server
curl http://localhost:7778/health

# Expected: {"status":"ok"}
```

```bash
# Test from your computer (not the server)
curl https://lg.ainnovate.tech/health

# Expected: {"status":"ok"}
```

### Step 5: Test in Extension

1. Open Chrome extension login page
2. Select "Custom Server" from dropdown
3. Enter: `https://lg.ainnovate.tech`
4. Click "Connect Server"
5. **Accept permission prompt when it appears**
6. Wait for green "Server is online" indicator

---

## 🔍 Diagnostic Tool

If still not working, use the built-in diagnostic tool:

1. Go to `chrome://extensions`
2. Enable "Developer mode" (top right)
3. Find your extension ID (something like: `abcdefghijklmnopqrstuvwxyz`)
4. Open in new tab:
   ```
   chrome-extension://YOUR_EXTENSION_ID/pages/tools/server-test.html
   ```
5. Enter: `https://lg.ainnovate.tech`
6. Click "Run Tests"
7. See exactly what's wrong

---

## 📋 Verification Checklist

Check these items:

### Backend Server
```bash
# 1. Container is running
docker compose ps
# backend should show "Up"

# 2. Logs show no errors
docker compose logs backend | tail -50
# Should NOT show errors

# 3. Health endpoint works
curl http://localhost:7778/health
# Should return: {"status":"ok"}
```

### Network Access
```bash
# 4. Port is accessible remotely
curl https://lg.ainnovate.tech/health
# Should return: {"status":"ok"}

# 5. CORS headers present
curl -v -X OPTIONS https://lg.ainnovate.tech/health | grep Access-Control
# Should show: Access-Control-Allow-Origin
```

### Extension Settings
```text
6. Extension has permission for custom server
   - Click "Connect Server" button
   - Accept permission prompt

7. Correct URL in extension
   - Should be: https://lg.ainnovate.tech
   - NO trailing slash
   - Must be HTTPS (not HTTP)
```

---

## Common Issues

### Issue 1: Port Not Open

**Symptom:** `curl` from your computer times out, but works on server

**Fix:**
```bash
# Check firewall
sudo ufw status

# Allow port 7778
sudo ufw allow 7778/tcp

# Or if using iptables
sudo iptables -I INPUT -p tcp --dport 7778 -j ACCEPT
```

### Issue 2: Reverse Proxy Needed

**Symptom:** You're using Nginx/Caddy in front of the backend

**Fix:** Ensure proxy passes CORS headers and forwards requests to port 7778

**Caddy (Recommended - Auto HTTPS):**
```caddyfile
# /etc/caddy/Caddyfile
lg.ainnovate.tech {
    reverse_proxy localhost:7778
}
```

Restart Caddy:
```bash
sudo systemctl restart caddy
```

**Nginx:**
```nginx
# /etc/nginx/sites-available/lg.ainnovate.tech
server {
    listen 443 ssl http2;
    server_name lg.ainnovate.tech;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:7778;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # IMPORTANT: Don't override CORS headers from backend
    }
}
```

### Issue 3: SSL Certificate Issues

**Symptom:** SSL errors in browser console

**Fix:** Use Let's Encrypt or Caddy for automatic valid certificates

**With Certbot (if using Nginx):**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d lg.ainnovate.tech
```

**With Caddy (easiest):**
```bash
# Caddy automatically gets Let's Encrypt certificates
sudo apt install caddy
```

---

## Your `.env` Should Look Like This

```bash
# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
DB_USER=linkedin_gateway_user
DB_PASSWORD=your_secure_password_here
DB_NAME=LinkedinGateway
DB_PORT=5432

# =============================================================================
# API CONFIGURATION
# =============================================================================
BACKEND_PORT=7778
PORT=7778
API_HOST=0.0.0.0

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here

# =============================================================================
# LINKEDIN OAUTH CREDENTIALS
# =============================================================================
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret

# =============================================================================
# PUBLIC URL - THIS IS REQUIRED!
# =============================================================================
PUBLIC_URL=https://lg.ainnovate.tech

# =============================================================================
# CORS CONFIGURATION - THIS IS CRITICAL FOR EXTENSION
# =============================================================================
# Allow Chrome extension to connect
CORS_ORIGINS=chrome-extension://*

# Or allow everything (less secure, but simpler for testing)
# CORS_ORIGINS=*

# =============================================================================
# EDITION CONFIGURATION
# =============================================================================
LG_BACKEND_EDITION=core
LG_CHANNEL=default

# =============================================================================
# RATE LIMITING
# =============================================================================
DEFAULT_RATE_LIMIT=100
DEFAULT_RATE_WINDOW=3600
```

---

## Still Not Working?

### Enable Debug Mode

1. **Backend logs in real-time:**
   ```bash
   docker compose logs -f backend
   ```

2. **Extension console:**
   - Open extension login page
   - Press F12
   - Go to "Console" tab
   - Look for errors (red text)

3. **Network tab:**
   - F12 → "Network" tab
   - Try to connect
   - Look for failed `/health` request
   - Click on it to see details

### Get Help

Collect this information:

```bash
# 1. Docker status
docker compose ps

# 2. Backend logs
docker compose logs backend | tail -100

# 3. Test health endpoint
curl -v https://lg.ainnovate.tech/health

# 4. Test CORS
curl -v -X OPTIONS https://lg.ainnovate.tech/health

# 5. Check environment
docker compose exec backend env | grep -E "CORS|PUBLIC_URL|PORT"
```

Share the output along with:
- Extension console errors (F12 → Console)
- Network tab screenshot (F12 → Network → failed request)

---

## TL;DR - 30 Second Fix

```bash
# 1. SSH to server
ssh user@yourserver.com

# 2. Navigate to project
cd /path/to/LinkedinGateway-SaaS/deployment

# 3. Edit .env
nano .env

# 4. Add/update these lines:
PUBLIC_URL=https://lg.ainnovate.tech
CORS_ORIGINS=chrome-extension://*

# 5. Save (Ctrl+X, Y, Enter)

# 6. Restart
docker compose restart backend

# 7. Test
curl https://lg.ainnovate.tech/health

# 8. In extension: Select "Custom Server", enter URL, click "Connect Server"
```

Done! 🎉

