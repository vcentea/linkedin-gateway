//@ts-check
/// <reference types="chrome"/>

/**
 * Gemini Controller for handling Gemini AI credential management
 * 
 * Credentials are obtained via local scripts (PowerShell/Bash) that handle
 * OAuth with localhost redirects, then submit to our backend.
 * 
 * This controller handles:
 * - Checking credential status from backend
 * - Storing credentials locally (for caching) - scoped per server/user
 * - Refreshing tokens when needed
 * - Syncing credentials with backend
 * 
 * @fileoverview Gemini controller for background service
 */

import { MESSAGE_TYPES } from '../../shared/constants/message-types.js';
import { 
  GEMINI_CLIENT_ID,
  GEMINI_CLIENT_SECRET,
  GOOGLE_TOKEN_URL,
  GEMINI_STATUS,
  TOKEN_REFRESH_BUFFER_SECONDS
} from '../../shared/constants/gemini-constants.js';
import { logger } from '../../shared/utils/logger.js';
import { createError } from '../../shared/utils/error-handler.js';
import * as authService from '../services/auth.service.js';
import { getAuthData } from '../services/storage.service.js';

// Storage key for per-server/per-user Gemini credentials
const GEMINI_CREDENTIALS_STORAGE_KEY = 'server_gemini_credentials';

// Use globalThis.chrome in service worker context
const chrome = globalThis.chrome;

// Current Gemini status
let currentStatus = GEMINI_STATUS.NOT_CONNECTED;

/**
 * Get current server URL for storage scoping
 * @returns {Promise<string>} Current server URL
 */
async function getCurrentServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['serverType', 'customApiUrl'], (result) => {
      const serverType = result.serverType || 'MAIN';
      const apiUrl = serverType === 'CUSTOM' 
        ? (result.customApiUrl || 'https://lg.ainnovate.tech')
        : 'https://lg.ainnovate.tech';
      resolve(apiUrl);
    });
  });
}

/**
 * Get current user ID for storage scoping
 * @returns {Promise<string|null>} Current user ID or null
 */
async function getCurrentUserId() {
  try {
    const authData = await getAuthData();
    return authData.userId || null;
  } catch {
    return null;
  }
}

/**
 * Initializes the Gemini controller
 * Checks for existing credentials and validates them
 */
export async function init() {
  logger.info('Initializing Gemini Controller', 'gemini.controller');
  
  // Check for existing credentials on startup
  try {
    const credentials = await getStoredCredentials();
    if (credentials && credentials.refresh_token) {
      // Validate/refresh credentials
      await validateAndRefreshCredentials(credentials);
    } else {
      currentStatus = GEMINI_STATUS.NOT_CONNECTED;
    }
  } catch (error) {
    logger.error(`Error during Gemini init: ${error}`, 'gemini.controller');
    currentStatus = GEMINI_STATUS.NOT_CONNECTED;
  }
}

/**
 * Handles messages related to Gemini
 * 
 * @param {Object} message - The received message
 * @param {Function} sendResponse - Function to send response back
 * @returns {boolean} - True if message was handled
 */
export function handleMessage(message, sendResponse) {
  if (!message || !message.type) {
    return false;
  }
  
  switch (message.type) {
    case MESSAGE_TYPES.CHECK_GEMINI_AUTH:
      handleCheckGeminiAuth(sendResponse);
      return true;
      
    case MESSAGE_TYPES.GET_GEMINI_STATUS:
      handleGetGeminiStatus(sendResponse);
      return true;
      
    case MESSAGE_TYPES.UPDATE_GEMINI_CREDENTIALS:
      handleUpdateGeminiCredentials(message.data, sendResponse);
      return true;
      
    case MESSAGE_TYPES.DISCONNECT_GEMINI:
      handleDisconnectGemini(sendResponse);
      return true;
      
    default:
      return false;
  }
}

/**
 * Handles request to check Gemini authentication status
 * 
 * @param {Function} sendResponse - Function to send response back
 */
async function handleCheckGeminiAuth(sendResponse) {
  try {
    const credentials = await getStoredCredentials();
    
    if (!credentials || !credentials.refresh_token) {
      sendResponse({ 
        authenticated: false, 
        status: GEMINI_STATUS.NOT_CONNECTED 
      });
      return;
    }
    
    // Check if token is expired or about to expire
    const isValid = await validateAndRefreshCredentials(credentials);
    
    sendResponse({
      authenticated: isValid,
      status: currentStatus,
      email: credentials.user_email
    });
  } catch (error) {
    logger.error(`Error checking Gemini auth: ${error}`, 'gemini.controller');
    sendResponse({ 
      authenticated: false, 
      status: GEMINI_STATUS.ERROR,
      error: error.message 
    });
  }
}

