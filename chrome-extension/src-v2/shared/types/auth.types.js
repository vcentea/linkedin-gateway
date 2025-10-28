//@ts-check

/**
 * Type definitions for authentication-related data structures.
 * 
 * @fileoverview Authentication type definitions that can be used with JSDoc annotations
 * for improved type safety and autocompletion.
 */

/**
 * Authentication data object for the logged-in user
 * @typedef {Object} AuthData
 * @property {string} [accessToken] - OAuth access token
 * @property {string} [userId] - User identifier
 * @property {number} [tokenExpiresAt] - Token expiration timestamp
 * @property {Object} [profile] - User profile data 
 * @property {string} [profile.id] - User ID from profile
 * @property {string} [profile.name] - User name
 * @property {string} [profile.email] - User email
 * @property {string} [profile.picture] - URL to profile picture
 */

/**
 * API Key data object
 * @typedef {Object} ApiKeyData
 * @property {string} key - The API key value
 * @property {string} [createdAt] - Creation timestamp
 * @property {string} [expiresAt] - Expiration timestamp
 * @property {boolean} [isActive] - Whether the key is currently active
 */

/**
 * Login credentials
 * @typedef {Object} LoginCredentials
 * @property {string} token - The authentication token
 * @property {string} userId - The user ID
 * @property {number} [expiresAt] - Token expiration timestamp
 */

/**
 * Authentication status response
 * @typedef {Object} AuthStatusResponse
 * @property {boolean} authenticated - Whether the user is authenticated
 * @property {Object} [userData] - User data if authenticated
 * @property {string} [error] - Error message if not authenticated
 */

// Export nothing - this file is only for JSDoc type definitions
export {}; 