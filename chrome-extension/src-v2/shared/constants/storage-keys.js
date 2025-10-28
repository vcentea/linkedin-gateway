//@ts-check

/**
 * Storage key constants for Chrome storage
 * 
 * @fileoverview Defines all storage keys used for the extension's chrome.storage APIs
 */

/**
 * Storage keys for Chrome storage
 * @readonly
 * @enum {string}
 */
export const STORAGE_KEYS = {
  /** Key for storing the auth access token */
  ACCESS_TOKEN: 'access_token',
  
  /** Key for storing the authenticated user ID */
  USER_ID: 'user_id',
  
  /** Key for storing the access token expiration timestamp */
  TOKEN_EXPIRES_AT: 'token_expires_at'
}; 