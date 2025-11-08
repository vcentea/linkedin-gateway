# HTTPS Tunneling Guide for LinkedIn OAuth

## Why HTTPS is Required

**LinkedIn OAuth REQUIRES HTTPS for callback URLs in production.**

LinkedIn will **REJECT** any HTTP callback URLs (like `http://localhost:8000/auth/user/callback`) when you try to add them to your LinkedIn Developer App settings.

## Detection on Startup

When you start the backend server, it will automatically:

1. ✅ Check if `PUBLIC_URL` is configured
2. ✅ Detect if you're behind a proxy/tunnel
3. ✅ Verify if HTTPS is being used
4. 🔴 Display a **CRITICAL WARNING** if using HTTP

## Configuration

Add these variables to your `backend/.env` file:

```env
# Public URL Configuration (for OAuth callbacks with HTTPS)
PUBLIC_URL=https://your-domain-or-tunnel-url.com
BEHIND_PROXY=true
TUNNEL_SERVICE=cloudflare  # or ngrok, nginx, etc.
```

### Environment Variables Explained

- **`PUBLIC_URL`**: Your public-facing HTTPS URL (required for LinkedIn OAuth)
- **`BEHIND_PROXY`**: Set to `true` if using a reverse proxy or tunnel
- **`TUNNEL_SERVICE`**: Optional - helps identify your setup (cloudflare, ngrok, nginx, etc.)

## Solution 1: Cloudflare Tunnel (Recommended - Free)

### Why Cloudflare Tunnel?
- ✅ **Free** - No cost for basic usage
- ✅ **Permanent URLs** - Get a stable URL that doesn't change
- ✅ **No port forwarding** - Works behind NAT/firewalls
- ✅ **Built-in DDoS protection**
- ✅ **Easy setup** - Just a few commands

### Quick Start (Temporary Tunnel)

1. **Install Cloudflared:**
   ```bash
   # Windows (using Chocolatey)
   choco install cloudflared
   
   # Or download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/
   ```

2. **Start Tunnel:**
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```

3. **Copy the HTTPS URL** from the output (e.g., `https://abc-123-def.trycloudflare.com`)

4. **Update `.env`:**
   ```env
   PUBLIC_URL=https://abc-123-def.trycloudflare.com
   BEHIND_PROXY=true
   TUNNEL_SERVICE=cloudflare
   ```

5. **Restart your backend server**

### Permanent Tunnel Setup

For a stable URL that doesn't change:

1. **Login to Cloudflare:**
   ```bash
   cloudflared tunnel login
   ```

2. **Create a Tunnel:**
   ```bash
   cloudflared tunnel create linkedin-gateway
   ```

3. **Configure the Tunnel:**
   Create `~/.cloudflared/config.yml`:
   ```yaml
   tunnel: <TUNNEL-ID>
   credentials-file: /path/to/.cloudflared/<TUNNEL-ID>.json
   
   ingress:
     - hostname: linkedin-gateway.yourdomain.com
       service: http://localhost:8000
     - service: http_status:404
   ```

4. **Route DNS:**
   ```bash
   cloudflared tunnel route dns linkedin-gateway linkedin-gateway.yourdomain.com
   ```

5. **Run the Tunnel:**
   ```bash
   cloudflared tunnel run linkedin-gateway
   ```

6. **Update `.env`:**
   ```env
   PUBLIC_URL=https://linkedin-gateway.yourdomain.com
   BEHIND_PROXY=true
   TUNNEL_SERVICE=cloudflare
   ```

## Solution 2: Ngrok (Easy - Free Tier)

### Why Ngrok?
- ✅ **Very easy** - One command to start
- ✅ **Free tier available** - Good for development
- ⚠️ **URL changes** - Free tier gets new URL on each restart
- ⚠️ **Rate limits** - Free tier has connection limits

### Setup

1. **Install Ngrok:**
   - Download from: https://ngrok.com/download
   - Or use package manager:
     ```bash
     # Windows (Chocolatey)
     choco install ngrok
     ```

2. **Sign up** (optional but recommended):
   - Get auth token from: https://dashboard.ngrok.com/get-started/your-authtoken
   ```bash
   ngrok config add-authtoken <YOUR_TOKEN>
   ```

3. **Start Tunnel:**
   ```bash
   ngrok http 8000
   ```

4. **Copy the HTTPS URL** from the output (e.g., `https://abc123.ngrok.io`)

5. **Update `.env`:**
   ```env
   PUBLIC_URL=https://abc123.ngrok.io
   BEHIND_PROXY=true
   TUNNEL_SERVICE=ngrok
   ```

6. **Restart your backend server**

### Ngrok Paid Features

For stable URLs, consider Ngrok's paid plans:
- **Static domain** - URL doesn't change
- **Custom domains** - Use your own domain
- **No connection limits**

## Solution 3: Nginx Reverse Proxy (Self-Hosted)

### Why Nginx?
- ✅ **Full control** - Own your infrastructure
- ✅ **Production-ready** - Battle-tested
- ✅ **Free SSL** - Use Let's Encrypt
- ⚠️ **Requires server** - Need a VPS or dedicated server
- ⚠️ **More complex** - Requires SSL certificate setup

### Setup

1. **Install Nginx:**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install nginx
   ```

2. **Install Certbot (for Let's Encrypt SSL):**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   ```

