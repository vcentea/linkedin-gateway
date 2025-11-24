# API Endpoints

This directory contains the API endpoints definition and utilities for making API calls.

## Structure

- `endpoints.json` - JSON file defining all API endpoints and their parameters
- `index.js` - API utility functions for making requests to the backend

## Future Improvements

Some potential improvements for the API endpoint definitions in `endpoints.json`:

1. **Group by Domain** - Organize endpoints by functional domain (auth, posts, profiles, etc.)
2. **Response Schema** - Add formal JSON schema for response validation instead of string examples
3. **Error Handling** - Add expected error codes and messages for each endpoint
4. **Version Control** - Include API version in the endpoint definition object
5. **Authentication Requirements** - Explicitly mark which endpoints require authentication
6. **Rate Limiting** - Include information about rate limiting for each endpoint
7. **Documentation Links** - Add links to more detailed documentation for each endpoint
8. **Deprecation Notices** - Add deprecation warnings for endpoints planned for retirement

## Current Endpoint Format

The current format for each endpoint is:

```json
{
  "name": "Human-readable name",
  "endpoint": "/api/path/to/endpoint",
  "method": "HTTP method (GET, POST, etc.)",
  "localTestUtility": "Optional function name for local testing",
  "params": [
    { 
      "name": "parameter_name",
      "type": "parameter type (text, number, etc.)",
      "required": true|false,
      "default": "default value if any",
      "description": "Parameter description"
    }
  ],
  "expectedResponse": "Example response format as a string"
}
``` 