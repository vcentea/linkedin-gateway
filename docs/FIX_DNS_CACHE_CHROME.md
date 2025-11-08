# Fix: ERR_NAME_NOT_RESOLVED in Chrome

## Problem
Chrome shows: `net::ERR_NAME_NOT_RESOLVED` for your server URL, but the server is actually working fine.

## Cause
Chrome's DNS cache has stale or missing entries for your domain.

## Solution

### Method 1: Clear Chrome's DNS Cache (Fastest)

1. **Open Chrome's DNS settings:**
   ```
   chrome://net-internals/#dns
   ```

2. **Click "Clear host cache"**

3. **Reload the extension page**

---

### Method 2: Flush System DNS Cache

**Windows:**
```cmd
ipconfig /flushdns
```

**Mac:**
```bash
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

**Linux:**
```bash
sudo systemd-resolve --flush-caches
```

Then **restart Chrome completely**.

---

### Method 3: Reset Chrome's Network Settings

1. Go to:
   ```
   chrome://net-internals/#sockets
   ```

2. Click **"Flush socket pools"**

3. Go to:
   ```
   chrome://net-internals/#dns
   ```

4. Click **"Clear host cache"**

5. **Restart Chrome**

---

### Method 4: Use IP Address Temporarily

If DNS still doesn't work, you can use the IP address directly:

**Your server IP:** `188.114.97.3` or `188.114.96.3`

**But this won't work with Cloudflare** because:
- Cloudflare requires the correct `Host` header
- SSL certificate won't match the IP

**Better solution:** Fix DNS

---

## Verification

After clearing DNS cache:

1. **Check domain resolves:**
   ```cmd
   nslookup lg.ainnovate.tech
   ```

2. **Test in browser:**
   - Open new tab
   - Go to: `https://lg.ainnovate.tech/health`
   - Should show: `{"status":"ok"}`

3. **Test in extension:**
   - Open extension login page
   - Select "Custom Server"
   - Enter: `https://lg.ainnovate.tech`
   - Click "Connect Server"
   - Should show: "Server is online" ✅

---

## If Still Not Working

### Check Cloudflare Settings

Since your server is behind Cloudflare, check:

1. **DNS Settings in Cloudflare Dashboard:**
   - Go to: https://dash.cloudflare.com
   - Select your domain: `ainnovate.tech`
   - Click "DNS" → "Records"
   - Verify `lg` subdomain exists and points to your server IP
   - Make sure **Proxy status is "Proxied" (orange cloud)** ✅

2. **SSL/TLS Settings:**
   - Go to "SSL/TLS" tab
   - Set to: **"Full (strict)"** or **"Full"**
   - This ensures HTTPS works properly

3. **Firewall Rules:**
   - Go to "Security" → "WAF"
   - Make sure no rules are blocking your requests
   - Check "Security Events" for blocked requests

---

## Alternative: Use a Different DNS Server

If your ISP's DNS is slow or problematic:

**Windows:**
1. Open "Network Connections" (Control Panel)
2. Right-click your network adapter → Properties
3. Select "Internet Protocol Version 4 (TCP/IPv4)"
4. Click Properties
5. Select "Use the following DNS server addresses:"
   - Preferred: `1.1.1.1` (Cloudflare DNS)
   - Alternate: `8.8.8.8` (Google DNS)
6. Click OK

**After changing DNS**, flush cache:
```cmd
ipconfig /flushdns
```

Then restart Chrome.

---

## Why This Happens

**Common causes:**
1. **DNS propagation delay** - After creating/changing DNS records, it takes time to propagate (up to 48 hours, usually much faster)
2. **Browser DNS cache** - Chrome caches DNS results
3. **System DNS cache** - Windows/Mac/Linux cache DNS
4. **ISP DNS issues** - Your ISP's DNS server might be slow or outdated
5. **Cloudflare propagation** - New Cloudflare records take a few minutes

---

## Quick Reference

| Action | Command |
|--------|---------|
| Clear Chrome DNS | `chrome://net-internals/#dns` → Clear host cache |
| Flush Windows DNS | `ipconfig /flushdns` |
| Check domain resolves | `nslookup lg.ainnovate.tech` |
| Test server directly | `curl https://lg.ainnovate.tech/health` |
| Restart Chrome | Close ALL Chrome windows, reopen |

---

## Your Server is Working!

The server is responding correctly:
```bash
$ curl https://lg.ainnovate.tech/health
{"status":"ok"}
```

The issue is just DNS resolution in Chrome. Once you clear the cache, it will work! 🎉