3. **Configure Nginx:**
   Create `/etc/nginx/sites-available/linkedin-gateway`:
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;
       
       location / {
           return 301 https://$server_name$request_uri;
       }
   }
   
   server {
       listen 443 ssl http2;
       server_name yourdomain.com;
       
       ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

4. **Enable Site:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/linkedin-gateway /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

5. **Get SSL Certificate:**
   ```bash
   sudo certbot --nginx -d yourdomain.com
   ```

6. **Update `.env`:**
   ```env
   PUBLIC_URL=https://yourdomain.com
   BEHIND_PROXY=true
   TUNNEL_SERVICE=nginx
   ```

## Solution 4: Cloud Deployment (Production)

### Cloud Platforms with Built-in HTTPS

All major cloud platforms provide HTTPS by default:

#### Heroku
```bash
heroku create linkedin-gateway
git push heroku main
```
- URL: `https://linkedin-gateway.herokuapp.com`

#### Railway
- Connect GitHub repo
- Deploy automatically
- URL: `https://linkedin-gateway.up.railway.app`

#### Render
- Connect GitHub repo
- Deploy automatically
- URL: `https://linkedin-gateway.onrender.com`

#### DigitalOcean App Platform
- Connect GitHub repo
- Deploy automatically
- URL: `https://linkedin-gateway-xxxxx.ondigitalocean.app`

### Update `.env` for Cloud:
```env
PUBLIC_URL=https://your-app.platform.com
BEHIND_PROXY=true
TUNNEL_SERVICE=heroku  # or railway, render, digitalocean, etc.
```

## Verification

### 1. Start Your Backend

```bash
cd backend
python main.py
```

### 2. Check Startup Output

**If HTTP (Local Development):**
```
🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴
⛔ CRITICAL: LinkedIn OAuth REQUIRES HTTPS!
================================================================================
LinkedIn will NOT accept HTTP callback URLs in production.
Your current callback URL uses HTTP, which will be REJECTED by LinkedIn.

🔧 SOLUTIONS to expose your API with HTTPS:
[... solutions listed ...]
================================================================================
🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴
```

**If HTTPS (Properly Configured):**
```
✅ Public URL configured: https://your-tunnel.trycloudflare.com
   Tunnel/Proxy Service: cloudflare

✅ HTTPS is configured - LinkedIn OAuth will work!

Callback URL (Redirect URI): https://your-tunnel.trycloudflare.com/auth/user/callback
```

### 3. Add to LinkedIn Developer Portal

1. Go to: https://www.linkedin.com/developers/apps
2. Select your app
3. Go to "Auth" tab
4. Add the HTTPS callback URL shown in your startup logs
5. Click "Update"

### 4. Test OAuth Flow

1. Open your browser to: `{PUBLIC_URL}/auth/login/linkedin`
2. You should be redirected to LinkedIn
3. After login, you'll be redirected back to your callback URL

## Troubleshooting

### Issue: "redirect_uri_mismatch"

**Cause:** The callback URL doesn't match what's in LinkedIn Developer Portal

**Solution:**
1. Check the exact URL in your startup logs
2. Ensure it matches EXACTLY in LinkedIn (including https://)
3. No trailing slashes
4. Protocol must match (https)

### Issue: Tunnel URL Changes

**Cause:** Using temporary tunnel (Ngrok free tier or Cloudflare quick tunnel)

**Solution:**
- Use Cloudflare permanent tunnel (free)
- Or upgrade to Ngrok paid plan for static domains
- Or deploy to a cloud platform

### Issue: "This site can't be reached"

**Cause:** Tunnel is not running or backend is not accessible

**Solution:**
1. Ensure backend is running: `python main.py`
2. Ensure tunnel is running: `cloudflared tunnel --url http://localhost:8000`
3. Check firewall settings
4. Verify port 8000 is not blocked

### Issue: SSL Certificate Errors

**Cause:** Using self-signed certificate or expired certificate

**Solution:**
- Use Let's Encrypt for free valid certificates
- Or use a tunneling service (they handle SSL for you)
- Never use self-signed certificates for OAuth

## Comparison Table

| Solution | Cost | Difficulty | Stable URL | Best For |
|----------|------|------------|------------|----------|
| **Cloudflare Tunnel** | Free | Easy | Yes (permanent) | Development & Production |
| **Ngrok Free** | Free | Very Easy | No | Quick Testing |
| **Ngrok Paid** | $8/mo | Very Easy | Yes | Development |
| **Nginx + Let's Encrypt** | Free* | Medium | Yes | Self-hosted Production |
| **Cloud Platform** | Varies | Easy | Yes | Production |

*Requires a server (VPS costs apply)

## Recommended Setup

### For Development:
1. **Start with Cloudflare Tunnel** (quick tunnel for testing)
2. **Upgrade to permanent tunnel** when ready (still free)

### For Production:
1. **Deploy to cloud platform** (Heroku, Railway, Render, etc.)
2. **Or use Cloudflare Tunnel** with your own domain
3. **Or self-host with Nginx** + Let's Encrypt

## Next Steps

1. Choose a solution from above
2. Set up HTTPS access
3. Update your `.env` file with `PUBLIC_URL`
4. Restart your backend
5. Verify the startup logs show HTTPS ✅
6. Add the HTTPS callback URL to LinkedIn Developer Portal
7. Test the OAuth flow

