# Troubleshooting Server Connection Issues

## Problem: Extension Shows "Server is Offline"

If your extension shows the server as offline even though the server is running, follow these diagnostic steps.

---

## Quick Diagnostic Tool

### Using the Built-in Tester

1. **Load the unpacked extension** in Chrome (`chrome://extensions`)
2. **Navigate to**: `chrome-extension://YOUR_EXTENSION_ID/pages/tools/server-test.html`
3. **Enter your server URL**: `https://lg.ainnovate.tech`
4. **Click "Run Tests"**

The tool will check:
- ✅ URL format validation
- ✅ Chrome extension permissions
- ✅ CORS configuration
- ✅ `/health` endpoint connectivity  
- ✅ Server info endpoint
- ✅ SSL certificate validity

---

## Common Issues and Solutions

### 1. CORS Not Configured

**Symptom**: Extension can't connect, CORS errors in browser console

**Solution**: Check your `.env` file in the `deployment/` directory:

```bash
# Allow all origins (development only!)
CORS_ORIGINS=*

# Or specific origins (production)
CORS_ORIGINS=http://localhost:*,https://your-extension-id.chromiumapp.org,chrome-extension://*
```

**For Chrome Extension**, use:
```bash
CORS_ORIGINS=chrome-extension://*
```

**Restart** your Docker container after changing:
```bash
cd deployment
docker compose restart backend
```

---

### 2. Chrome Extension Permissions Missing

**Symptom**: "Permission required" or "Permission denied"

**Solution**: The extension needs explicit permission to access your custom server.

**In the login page:**
1. Select "Custom Server"
2. Enter your URL: `https://lg.ainnovate.tech`
3. Click "Connect Server"
4. **Accept the permission prompt** that appears

**Manual permission grant:**
1. Go to `chrome://extensions`
2. Find "LinkedIn Gateway"
3. Click "Details"
4. Scroll to "Site access"
5. Add your server URL

---

### 3. Server Not Accessible

**Symptom**: Timeout after 5 seconds, "Failed to fetch"

**Possible causes:**
- Server is not running
- Firewall blocking port 7778 (or your configured port)
- DNS not resolving
- Server not bound to `0.0.0.0` (listening on localhost only)

**Check if server is running:**
```bash
# From server machine
curl http://localhost:7778/health

# From your computer
curl https://lg.ainnovate.tech/health
```

**Expected response:**
```json
{"status":"ok"}
```

**Check Docker logs:**
```bash
cd deployment
docker compose logs -f backend
```

**Check server is accessible:**
```bash
# On server machine
netstat -tulpn | grep 7778

# Or check if port is exposed
docker compose ps backend
```

---

### 4. SSL Certificate Issues

**Symptom**: `net::ERR_CERT_AUTHORITY_INVALID` or `SEC_ERROR_UNKNOWN_ISSUER`

**Solution**: 

**Option A - Use a Valid Certificate (Recommended)**
Use Let's Encrypt with Certbot or Caddy:
```bash
# Install Caddy (auto HTTPS)
apt install caddy

# Caddy config (/etc/caddy/Caddyfile)
lg.ainnovate.tech {
    reverse_proxy localhost:7778
}
```

**Option B - Ignore Certificate Warnings (Development Only)**
1. Visit `https://lg.ainnovate.tech` in Chrome
2. Click "Advanced"
3. Click "Proceed to lg.ainnovate.tech (unsafe)"
4. Now try the extension again

⚠️ **Not recommended for production!**

---

### 5. Wrong Server URL in Extension

**Symptom**: Extension trying to connect to wrong server

**Solution**: 

1. Open extension login page
2. Check the server dropdown
3. If using "Custom Server", verify the URL is correct
4. URL should be: `https://lg.ainnovate.tech` (no trailing slash)
5. Click "Connect Server" to test

**Clear old settings:**
```javascript
// In browser console (extension page)
chrome.storage.local.clear(() => {
    location.reload();
});
```

---

### 6. Firewall Blocking Connections

**Symptom**: Connection timeout, works on server but not remotely

**Solution**:

**Check if port is open:**
```bash
# On server
sudo ufw status
sudo ufw allow 7778/tcp

# Or with iptables
sudo iptables -I INPUT -p tcp --dport 7778 -j ACCEPT
```

**Docker may bypass UFW**, so also check:
```bash
# Make sure Docker is publishing the port
docker compose ps backend
# Should show: 0.0.0.0:7778->7778/tcp
```

---

### 7. Backend Not Responding to /health

**Symptom**: Server runs but `/health` returns errors

**Check backend logs:**
```bash
docker compose logs backend | grep health
```

**Test directly:**
```bash
# Should return {"status":"ok"}
curl https://lg.ainnovate.tech/health

# Check with verbose output
curl -v https://lg.ainnovate.tech/health
```

**Check FastAPI is running:**
```bash
docker compose exec backend ps aux | grep uvicorn
```

---

## Step-by-Step Diagnostic Process

### Step 1: Verify Server is Running