/**
 * Handle get Gemini status request
 * Checks backend for credentials via API key info and syncs with local storage
 * 
 * FIX: Properly syncs when backend has empty/different credentials
 * Handles both 'access_token' and 'token' field names for compatibility
 * 
 * @param {Function} sendResponse - Function to send response back
 */
async function handleGetGeminiStatus(sendResponse) {
  try {
    // First check local storage
    let credentials = await getStoredCredentials();
    
    // Also check backend (credentials might have been added via script or be different)
    try {
      const apiKeyResult = await authService.getApiKey();
      
      if (apiKeyResult.success && apiKeyResult.keyExists) {
        const backendCreds = apiKeyResult.apiKeyInfo?.gemini_credentials;
        
        // Check if backend has valid credentials (can use either access_token, token, or refresh_token)
        const hasBackendCreds = backendCreds && typeof backendCreds === 'object' && Object.keys(backendCreds).length > 0;
        const backendHasValidCreds = hasBackendCreds && (backendCreds.access_token || backendCreds.token || backendCreds.refresh_token);
        
        // Sync logic: Ensure local storage matches backend
        if (backendHasValidCreds) {
          // Backend has credentials
          const backendEmail = backendCreds.user_email;
          const localEmail = credentials?.user_email;
          
          // Update local if backend has different credentials or local is empty
          if (!credentials || localEmail !== backendEmail) {
            logger.info(`Syncing Gemini credentials from backend (backend: ${backendEmail}, local: ${localEmail})`, 'gemini.controller');
            // Normalize: ensure access_token field exists
            if (!backendCreds.access_token && backendCreds.token) {
              backendCreds.access_token = backendCreds.token;
            }
            credentials = backendCreds;
            await storeCredentials(credentials);
          }
        } else if (hasBackendCreds) {
          // Backend has credentials object but it's empty or invalid
          // This shouldn't normally happen, but log it for debugging
          logger.warn(`Backend has empty/invalid gemini_credentials: ${JSON.stringify(backendCreds)}`, 'gemini.controller');
          // Don't clear local if we have valid local credentials
          if (!credentials?.refresh_token) {
            await clearCredentials();
            credentials = null;
          }
        } else {
          // Backend has NO credentials at all - clear local if it has stale data
          if (credentials && credentials.refresh_token) {
            logger.info('Backend has no Gemini credentials, clearing local cache', 'gemini.controller');
            await clearCredentials();
            credentials = null;
          }
        }
      }
    } catch (e) {
      logger.warn(`Could not fetch backend credentials: ${e.message}`, 'gemini.controller');
    }
    
    if (!credentials || !credentials.refresh_token) {
      currentStatus = GEMINI_STATUS.NOT_CONNECTED;
      sendResponse({
        enabled: false,
        status: GEMINI_STATUS.NOT_CONNECTED,
        timestamp: Date.now()
      });
      return;
    }
    
    // Validate credentials
    const isValid = await validateAndRefreshCredentials(credentials);
    
    sendResponse({
      enabled: isValid,
      status: currentStatus,
      email: credentials.user_email,
      timestamp: Date.now()
    });
  } catch (error) {
    logger.error(`Error getting Gemini status: ${error.message}`, 'gemini.controller');
    sendResponse({
      enabled: false,
      status: GEMINI_STATUS.ERROR,
      error: error.message,
      timestamp: Date.now()
    });
  }
}

/**
 * Validate credentials and refresh if needed
 * 
 * @param {Object} credentials - Stored credentials
 * @returns {Promise<boolean>} True if credentials are valid
 */
