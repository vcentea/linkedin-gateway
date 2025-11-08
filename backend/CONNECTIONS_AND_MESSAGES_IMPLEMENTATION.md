# LinkedIn Connections and Messages Implementation

## Overview
This document describes the implementation of LinkedIn connection request and direct messaging endpoints, following the existing pattern used for feed operations.

## Files Created

### Service Layer (`backend/app/linkedin/services/`)

#### 1. `connections.py`
Implements the `LinkedInConnectionService` class with the following methods:

- **`send_simple_connection_request(profile_id: str)`**
  - Sends a connection request without a message
  - Mirrors `sendSimpleConnectionRequest` from the old frontend code
  - Endpoint: `POST /api/v1/connections/simple`

- **`send_connection_request_with_message(profile_id: str, message: str)`**
  - Sends a connection request with a custom message
  - Mirrors `sendConnectionRequestWithMessage` from the old frontend code
  - Endpoint: `POST /api/v1/connections/with-message`

#### 2. `messages.py`
Implements the `LinkedInMessageService` class with the following methods:

- **`send_direct_message(profile_id: str, message_text: str)`**
  - Sends a direct message to a LinkedIn profile
  - Automatically handles both new and existing conversations
  - Mirrors `sendDirectMessage` from the old frontend code
  - Endpoint: `POST /api/v1/messages/send`

**Helper methods:**
- `_randomize_edges(input_string: str)` - Randomizes first/last 3 characters for origin tokens
- `_extract_mailbox_urn(sdk_entity_urn: str)` - Extracts mailbox URN from conversation URN
- `_get_my_profile_id()` - Fetches the current user's LinkedIn profile ID
- `_get_conversation_details(profile_id: str)` - Gets existing conversation details with a profile

### API Layer (`backend/app/api/v1/`)

#### 1. `connections.py`
Provides two endpoints following the same pattern as the feed endpoint:

**Endpoints:**
- `POST /api/v1/connections/simple` - Send simple connection request
- `POST /api/v1/connections/with-message` - Send connection request with message

**Features:**
- Support for both `server_call=True` (direct server execution) and `server_call=False` (proxy via extension)
- API key validation
- WebSocket connection verification for proxy mode
- Comprehensive error handling and logging
- Structured response models

#### 2. `messages.py`
Provides endpoint for direct messaging:

**Endpoint:**
- `POST /api/v1/messages/send` - Send direct message

**Features:**
- Support for both `server_call=True` and `server_call=False` modes
- Automatically detects and handles existing conversations vs. new conversations
- API key validation
- WebSocket connection verification for proxy mode
- Comprehensive error handling and logging
- Structured response models

## Integration

### Updated Files

1. **`backend/app/linkedin/services/__init__.py`**
   - Added exports for `LinkedInConnectionService` and `LinkedInMessageService`

2. **`backend/main.py`**
   - Added imports for new routers
   - Registered new routers with `/api/v1` prefix:
     - `connections_v1_router`
     - `messages_v1_router`

## Request/Response Models

### Connection Requests

**SimpleConnectionRequest:**
```python
{
    "profile_id": str,          # LinkedIn profile ID OR profile URL
                                # Also accepts: "profile_identifier" (alias)
                                # Examples: 
                                # - "john-doe-123" (direct ID)
                                # - "https://www.linkedin.com/in/john-doe" (URL with vanity name)
    "api_key": str,             # User's API key
    "server_call": bool         # True for server execution, False for proxy (default: false)
}
```

**ConnectionWithMessageRequest:**
```python
{
    "profile_id": str,          # LinkedIn profile ID OR profile URL
                                # Also accepts: "profile_identifier" (alias)
                                # Examples: 
                                # - "john-doe-123" (direct ID)
                                # - "https://www.linkedin.com/in/john-doe" (URL with vanity name)
    "message": str,             # Custom message
    "api_key": str,             # User's API key
    "server_call": bool         # True for server execution, False for proxy (default: false)
}
```

**ConnectionResponse:**
```python
{
    "success": bool
}
```

### Direct Messages

**SendMessageRequest:**
```python
{
    "profile_id": str,          # LinkedIn profile ID OR profile URL
                                # Also accepts: "profile_identifier" (alias)
                                # Examples: 
                                # - "john-doe-123" (direct ID)
                                # - "https://www.linkedin.com/in/john-doe" (URL with vanity name)
    "message_text": str,        # Message content
    "api_key": str,             # User's API key
    "server_call": bool         # True for server execution, False for proxy (default: false)
}
```

**MessageResponse:**
```python
{
    "success": bool
}
```

## Execution Modes

Both services support two execution modes:

