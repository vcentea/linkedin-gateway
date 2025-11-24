# LinkedIn Server-Side Authentication Limitation

## 🚨 Critical Issue: 401 Unauthorized

### The Problem

When executing LinkedIn API calls from the **server**, we get `401 Unauthorized` errors, even though the **client-side** calls work perfectly.

### Root Cause

**Client-Side (Works ✅):**
```javascript
fetch(url, {
    headers: {
        'csrf-token': csrfToken,
        'cookie': `JSESSIONID="${csrfToken}";`
    },
    credentials: 'include'  // ← THIS IS KEY!
})
```

The `credentials: 'include'` tells the browser to **automatically include ALL LinkedIn cookies**:
- `JSESSIONID` (CSRF token)
- `li_at` (authentication token)
- `lidc` (datacenter routing)
- `bcookie` (browser cookie)
- `bscookie` (secure browser cookie)
- `lang` (language preference)
- ...and potentially 10+ more cookies

**Server-Side (Fails ❌):**
```python
httpx.get(url, headers={
    'csrf-token': csrf_token,
    'cookie': f'JSESSIONID="{csrf_token}";'
})
```

We only have the `JSESSIONID` cookie (CSRF token), but **LinkedIn requires the complete authenticated session** with all cookies to authorize the request.

---

## 📊 What We're Missing

### Current Storage:
```sql
api_keys table:
- csrf_token (VARCHAR)  ← Only JSESSIONID
```

### What We Need:
```sql
api_keys table:
- csrf_token (VARCHAR)       ← JSESSIONID
- li_at_token (VARCHAR)      ← Main auth token
- linkedin_cookies (JSONB)   ← ALL cookies as JSON
```

---

## 🔧 Solutions

### Option 1: Store All LinkedIn Cookies (Recommended)

**Changes Required:**

1. **Database Migration:**
```sql
ALTER TABLE api_keys ADD COLUMN linkedin_cookies JSONB;
```

2. **Client Updates:**
   - Extract ALL LinkedIn cookies from browser
   - Send complete cookie jar to backend
   - Update cookies when they change

3. **Server Updates:**
   - Store all cookies in database
   - Send all cookies with each request

**Pros:**
- ✅ Full server-side execution works
- ✅ Complete control over requests
- ✅ Can implement retry logic, rate limiting, etc.

**Cons:**
- ❌ More complex cookie management
- ❌ Security concern (storing sensitive cookies)
- ❌ Cookies can expire/change frequently

---

### Option 2: Client-Only Execution (Current Workaround)

Keep `server_call=false` as default and recommended approach.

**Pros:**
- ✅ Works perfectly now
- ✅ No security concerns
- ✅ Browser handles all authentication

**Cons:**
- ❌ Requires browser/extension to be active
- ❌ Limited to what browser can do

---

### Option 3: Hybrid Approach

Use **server-side for non-authenticated endpoints** only (if any exist), and **client-side for authenticated endpoints**.

---

## 🎯 Recommended Approach

**Short-term:** Use `server_call=false` (client-side execution via WebSocket)
- This is the default
- Works perfectly
- No changes needed

**Long-term:** Implement Option 1 if needed
- Only if you need server-side execution for:
  - Scheduled tasks
  - Bulk operations
  - Server-side rate limiting
  - Independence from browser

---

## 💡 Implementation for Option 1

### Step 1: Update Database Schema

```sql
-- Add column for storing all LinkedIn cookies
ALTER TABLE api_keys ADD COLUMN linkedin_cookies JSONB DEFAULT '{}';

-- Index for faster lookups
CREATE INDEX idx_api_keys_cookies ON api_keys USING gin (linkedin_cookies);
```

### Step 2: Update Client to Send All Cookies

```javascript
// In linkedin.controller.js - get ALL LinkedIn cookies
async function getAllLinkedInCookies() {
    return new Promise((resolve) => {
        chrome.cookies.getAll({ domain: '.linkedin.com' }, (cookies) => {
            const cookieObj = {};
            cookies.forEach(cookie => {
                cookieObj[cookie.name] = cookie.value;
            });
            resolve(cookieObj);
        });
    });
}

// When updating CSRF token, also send all cookies
async function updateLinkedInCookies() {
    const cookies = await getAllLinkedInCookies();
    
    // Send to backend
    await fetch(`${API_URL}/users/me/api-key/linkedin-cookies`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({ cookies })
    });
}
```

### Step 3: Update Backend to Store Cookies

```python
# In app/crud/api_key.py
async def update_linkedin_cookies(
    db: AsyncSession, 
    user_id: UUID, 
    cookies: dict
) -> Optional[APIKey]:
    """Update LinkedIn cookies for user's active API key."""
    active_key = await get_active_api_key_by_user(db=db, user_id=user_id)
    if active_key:
        active_key.linkedin_cookies = cookies
        db.add(active_key)
        await db.flush()
        await db.refresh(active_key)
        return active_key
    return None
```

### Step 4: Update Server to Use All Cookies

```python
# In app/linkedin/services/base.py
def _build_headers(self, linkedin_cookies: dict = None) -> Dict[str, str]:
    """Build headers with all LinkedIn cookies."""
    
    # Build cookie string from all cookies
    if linkedin_cookies:
        cookie_string = "; ".join([
            f"{name}={value}" 
            for name, value in linkedin_cookies.items()
        ])
    else:
        # Fallback to just JSESSIONID
        cookie_string = f'JSESSIONID="{self.csrf_token}";'
    
    return {
        'csrf-token': self.csrf_token,
        'accept': 'application/vnd.linkedin.normalized+json+2.1',
        'X-RestLi-Protocol-Version': '2.0.0',
        'cookie': cookie_string,
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
```

---

## 🔒 Security Considerations

**If implementing Option 1:**

1. **Encrypt cookies at rest:**
   ```python
   from cryptography.fernet import Fernet
   
   # Encrypt before storing
   encrypted_cookies = encrypt(json.dumps(cookies))
   
   # Decrypt before using
   cookies = json.loads(decrypt(encrypted_cookies))
   ```

2. **Use secure storage:**
   - PostgreSQL with encryption at rest
   - Restricted database access
   - Audit logging for cookie access

3. **Cookie refresh strategy:**
   - Re-sync cookies periodically (every hour?)
   - Handle expired cookies gracefully
   - Fall back to client-side if server-side fails

---

## 📈 Testing

To verify what cookies are needed:

```javascript
// In browser console on linkedin.com
chrome.cookies.getAll({ domain: '.linkedin.com' }, console.log);
```

Common required cookies:
- `li_at` - Main authentication
- `JSESSIONID` - CSRF protection
- `lidc` - Datacenter routing
- `bcookie` - Browser identification
- `bscookie` - Secure browser cookie

---

## 🎓 Summary

**Current State:**
- ✅ Client-side execution works perfectly
- ❌ Server-side execution fails (401) - missing cookies

**Solution:**
- **Easy:** Keep using client-side (`server_call=false`)
- **Complex:** Store and use ALL LinkedIn cookies for server-side calls

**Recommendation:**
Use **client-side execution** unless you have a specific need for server-side execution that justifies the additional complexity and security considerations.

