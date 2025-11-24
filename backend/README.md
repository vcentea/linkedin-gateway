# LinkedIn Gateway Backend

This document provides information about the backend API endpoints used by the LinkedIn Gateway extension.

## API Endpoints

### Authentication

#### Login
- **Endpoint**: `/auth/login`
- **Method**: `POST`
- **Description**: Authenticates a user and returns a JWT token
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "password123"
  }
  ```
- **Response**:
  ```json
  {
    "access_token": "jwt_token_here",
    "token_type": "bearer",
    "id": "user_id",
    "name": "User Name",
    "email": "user@example.com",
    "profile_picture_url": "http://example.com/profile.jpg",
    "token_expires_at": "2023-12-31T23:59:59Z"
  }
  ```

#### Logout
- **Endpoint**: `/auth/logout`
- **Method**: `POST`
- **Description**: Logs out a user by invalidating their token
- **Headers**: Authorization: Bearer {token}
- **Response**: HTTP 204 No Content

### API Key Management

#### Get API Key
- **Endpoint**: `/users/me/api-key`
- **Method**: `GET`
- **Description**: Retrieves information about the user's active API key (metadata only).
- **Headers**: Authorization: Bearer {token}
- **Response**:
  - Success (200 OK - Key Exists):
    ```json
    {
      "id": "key_id",
      "prefix": "prefix",
      "name": "Optional Key Name",
      "created_at": "2023-12-31T23:59:59Z",
      "last_used_at": "2023-12-31T23:59:59Z", // Can be null
      "is_active": true
    }
    ```
    > **Note:** This response confirms an active key exists but **does not** include the secret part of the key.
  - Not Found (404 - No Active Key):
    ```json
    {
      "detail": "No active API key found."
    }
    ```

#### Generate API Key
- **Endpoint**: `/users/me/api-key`
- **Method**: `POST`
- **Description**: Generates a new API key for the user (deactivates any existing key).
- **Headers**: Authorization: Bearer {token}
- **Optional Query Parameter**: `name` (string) - An optional name for the key.
- **Response (201 Created)**:
  ```json
  {
    "key": "LKG_prefix_secret", // Full key is only returned upon creation
    "id": "key_id",
    "prefix": "prefix",
    "name": "Optional Key Name",
    "created_at": "2023-12-31T23:59:59Z",
    "is_active": true
  }
  ```
  > **IMPORTANT**: The full `key` string is ONLY returned in this response. Store it securely.

#### Delete API Key
- **Endpoint**: `/users/me/api-key`
- **Method**: `DELETE`
- **Description**: Deactivates the user's active API key.
- **Headers**: Authorization: Bearer {token}
- **Response**: HTTP 204 No Content

### User Management

#### Get User Profile
- **Endpoint**: `/me`
- **Method**: `GET`
- **Description**: Retrieves the current user's profile information.
- **Headers**: Authorization: Bearer {token}
- **Response**:
  ```json
  {
    "id": "user_id",
    "name": "User Name",
    "email": "user@example.com",
    "created_at": "2023-12-31T23:59:59Z",
    "profile_picture_url": "http://example.com/profile.jpg"
  }
  ```

### Post Management

#### Request Feed
- **Endpoint**: `/api/v1/posts/request-feed`
- **Method**: `POST`
- **Description**: Requests the LinkedIn feed through the extension.
- **Headers**: 
  - Authorization: Bearer {token} OR
  - X-API-Key: {api_key}
- **Request Body**:
  ```json
  {
    "start_index": 0,
    "count": 10
  }
  ```
- **Response**: Returns feed data with posts.

## Authentication Methods

The API supports two authentication methods:

1. **Bearer Token Authentication**: Used for browser extension communication.
   ```
   Authorization: Bearer {jwt_token}
   ```

2. **API Key Authentication**: Used for external applications.
   ```
   X-API-Key: LKG_prefix_secret
   ```

## WebSocket Endpoints

- **Endpoint**: `/ws/{user_id}`
- **Description**: WebSocket connection for real-time communication with the extension.
- **Authentication**: Requires a valid JWT token sent in the first message.

## Error Responses

All endpoints return standardized error responses:

```json
{
  "detail": "Error message describing the issue"
}
```

Common HTTP status codes:
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 422: Validation Error
- 500: Internal Server Error

## WebSocket Support

The backend includes real-time WebSocket functionality for persistent connections between the server and clients.

### WebSocket Endpoint

The main WebSocket endpoint is available at:

```
ws://your-api-host:port/ws
```

### Authentication

WebSocket connections require authentication with a JWT token. The connection flow is:

1. Connect to the WebSocket endpoint
2. Send an authentication message with your JWT token:
   ```json
   {
     "type": "auth",
     "token": "your.jwt.token"
   }
   ```
3. The server will respond with an auth success message if the token is valid:
   ```json
   {
     "type": "auth_success",
     "user_id": "your-user-id"
   }
   ```

### Message Types

The WebSocket implementation uses structured message types:

- `auth`: Authentication request
- `auth_success`: Successful authentication response
- `error`: Error message
- `ping/pong`: Keep-alive messages
- `notification`: User notifications
- `status_update`: Status change notifications
- `linkedin_event`: LinkedIn-related events

### Keep-Alive

The WebSocket connection uses a ping-pong mechanism to keep the connection alive. The client should send a ping message every 30 seconds:

```json
{
  "type": "ping"
}
```

The server will respond with:

```json
{
  "type": "pong"
}
```

### REST API for WebSocket Operations

The following REST endpoints are available for WebSocket operations:

- `GET /ws/status`: Get WebSocket connection statistics
- `POST /ws/notify/user/{user_id}`: Send a notification to a specific user
- `POST /ws/notify/broadcast`: Broadcast a notification to all connected users
- `POST /ws/notify/users`: Send a notification to multiple users 