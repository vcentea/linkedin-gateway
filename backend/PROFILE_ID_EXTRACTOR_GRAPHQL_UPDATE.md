# Profile ID Extractor - GraphQL API Update

## Overview

Updated the profile ID extraction logic to use LinkedIn's GraphQL API instead of parsing HTML pages. This is more reliable, faster, and cleaner.

## Previous Approach (HTML Parsing)

**Problems:**
- Fetched entire HTML page
- Parsed hidden `<code>` elements with display:none
- Decoded HTML entities
- Searched for JSON data in HTML
- Fragile - breaks when LinkedIn changes HTML structure
- Slower due to larger response size

## New Approach (GraphQL API)

**GraphQL Endpoint:**
```
GET https://www.linkedin.com/voyager/api/graphql?variables=(vanityName:{VANITY_NAME})&queryId=voyagerIdentityDashProfiles.34ead06db82a2cc9a778fac97f69ad6a
```

**Process:**
1. Extract vanity name from URL (e.g., `vlad-centea-821435309` from `https://www.linkedin.com/in/vlad-centea-821435309`)
2. Call GraphQL endpoint with vanity name
3. Parse JSON response
4. Find profile object in `included` array where `publicIdentifier` matches vanity name
5. Extract profile ID from `entityUrn` field

**Response Structure:**
```json
{
    "included": [
        {
            "lastName": "Centea",
            "entityUrn": "urn:li:fsd_profile:ACoAAE6NWVkBs_w9UHFzV8oRIt_9bFJxdXlAEVM",
            "publicIdentifier": "vlad-centea-821435309",
            "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
            "firstName": "Vlad"
        }
    ]
}
```

## Benefits

✅ **Cleaner** - Direct API call, no HTML parsing
✅ **Faster** - Smaller JSON response vs full HTML page
✅ **More Reliable** - API endpoint less likely to change than HTML structure
✅ **Easier to Debug** - JSON response is easier to inspect
✅ **Better Error Handling** - Clear API responses vs unpredictable HTML

## Implementation Details

### File Updated
- `backend/app/linkedin/utils/profile_id_extractor.py`

### Code Changes

**Old Logic:**
```python
# Fetch HTML page
response = await client.get(profile_input, headers=headers)
html = response.text

# Parse hidden code elements
hidden_code_pattern = r'<code[^>]*style="display:\s*none"[^>]*>([^<]+)</code>'
# ... complex HTML parsing ...
```

**New Logic:**
```python
# Build GraphQL URL
graphql_url = (
    f"https://www.linkedin.com/voyager/api/graphql"
    f"?variables=(vanityName:{vanity_name})"
    f"&queryId=voyagerIdentityDashProfiles.34ead06db82a2cc9a778fac97f69ad6a"
)

# Fetch JSON response
response = await client.get(graphql_url, headers=headers)
data = response.json()

# Find profile in included array
for item in data.get('included', []):
    if item.get('publicIdentifier') == vanity_name:
        entity_urn = item.get('entityUrn', '')
        # Extract ID from URN
        urn_match = re.search(r'urn:li:fsd_profile:([A-Za-z0-9_-]+)', entity_urn)
        if urn_match:
            return urn_match.group(1)
```

### Removed Code
- `decode_html_entities()` function (no longer needed)
- HTML parsing regex patterns
- JSON extraction from HTML code blocks
- All HTML-related logic

## Affected Services

This utility is used by:
- `LinkedInConnectionService` - For connection requests
- `LinkedInMessageService` - For direct messages
- `LinkedInProfileService` - For profile operations
- Any other service that needs to resolve LinkedIn URLs to profile IDs

All services benefit from this improvement automatically.

## Error Handling

The GraphQL approach maintains the same error handling:
- Returns clear `ValueError` if vanity name cannot be extracted from URL
- Returns `ValueError` if GraphQL API returns error (401 = expired session)
- Returns `ValueError` if profile not found in response

## Testing

**Example URL:**
```
https://www.linkedin.com/in/vlad-centea-821435309
```

**Steps:**
1. Extract vanity name: `vlad-centea-821435309`
2. Call GraphQL: `...?variables=(vanityName:vlad-centea-821435309)&queryId=...`
3. Find profile with `publicIdentifier: "vlad-centea-821435309"`
4. Extract from `entityUrn: "urn:li:fsd_profile:ACoAAE6NWVkBs_w9UHFzV8oRIt_9bFJxdXlAEVM"`
5. Return profile ID: `ACoAAE6NWVkBs_w9UHFzV8oRIt_9bFJxdXlAEVM`

## Migration Notes

- No breaking changes - function signature remains the same
- All existing callers work without modification
- Improved performance and reliability
- Same error handling behavior