async function validateAndRefreshCredentials(credentials) {
  currentStatus = GEMINI_STATUS.VALIDATING;
  
  try {
        if (!credentials.refresh_token) {
          logger.error('No refresh token available', 'gemini.controller');
          currentStatus = GEMINI_STATUS.ERROR;
          return false;
        }
        
    // Check expiry
    const expiry = credentials.expiry_date 
      ? new Date(credentials.expiry_date) 
      : (credentials.expiry ? new Date(credentials.expiry) : new Date(0));
    
    const now = new Date();
    const bufferMs = TOKEN_REFRESH_BUFFER_SECONDS * 1000;
    
    if (expiry.getTime() - now.getTime() < bufferMs) {
      logger.info('Token expired or expiring soon, refreshing...', 'gemini.controller');
      
      // Refresh the token
        const newTokens = await refreshAccessToken(credentials.refresh_token);
        
        // Update credentials
      credentials.access_token = newTokens.access_token;
      credentials.token = newTokens.access_token; // Legacy field
      credentials.expiry_date = Date.now() + (newTokens.expires_in * 1000);
      credentials.expiry = new Date(credentials.expiry_date).toISOString();
        
        // Store updated credentials
        await storeCredentials(credentials);
        
        // Sync to backend
        await syncCredentialsToBackend(credentials);
        
      logger.info('Token refreshed successfully', 'gemini.controller');
      }
      
      currentStatus = GEMINI_STATUS.CONNECTED;
      return true;
    
  } catch (error) {
    logger.error(`Token validation/refresh failed: ${error.message}`, 'gemini.controller');
    currentStatus = GEMINI_STATUS.ERROR;
    return false;
  }
}

/**
 * Refresh access token using refresh token
 * 
 * @param {string} refreshToken - Refresh token
 * @returns {Promise<Object>} New token data
 */
async function refreshAccessToken(refreshToken) {
  logger.info('Refreshing access token...', 'gemini.controller');
  
  const response = await fetch(GOOGLE_TOKEN_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      refresh_token: refreshToken,
      client_id: GEMINI_CLIENT_ID,
      client_secret: GEMINI_CLIENT_SECRET,
      grant_type: 'refresh_token',
    }).toString()
  });
  
  if (!response.ok) {
    const errorData = await response.text();
    throw createError('TokenRefreshError', `Token refresh failed: ${errorData}`, 'gemini.controller');
  }
  
  return response.json();
}

/**
 * Handle update Gemini credentials request
 * 
 * @param {Object} data - Credentials data
 * @param {Function} sendResponse - Function to send response back
 */
