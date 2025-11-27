//@ts-check

/**
 * Constants for Gemini AI integration
 * 
 * @fileoverview Defines OAuth configuration and constants for Google/Gemini authentication.
 * Uses the SAME OAuth credentials as the official Gemini CLI - this ensures users get their OWN
 * project and quota, not tied to our extension's project.
 * 
 * IMPORTANT: These credentials are INTENTIONALLY PUBLIC
 * Desktop OAuth apps require embedded client credentials (this is Google's design).
 * The Gemini CLI itself uses these same credentials publicly.
 * 
 * @see https://github.com/gzzhongqi/geminicli2api - Source of these public credentials
 */

/**
 * Google OAuth 2.0 Client ID from Gemini CLI
 * This is a PUBLIC client that ensures tokens are tied to USER's project
 * gitleaks:allow - Intentionally public OAuth credential from Gemini CLI
 * @type {string}
 */
export const GEMINI_CLIENT_ID = '681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com';

/**
 * Google OAuth 2.0 Client Secret from Gemini CLI  
 * This is a PUBLIC secret (desktop apps require it for token exchange)
 * gitleaks:allow - Intentionally public OAuth credential from Gemini CLI
 * @type {string}
 */
export const GEMINI_CLIENT_SECRET = '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';

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