### 1. Server Call Mode (`server_call=True`)
- Executes LinkedIn API calls directly from the backend
- Requires LinkedIn cookies to be stored in the database
- More reliable but requires cookie management

### 2. Proxy Mode (`server_call=False`)
- Routes requests through the browser extension
- Uses active WebSocket connection
- No cookie storage required on server
- Requires browser extension to be active

## LinkedIn API Endpoints Used

### Connection Requests
```
POST https://www.linkedin.com/voyager/api/voyagerRelationshipsDashMemberRelationships
     ?action=verifyQuotaAndCreateV2
     &decorationId=com.linkedin.voyager.dash.deco.relationships.InvitationCreationResultWithInvitee-2
```

### Direct Messages
```
POST https://www.linkedin.com/voyager/api/voyagerMessagingDashMessengerMessages
     ?action=createMessage
```

### Helper Endpoints (for messages)
```
GET https://www.linkedin.com/voyager/api/messaging/conversations
    ?q=participants&recipients=List({profile_id})

GET https://www.linkedin.com/voyager/api/feed/updatesV2
    ?commentsCount=0&count=1&likesCount=0&moduleKey=home-feed%3Adesktop
    &q=feed&sortOrder=MEMBER_SETTING&start=0
```

## Error Handling

All endpoints include comprehensive error handling:
- **API key validation errors** - 401/403 with appropriate message
- **LinkedIn session expired** - 401 with message "LinkedIn session expired or invalid. Please refresh your LinkedIn cookies and try again."
  - Occurs when profile ID cannot be extracted (usually means LinkedIn cookies are expired)
- **Duplicate connection request** - 409 with message "Connection request already sent to this profile. Please wait before sending again."
  - Occurs when attempting to send a connection request to someone you've already sent one to
  - Applies to both server_call and proxy modes
- **WebSocket connection errors (proxy mode)** - 404/503 with connection status
- **LinkedIn API errors (4xx, 5xx responses)** - 502 with LinkedIn error details
- **JSON parsing errors** - 500 with parsing error details
- **Network timeouts** - Appropriate timeout error
- **Invalid input validation** - 422 with validation details

## Logging

Extensive logging at INFO and ERROR levels:
- Request initiation with mode (SERVER_CALL/PROXY)
- API key validation
- WebSocket connection status
- LinkedIn API responses
- Success/failure outcomes

## Profile Identification

All endpoints accept **both** profile IDs and profile URLs:

- **Direct Profile ID**: `"john-doe-123"` 
- **Profile URL with vanity name**: `"https://www.linkedin.com/in/john-doe"`
- **Full profile URL**: `"https://www.linkedin.com/in/john-doe/"`

The system automatically extracts the profile ID from URLs using the `extract_profile_id` utility, which:
1. Checks if input is already a profile ID (returns as-is)
2. Extracts vanity name from URL pattern `/in/{vanity_name}`
3. Fetches the profile page and parses the profile ID from the HTML

## Testing

To test the endpoints:

### Simple Connection Request
```bash
# Using profile ID
curl -X POST http://localhost:8000/api/v1/connections/simple \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "john-doe-123",
    "api_key": "your-api-key"
  }'

# Using profile URL (server-side execution)
curl -X POST http://localhost:8000/api/v1/connections/simple \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "https://www.linkedin.com/in/john-doe",
    "api_key": "your-api-key",
    "server_call": true
  }'
```

### Connection Request with Message
```bash
# Using profile ID
curl -X POST http://localhost:8000/api/v1/connections/with-message \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "john-doe-123",
    "message": "Hi! I'd like to connect.",
    "api_key": "your-api-key"
  }'

# Using profile URL (server-side execution)
curl -X POST http://localhost:8000/api/v1/connections/with-message \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "https://www.linkedin.com/in/john-doe",
    "message": "Hi! I'd like to connect.",
    "api_key": "your-api-key",
    "server_call": true
  }'
```

### Send Direct Message
```bash
# Using profile ID
curl -X POST http://localhost:8000/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "john-doe-123",
    "message_text": "Hello! How are you?",
    "api_key": "your-api-key"
  }'

# Using profile URL (server-side execution)
curl -X POST http://localhost:8000/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "https://www.linkedin.com/in/john-doe",
    "message_text": "Hello! How are you?",
    "api_key": "your-api-key",
    "server_call": true
  }'
```

## Architecture Pattern

The implementation follows the established hexagonal architecture:

```
Client Request
    ↓
API Endpoint (connections.py / messages.py)
    ↓
Service Layer (LinkedInConnectionService / LinkedInMessageService)
    ↓
Base Service (LinkedInServiceBase)
    ↓
LinkedIn API (via httpx or WebSocket proxy)
```

This maintains clean separation of concerns and allows for easy testing and modification.