```bash
# SSH to your server
ssh user@yourserver.com

# Check Docker containers
cd /path/to/LinkedinGateway-SaaS/deployment
docker compose ps

# Backend should show "running"
```

### Step 2: Test Health Endpoint Locally

```bash
# On the server
curl http://localhost:7778/health

# Expected: {"status":"ok"}
```

### Step 3: Test Health Endpoint Remotely

```bash
# From your computer (not the server)
curl https://lg.ainnovate.tech/health

# Expected: {"status":"ok"}
```

### Step 4: Check CORS Headers

```bash
curl -v -X OPTIONS https://lg.ainnovate.tech/health

# Look for:
# Access-Control-Allow-Origin: *
# or
# Access-Control-Allow-Origin: chrome-extension://...
```

### Step 5: Test from Extension

1. Open extension login page
2. Open Browser DevTools (F12)
3. Go to "Console" tab
4. Look for errors related to:
   - `fetch`
   - `CORS`
   - `net::ERR_`
5. Copy error messages for diagnosis

### Step 6: Use the Diagnostic Tool

Load: `chrome-extension://YOUR_EXTENSION_ID/pages/tools/server-test.html`

This will run all tests automatically and show exactly what's wrong.

---

## Environment Variables Checklist

Verify these in `deployment/.env`:

```bash
# Required
DB_USER=linkedin_gateway_user
DB_PASSWORD=your_secure_password
DB_NAME=LinkedinGateway

SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_secret_key

# LinkedIn OAuth
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret

# Public URL - MUST match your actual URL
PUBLIC_URL=https://lg.ainnovate.tech

# CORS - Allow extension access
CORS_ORIGINS=chrome-extension://*

# Port (default is 7778)
PORT=7778
```

After changing `.env`, restart:
```bash
cd deployment
docker compose restart backend
```

---

## Common Error Messages

### "Failed to fetch"
**Cause**: Server is not reachable
**Fix**: Check if server is running, firewall rules, DNS resolution

### "CORS policy: No 'Access-Control-Allow-Origin' header"
**Cause**: CORS not configured
**Fix**: Set `CORS_ORIGINS=chrome-extension://*` in `.env` and restart

### "net::ERR_CERT_AUTHORITY_INVALID"
**Cause**: Invalid SSL certificate
**Fix**: Use valid certificate (Let's Encrypt) or import self-signed cert

### "Permission denied"
**Cause**: Chrome extension doesn't have permission
**Fix**: Grant permission when prompted or manually in chrome://extensions

### "Server returned an error (500)"
**Cause**: Backend error (database, config, etc.)
**Fix**: Check backend logs: `docker compose logs backend`

---

## Still Not Working?

### Collect Diagnostic Information

1. **Backend logs:**
   ```bash
   docker compose logs backend > backend-logs.txt
   ```

2. **Extension console errors:**
   - Open extension login page
   - F12 → Console tab
   - Screenshot or copy errors

3. **Network errors:**
   - F12 → Network tab
   - Try to connect
   - Click failed request
   - Screenshot Headers and Response tabs

4. **Run diagnostic tool:**
   - Load `chrome-extension://YOUR_EXT_ID/pages/tools/server-test.html`
   - Run tests
   - Screenshot results

5. **Server info:**
   ```bash
   # Docker status
   docker compose ps
   
   # Backend health
   curl http://localhost:7778/health
   curl https://lg.ainnovate.tech/health
   
   # CORS check
   curl -v -X OPTIONS https://lg.ainnovate.tech/health
   
   # Port check
   netstat -tulpn | grep 7778
   ```

---

## Quick Fixes Summary

| Issue | Quick Fix |
|-------|-----------|
| CORS errors | Add `CORS_ORIGINS=chrome-extension://*` to `.env` |
| Permission denied | Click "Connect Server" and accept prompt |
| Server offline | Check `docker compose ps` and logs |
| SSL errors | Use Let's Encrypt or Caddy for valid cert |
| Timeout | Check firewall, ensure port 7778 is open |
| Wrong URL | Verify `PUBLIC_URL` in `.env` matches actual URL |

---

## Testing Checklist

- [ ] Server is running (`docker compose ps`)
- [ ] Health endpoint works locally (`curl http://localhost:7778/health`)
- [ ] Health endpoint works remotely (`curl https://lg.ainnovate.tech/health`)
- [ ] CORS headers present (`curl -v -X OPTIONS https://lg.ainnovate.tech/health`)
- [ ] Firewall allows port 7778
- [ ] SSL certificate is valid (if using HTTPS)
- [ ] Extension has permission for custom server
- [ ] Correct server URL in extension settings
- [ ] `PUBLIC_URL` in `.env` matches actual URL
- [ ] `CORS_ORIGINS` allows `chrome-extension://*`

---

## Need More Help?

1. Use the diagnostic tool first
2. Check all items in the testing checklist
3. Collect diagnostic information (logs, screenshots)
4. Review backend logs for specific error messages

