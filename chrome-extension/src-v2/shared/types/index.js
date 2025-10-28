/**
 * @fileoverview Central export file for all type definitions
 * 
 * This file serves as the main entry point for importing type definitions
 * across the codebase. It re-exports all type definitions from individual
 * type files to allow for centralized imports.
 */

// Import and re-export Chrome API types
import './chrome.types.js';

// Export LinkedIn-specific types
export * from './linkedin.types.js';

// Export WebSocket-specific types (if they exist)
// Uncommenting this would require the file to exist
// export * from './websocket.types.js';

/**
 * @typedef {Object} SendMessageOptions
 * @property {string} type - The message type (from message-types.js constants)
 * @property {Object} [data] - Optional data payload for the message
 */

/**
 * @typedef {Object} ApiRequestOptions
 * @property {string} endpoint - The API endpoint to call
 * @property {string} [method='GET'] - HTTP method to use
 * @property {Object} [params] - Query parameters for GET requests
 * @property {Object} [data] - Request body for POST/PUT/PATCH requests
 * @property {Object} [headers] - Additional headers to send
 * @property {boolean} [requiresAuth=true] - Whether the request requires authentication
 */

/**
 * @typedef {Object} ApiResponseData
 * @property {boolean} success - Whether the API call was successful
 * @property {Object|Array} [data] - Response data if successful
 * @property {string} [message] - Success or error message
 * @property {number} [statusCode] - HTTP status code
 * @property {Object} [error] - Error details if unsuccessful
 */ 