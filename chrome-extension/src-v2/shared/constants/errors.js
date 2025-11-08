//@ts-check

/**
 * Error constants for the application
 * 
 * @fileoverview Defines error types, codes, and messages used throughout the extension
 * This file will be expanded as error handling is consolidated
 */

/**
 * Error types categorized by domain
 * @readonly
 * @enum {string}
 */
export const ERROR_TYPES = {
  /** Authentication-related errors */
  AUTH: 'auth_error',
  
  /** Network request errors */
  NETWORK: 'network_error',
  
  /** WebSocket connection errors */
  WEBSOCKET: 'websocket_error',
  
  /** LinkedIn API/scraping errors */
  LINKEDIN: 'linkedin_error',
  
  /** Input validation errors */
  VALIDATION: 'validation_error',
  
  /** Unknown/uncategorized errors */
  UNKNOWN: 'unknown_error'
};

/**
 * Error messages for common errors
 * @readonly
 * @enum {string}
 */
export const ERROR_MESSAGES = {
  // Auth errors
  TOKEN_EXPIRED: 'Authentication token has expired',
  NOT_AUTHENTICATED: 'Not authenticated',
  
  // Network errors
  NETWORK_OFFLINE: 'Network connection is offline',
  REQUEST_TIMEOUT: 'Request timed out',
  
  // WebSocket errors
  WS_CONNECTION_FAILED: 'WebSocket connection failed',
  WS_CONNECTION_CLOSED: 'WebSocket connection closed unexpectedly',
  
  // LinkedIn errors
  NOT_LOGGED_IN: 'Not logged into LinkedIn',
  SCRAPING_FAILED: 'Failed to scrape data from LinkedIn',
  
  // Generic
  UNKNOWN_ERROR: 'An unknown error occurred'
}; 