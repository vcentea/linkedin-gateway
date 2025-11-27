//@ts-check

/**
 * Constants for Gemini AI integration
 * 
 * @fileoverview Defines OAuth configuration and constants for Google/Gemini authentication.
 * Gemini OAuth is optional - credentials should be configured via server settings if needed.
 * 
 * @see https://github.com/gzzhongqi/geminicli2api for public OAuth client credentials
 */

/**
 * Google OAuth 2.0 Client ID - loaded from server config
 * Leave empty - Gemini OAuth is handled server-side
 * @type {string}
 */
export const GEMINI_CLIENT_ID = '';

/**
 * Google OAuth 2.0 Client Secret - loaded from server config
 * Leave empty - Gemini OAuth is handled server-side
 * @type {string}
 */
export const GEMINI_CLIENT_SECRET = '';

/**
 * OAuth scopes required for Gemini API access
 * Matches official Gemini CLI exactly (including openid)
 * @type {string[]}
 */
export const GEMINI_SCOPES = [
  'https://www.googleapis.com/auth/cloud-platform',
  'https://www.googleapis.com/auth/userinfo.email',
  'https://www.googleapis.com/auth/userinfo.profile',
  'openid',
];

/**
 * Google OAuth 2.0 authorization URL
 * @type {string}
 */
export const GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth';

/**
 * Google OAuth 2.0 token exchange URL
 * @type {string}
 */
export const GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token';

/**
 * Storage keys for Gemini credentials
 * @readonly
 * @enum {string}
 */
export const GEMINI_STORAGE_KEYS = {
  /** Stored Gemini OAuth credentials */
  CREDENTIALS: 'gemini_credentials',
  /** Last time credentials were validated */
  LAST_VALIDATED: 'gemini_last_validated',
  /** User's Google email (for display) */
  USER_EMAIL: 'gemini_user_email',
  /** User's Google profile picture */
  USER_PICTURE: 'gemini_user_picture',
};

/**
 * Gemini connection status values
 * @readonly
 * @enum {string}
 */
export const GEMINI_STATUS = {
  /** Not connected - no credentials stored */
  NOT_CONNECTED: 'not_connected',
  /** Connected and credentials valid */
  CONNECTED: 'connected',
  /** Credentials exist but are expired (refresh needed) */
  EXPIRED: 'expired',
  /** Currently validating/refreshing credentials */
  VALIDATING: 'validating',
  /** Error state - credentials invalid or refresh failed */
  ERROR: 'error',
};

/**
 * How often to validate Gemini credentials (in milliseconds)
 * Same interval as LinkedIn for consistency
 * @type {number}
 */
export const GEMINI_VALIDATION_INTERVAL = 5 * 60 * 1000; // 5 minutes

/**
 * Token refresh buffer - refresh tokens this many seconds before expiry
 * @type {number}
 */
export const TOKEN_REFRESH_BUFFER_SECONDS = 300; // 5 minutes before expiry

