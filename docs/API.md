# LinkedIn Gateway API Documentation

## Authentication Endpoints

### Login
- **Endpoint**: `/auth/login`
- **Method**: `POST`
- **Description**: Authenticates a user with email and password
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

### Logout
- **Endpoint**: `/auth/logout`
- **Method**: `POST`
- **Description**: Invalidates a user's token
- **Headers**: `Authorization: Bearer {token}`
- **Response**: HTTP 204 No Content

## API Key Management

### Get API Key
- **Endpoint**: `/users/me/api-key`
- **Method**: `GET`
- **Description**: Retrieves information (metadata) about the user's active API key.
- **Headers**: `Authorization: Bearer {token}`
- **Response**:
  - **Success (200 OK - Key Exists)**:
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
    > **Note**: This response confirms an active key exists but **does not** include the secret part of the key.
  
  - **Not Found (404 - No Active Key)**:
    ```json
    {
      "detail": "No active API key found."
    }
    ```

### Generate API Key
- **Endpoint**: `/users/me/api-key`
- **Method**: `POST`
- **Description**: Creates a new API key (invalidates any existing key).
- **Headers**: `Authorization: Bearer {token}`
- **Optional Query Parameters**: `name` - A name for the API key.
- **Response (201 Created)**:
  ```json
  {
    "key": "LKG_prefix_secret", // Full key returned only upon creation
    "id": "key_id",
    "prefix": "prefix",
    "name": "Optional Key Name",
    "created_at": "2023-12-31T23:59:59Z",
    "is_active": true
  }
  ```
  > **IMPORTANT**: The full API key is ONLY returned in this response. Store it securely as you won't be able to retrieve it later.

### Delete API Key
- **Endpoint**: `/users/me/api-key`
- **Method**: `DELETE`
- **Description**: Deactivates the user's current API key.
- **Headers**: `Authorization: Bearer {token}`
- **Response**: HTTP 204 No Content

## Using API Keys

Once you have an API key, you can use it to authenticate API requests:

### Option 1: Header Authentication
Include the API key in the `X-API-Key` header:
```
X-API-Key: LKG_prefix_secret
```

### Option 2: Body Authentication
For POST requests, you can include the API key in the request body:
```json
{
  "api_key": "LKG_prefix_secret",
  "other_params": "..."
}
```

## API Key Errors

- **401 Unauthorized**: Invalid or expired API key
- **403 Forbidden**: API key doesn't have permission for the requested resource
- **404 Not Found**: No active API key found for the user

## API Key Format

API keys follow this format: `LKG_prefix_secret` where:
- `LKG_` is a fixed prefix for all keys
- `prefix` is a unique 16-character identifier (letters and numbers)
- `secret` is a longer string that should be kept confidential

Example: `LKG_a1b2c3d4e5f6g7h8_s3cr3tP4rtTh4tIsL0ng3rAndR4nd0m` 