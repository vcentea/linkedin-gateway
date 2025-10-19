# LinkedIn API URL Comparison: Client vs Server

**⚠️ CRITICAL: URLs must be EXACTLY 1:1 between client and server**

This document shows the exact URL construction for each LinkedIn API endpoint on both client and server sides. Any changes to these URLs must maintain exact parity.

---

## Feed API (updatesV2)

### Client
**File:** `chrome-extension/src-v2/content/linkedin/feed.js:115`

```javascript
const requestedCount = count + 1; // Request one more than needed
const url = `https://www.linkedin.com/voyager/api/feed/updatesV2?count=${requestedCount}&start=${startIndex}&q=feed&includeLongTermHistory=true&useCase=DEFAULT`;
```

### Server
**File:** `backend/app/linkedin/services/feed.py:62-67`

```python
requested_count = count + 1
url = (
    f"{self.VOYAGER_BASE_URL}/feed/updatesV2"
    f"?count={requested_count}&start={start_index}"
    f"&q=feed&includeLongTermHistory=true&useCase=DEFAULT"
)
```

### Status: ✅ MATCH

**Example URL:**
```
https://www.linkedin.com/voyager/api/feed/updatesV2?count=11&start=0&q=feed&includeLongTermHistory=true&useCase=DEFAULT
```

---

## Comments API (GraphQL)

### Client
**File:** `chrome-extension/src-v2/content/linkedin/comments.js:87`

```javascript
const url = `${GRAPHQL_BASE_URL}?variables=(count:${count},numReplies:${numReplies},socialDetailUrn:urn%3Ali%3Afsd_socialDetail%3A%28${encodeURIComponent(postUrn)}%2C${encodeURIComponent(postUrn)}%2Curn%3Ali%3AhighlightedReply%3A-%29,sortOrder:RELEVANCE,start:${start})&queryId=${COMMENTS_QUERY_ID}`;
```

### Server
**File:** `backend/app/linkedin/services/comments.py:75-82`

```python
encoded_post_urn = quote(post_urn, safe='')
url = (
    f"{self.GRAPHQL_BASE_URL}?variables="
    f"(count:{count},numReplies:{num_replies},"
    f"socialDetailUrn:urn%3Ali%3Afsd_socialDetail%3A%28{encoded_post_urn}%2C{encoded_post_urn}%2Curn%3Ali%3AhighlightedReply%3A-%29,"
    f"sortOrder:RELEVANCE,start:{start})"
    f"&queryId={self.COMMENTS_QUERY_ID}"
)
```

### Status: ✅ MATCH

**Key Points:**
- `quote(post_urn, safe='')` in Python = `encodeURIComponent(postUrn)` in JavaScript
- Manual encoding: `%3A` = `:`, `%28` = `(`, `%2C` = `,`, `%29` = `)`
- The prefix `urn%3Ali%3Afsd_socialDetail%3A%28` is manually encoded (not using quote/encodeURIComponent)
- PostUrn is encoded twice with separator `%2C` between them
- Suffix is manually encoded: `%2Curn%3Ali%3AhighlightedReply%3A-%29`

**Example URL:**
```
https://www.linkedin.com/voyager/api/graphql?variables=(count:10,numReplies:1,socialDetailUrn:urn%3Ali%3Afsd_socialDetail%3A%28urn%3Ali%3Aactivity%3A1234567890%2Curn%3Ali%3Aactivity%3A1234567890%2Curn%3Ali%3AhighlightedReply%3A-%29,sortOrder:RELEVANCE,start:0)&queryId=voyagerSocialDashComments.95ed44bc87596acce7c460c70934d0ff
```

---

## Constants

### Query IDs
- **Comments Query ID:** `voyagerSocialDashComments.95ed44bc87596acce7c460c70934d0ff`
  - Client: `chrome-extension/src-v2/content/linkedin/comments.js:28`
  - Server: `backend/app/linkedin/services/comments.py:18`

### Base URLs
- **Voyager API:** `https://www.linkedin.com/voyager/api`
  - Server: `backend/app/linkedin/services/base.py:22`
- **GraphQL API:** `https://www.linkedin.com/voyager/api/graphql`
  - Client: `chrome-extension/src-v2/content/linkedin/comments.js:22`
  - Server: `backend/app/linkedin/services/base.py:23`

---

## Verification Checklist

When modifying LinkedIn API calls, verify:

- [ ] URL structure matches exactly (query params in same order)
- [ ] Query parameter names match exactly (case-sensitive)
- [ ] URL encoding method is equivalent (`encodeURIComponent` = `quote(safe='')`)
- [ ] Manual encoding sequences match exactly (e.g., `%3A`, `%28`, `%2C`)
- [ ] Constants (query IDs, base URLs) are identical
- [ ] Any special formatting (like `count + 1`) is preserved
- [ ] Test both `server_call=true` and `server_call=false` work

---

## Testing

To verify URLs are identical:

1. **Enable logging** in both client and server
2. **Make the same request** with `server_call=true` and `server_call=false`
3. **Compare the logged URLs** character-by-character
4. **Verify response formats** are identical

---

**Last Updated:** 2025-01-11
**Maintainer:** Keep this document updated with any URL changes