async function handleUpdateGeminiCredentials(data, sendResponse) {
  try {
    if (!data || !data.credentials) {
      throw createError('InvalidData', 'No credentials provided', 'gemini.controller');
    }
    
    await storeCredentials(data.credentials);
    await syncCredentialsToBackend(data.credentials);
    
    currentStatus = GEMINI_STATUS.CONNECTED;
    
    sendResponse({ success: true });
    broadcastStatusUpdate();
  } catch (error) {
    logger.error(`Error updating credentials: ${error.message}`, 'gemini.controller');
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Handle disconnect Gemini request
 * 
 * @param {Function} sendResponse - Function to send response back
 */
async function handleDisconnectGemini(sendResponse) {
  try {
    // Clear local storage
    await clearCredentials();
    
    // Clear backend credentials (set to empty)
    await syncCredentialsToBackend({});
    
    currentStatus = GEMINI_STATUS.NOT_CONNECTED;
    
    sendResponse({ success: true });
    broadcastStatusUpdate();
  } catch (error) {
    logger.error(`Error disconnecting Gemini: ${error.message}`, 'gemini.controller');
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Store credentials in Chrome storage (scoped per server/user)
 * 
 * Storage structure: server_gemini_credentials[serverUrl][userId] = credentials
 * This ensures different users on the same browser don't share credentials
 * 
 * @param {Object} credentials - Credentials to store
 */
async function storeCredentials(credentials) {
  const serverUrl = await getCurrentServerUrl();
  const userId = await getCurrentUserId();
  
  if (!userId) {
    logger.warn('Cannot store Gemini credentials: No user logged in', 'gemini.controller');
    return;
  }
  
  return new Promise((resolve, reject) => {
    chrome.storage.local.get([GEMINI_CREDENTIALS_STORAGE_KEY], (result) => {
      const allServerCreds = result[GEMINI_CREDENTIALS_STORAGE_KEY] || {};
      
      // Initialize server object if needed
      if (!allServerCreds[serverUrl]) {
        allServerCreds[serverUrl] = {};
      }
      
      // Store credentials for this server + user
      allServerCreds[serverUrl][userId] = {
        ...credentials,
        lastValidated: Date.now()
      };
      
      chrome.storage.local.set({ [GEMINI_CREDENTIALS_STORAGE_KEY]: allServerCreds }, () => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        logger.info(`Gemini credentials stored for server: ${serverUrl}, user: ${userId}`, 'gemini.controller');
        resolve();
      });
    });
  });
}

/**
 * Get stored credentials from Chrome storage (scoped per server/user)
 * 
 * @returns {Promise<Object|null>} Stored credentials or null
 */
async function getStoredCredentials() {
  const serverUrl = await getCurrentServerUrl();
  const userId = await getCurrentUserId();
  
  if (!userId) {
    logger.info('No user logged in, no Gemini credentials to retrieve', 'gemini.controller');
    return null;
  }
  
  return new Promise((resolve) => {
    chrome.storage.local.get([GEMINI_CREDENTIALS_STORAGE_KEY], (result) => {
      const allServerCreds = result[GEMINI_CREDENTIALS_STORAGE_KEY] || {};
      const serverCreds = allServerCreds[serverUrl] || {};
      const userCreds = serverCreds[userId] || null;
      
      if (userCreds) {
        logger.info(`Found Gemini credentials for server: ${serverUrl}, user: ${userId}`, 'gemini.controller');
      }
      
      resolve(userCreds);
    });
  });
}

/**
 * Clear stored credentials for current server/user
 * Exported for use during logout
 */
export async function clearCredentials() {
  const serverUrl = await getCurrentServerUrl();
  const userId = await getCurrentUserId();
  
  return new Promise((resolve, reject) => {
    chrome.storage.local.get([GEMINI_CREDENTIALS_STORAGE_KEY], (result) => {
      const allServerCreds = result[GEMINI_CREDENTIALS_STORAGE_KEY] || {};
      
      // If we have a userId, only clear that user's credentials
      // If no userId (logged out), clear all credentials for this server
      if (userId && allServerCreds[serverUrl]) {
        delete allServerCreds[serverUrl][userId];
        // Clean up empty server objects
        if (Object.keys(allServerCreds[serverUrl]).length === 0) {
          delete allServerCreds[serverUrl];
        }
        logger.info(`Gemini credentials cleared for server: ${serverUrl}, user: ${userId}`, 'gemini.controller');
      } else if (allServerCreds[serverUrl]) {
        // No user context - clear all for this server (logout scenario)
        delete allServerCreds[serverUrl];
        logger.info(`Gemini credentials cleared for server: ${serverUrl} (all users)`, 'gemini.controller');
      }
      
      chrome.storage.local.set({ [GEMINI_CREDENTIALS_STORAGE_KEY]: allServerCreds }, () => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        resolve();
      });
    });
  });
}

/**
 * Sync credentials to backend
 * 
 * @param {Object} credentials - Credentials to sync
 */
async function syncCredentialsToBackend(credentials) {
  try {
    // Check if user has API key
    const apiKeyResult = await authService.getApiKey();
    
    if (!apiKeyResult.success || !apiKeyResult.keyExists) {
      logger.info('No API key found, skipping Gemini credentials sync', 'gemini.controller');
      return;
    }
    
    // Update Gemini credentials in backend
    const updateResult = await authService.updateGeminiCredentials(credentials);
    
    if (updateResult.success) {
      logger.info('Gemini credentials synced to backend', 'gemini.controller');
    } else {
      logger.warn(`Failed to sync Gemini credentials: ${updateResult.error}`, 'gemini.controller');
    }
  } catch (error) {
    logger.error(`Error syncing Gemini credentials: ${error.message}`, 'gemini.controller');
  }
}

/**
 * Broadcast status update to all extension pages
 */
function broadcastStatusUpdate() {
  chrome.runtime.sendMessage({
    type: MESSAGE_TYPES.GEMINI_STATUS_UPDATE,
    data: {
      status: currentStatus,
      timestamp: Date.now()
    }
  }).catch(() => {
    // Ignore errors if no listeners
  });
}

/**
 * Get current Gemini status
 * 
 * @returns {string} Current status
 */
export function getCurrentStatus() {
  return currentStatus;
}

/**
 * Export for external validation triggers
 */
export async function checkAndRefreshCredentials() {
  const credentials = await getStoredCredentials();
  if (credentials && credentials.refresh_token) {
    return validateAndRefreshCredentials(credentials);
  }
  return false;
}

/**
 * Trigger a full Gemini status refresh and broadcast update
 * Called after API key operations (generate/delete) to sync UI
 * 
 * IMPORTANT: This function fetches from backend FIRST before modifying local storage.
 * This prevents data loss if the backend fetch fails or returns unexpected data.
 * 
 * @returns {Promise<{enabled: boolean, email?: string}>} Current status
 */
export async function triggerStatusRefresh() {
  logger.info('Triggering Gemini status refresh after API key operation', 'gemini.controller');
  
  try {
    // Get current local credentials BEFORE doing anything
    const localCredentials = await getStoredCredentials();
    
    // Fetch from backend first (don't clear local yet!)
    let credentials = null;
    let backendFetchSucceeded = false;
    
    try {
      const apiKeyResult = await authService.getApiKey();
      logger.info(`Backend API key fetch result: success=${apiKeyResult.success}, keyExists=${apiKeyResult.keyExists}`, 'gemini.controller');
      
      if (apiKeyResult.success && apiKeyResult.keyExists) {
        backendFetchSucceeded = true;
        const backendCreds = apiKeyResult.apiKeyInfo?.gemini_credentials;
        
        // Log what we received from backend for debugging
        const hasBackendCreds = backendCreds && typeof backendCreds === 'object' && Object.keys(backendCreds).length > 0;
        const hasAccessToken = backendCreds?.access_token || backendCreds?.token;
        logger.info(`Backend gemini_credentials: exists=${hasBackendCreds}, hasAccessToken=${!!hasAccessToken}, email=${backendCreds?.user_email || 'none'}`, 'gemini.controller');
        
        if (hasBackendCreds && hasAccessToken) {
          // Backend has valid credentials - use them
          credentials = backendCreds;
          // Normalize: ensure access_token field exists (some formats use 'token')
          if (!credentials.access_token && credentials.token) {
            credentials.access_token = credentials.token;
          }
          await storeCredentials(credentials);
          currentStatus = GEMINI_STATUS.CONNECTED;
          logger.info(`Gemini credentials synced from backend: ${credentials.user_email}`, 'gemini.controller');
        } else if (hasBackendCreds) {
          // Backend has credentials object but no access_token - might need refresh
          // Keep local credentials if they exist and have refresh_token
          if (localCredentials?.refresh_token) {
            logger.info('Backend credentials incomplete, keeping local credentials with refresh_token', 'gemini.controller');
            credentials = localCredentials;
            currentStatus = GEMINI_STATUS.CONNECTED;
          } else {
            currentStatus = GEMINI_STATUS.NOT_CONNECTED;
            await clearCredentials();
          }
        } else {
          // Backend has NO credentials - clear local to stay in sync
          logger.info('Backend has no Gemini credentials, clearing local', 'gemini.controller');
          await clearCredentials();
          currentStatus = GEMINI_STATUS.NOT_CONNECTED;
        }
      } else if (apiKeyResult.success && !apiKeyResult.keyExists) {
        // No API key exists - clear credentials
        backendFetchSucceeded = true;
        logger.info('No API key exists, clearing Gemini credentials', 'gemini.controller');
        await clearCredentials();
        currentStatus = GEMINI_STATUS.NOT_CONNECTED;
      } else {
        // API call failed - keep local credentials intact
        logger.warn(`Backend API key fetch failed: ${apiKeyResult.error}`, 'gemini.controller');
        credentials = localCredentials;
        if (credentials?.refresh_token) {
          currentStatus = GEMINI_STATUS.CONNECTED;
        } else {
          currentStatus = GEMINI_STATUS.NOT_CONNECTED;
        }
      }
    } catch (e) {
      // Fetch error - keep local credentials intact to avoid data loss
      logger.warn(`Could not fetch backend credentials during refresh: ${e.message}`, 'gemini.controller');
      credentials = localCredentials;
      if (credentials?.refresh_token) {
        currentStatus = GEMINI_STATUS.CONNECTED;
      } else {
        currentStatus = GEMINI_STATUS.NOT_CONNECTED;
      }
    }
    
    // Build result
    const result = {
      enabled: currentStatus === GEMINI_STATUS.CONNECTED,
      status: currentStatus,
      email: credentials?.user_email,
      timestamp: Date.now()
    };
    
    // Broadcast detailed status update
    chrome.runtime.sendMessage({
      type: MESSAGE_TYPES.GEMINI_STATUS_UPDATE,
      data: result
    }).catch(() => {
      // Ignore errors if no listeners
    });
    
    logger.info(`Gemini status refresh complete: ${currentStatus}, email=${credentials?.user_email || 'none'}`, 'gemini.controller');
    return result;
  } catch (error) {
    logger.error(`Error during Gemini status refresh: ${error.message}`, 'gemini.controller');
    currentStatus = GEMINI_STATUS.ERROR;
    return { enabled: false, status: GEMINI_STATUS.ERROR };
  }
}
