//@ts-check

/**
 * Type definitions for API-related data structures.
 * 
 * @fileoverview API type definitions that can be used with JSDoc annotations
 * for improved type safety and autocompletion.
 */

/**
 * API request options
 * @typedef {Object} ApiRequestOptions
 * @property {string} endpoint - API endpoint (without base URL)
 * @property {'GET'|'POST'|'PUT'|'DELETE'|'PATCH'} method - HTTP method
 * @property {Object.<string, string|number|boolean>} [params] - Query parameters
 * @property {Object} [body] - Request body for POST/PUT/PATCH
 * @property {Object.<string, string>} [headers] - Additional headers
 * @property {boolean} [requiresAuth=true] - Whether authorization is required
 * @property {number} [timeout] - Request timeout in milliseconds
 */

/**
 * API response
 * @template T
 * @typedef {Object} ApiResponse
 * @property {boolean} success - Whether the request was successful
 * @property {T} [data] - Response data if successful 
 * @property {Object} [error] - Error information if unsuccessful
 * @property {string} [error.message] - Error message
 * @property {number} [error.status] - HTTP status code
 * @property {string} [error.code] - Error code
 */

/**
 * API endpoint configuration
 * @typedef {Object} ApiEndpointConfig
 * @property {string} name - Display name
 * @property {string} endpoint - Endpoint path
 * @property {'GET'|'POST'|'PUT'|'DELETE'|'PATCH'} method - HTTP method
 * @property {string} [description] - Endpoint description
 * @property {Array<{name: string, description: string, required: boolean, type: string}>} [params] - Parameters
 * @property {boolean} [requiresAuth] - Whether authentication is required
 * @property {Array<string>} [pathParams] - Path parameters that will be replaced in endpoint
 * @property {string} [localTestUtility] - Name of function to use for local testing
 * @property {boolean} [requiresContentScript] - Whether content script is needed for testing
 */

/**
 * API configuration
 * @typedef {Object} ApiConfig
 * @property {string} API_URL - Base URL for the backend API
 * @property {Object.<string, string>} HEADERS - Default headers for API requests
 * @property {number} TIMEOUT - Default timeout for API requests in ms
 * @property {number} RETRY_ATTEMPTS - Number of retry attempts for failed requests
 * @property {number} RETRY_DELAY - Delay between retry attempts in ms
 */

// Export nothing - this file is only for JSDoc type definitions
export {}; 