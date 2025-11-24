//@ts-check
/// <reference types="chrome"/>

/**
 * Storage Service for managing state and data persistence
 * 
 * This service provides a centralized interface for all storage operations,
 * including Chrome's local and session storage as well as runtime state management.
 * It wraps the existing storage utilities for improved organization and type safety.
 * 
 * @fileoverview Storage service implementation
 */

import { 
  getLocalStorage, 
  setLocalStorage, 
  removeLocalStorage,
  getSessionStorage,
  setSessionStorage,
  removeSessionStorage
} from '../../shared/utils/storage.utils.js';
import { STORAGE_KEYS } from '../../shared/constants/storage-keys.js';
import { logger } from '../../shared/utils/logger.js';
import { handleError } from '../../shared/utils/error-handler.js';

// In-memory runtime state
const runtimeState = new Map();

/**
 * Get an item from runtime state
 * @param {string} key - The key to retrieve
 * @param {any} [defaultValue=null] - Default value if key doesn't exist
 * @returns {any} The stored value or defaultValue
 */
export function getRuntimeState(key, defaultValue = null) {
  logger.info(`Getting runtime state: ${key}`, 'storage.service');
  return runtimeState.has(key) ? runtimeState.get(key) : defaultValue;
}

/**
 * Set an item in runtime state
 * @param {string} key - The key to set
 * @param {any} value - The value to store
 */
export function setRuntimeState(key, value) {
  logger.info(`Setting runtime state: ${key}`, 'storage.service');
  runtimeState.set(key, value);
}

/**
 * Remove an item from runtime state
 * @param {string} key - The key to remove
 * @returns {boolean} True if item existed and was removed
 */
export function removeRuntimeState(key) {
  logger.info(`Removing runtime state: ${key}`, 'storage.service');
  return runtimeState.delete(key);
}

/**
 * Clear all runtime state
 */
export function clearRuntimeState() {
  logger.info('Clearing all runtime state', 'storage.service');
  runtimeState.clear();
}

/**
 * Get current server URL
 * @returns {Promise<string>} Current server URL
 */
async function getCurrentServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['serverType', 'customApiUrl'], (result) => {
      const serverType = result.serverType || 'MAIN';
      let apiUrl;
      
      if (serverType === 'CUSTOM') {
        apiUrl = result.customApiUrl || 'https://lg.ainnovate.tech';
      } else {
        apiUrl = 'https://lg.ainnovate.tech'; // MAIN server
      }
      
      resolve(apiUrl);
    });
  });
}

/**
 * Get authentication data from storage for current server
 * @returns {Promise<{accessToken: string|null, userId: string|null, tokenExpiresAt: number|null}>} Authentication data
 */
export async function getAuthData() {
  try {
    logger.info('Getting auth data from storage', 'storage.service');
    
    // Get current server URL
    const serverUrl = await getCurrentServerUrl();
    logger.info(`Getting auth data for server: ${serverUrl}`, 'storage.service');
    
    // Get all server auth data
    const allServerAuth = await getLocalStorage('server_auth_data', {});
    
    // Get auth data for current server
    const serverAuth = allServerAuth[serverUrl] || {};
    
    // Fallback: Check for legacy single-token storage (migrate if found)
    if (!serverAuth.accessToken) {
      const legacyToken = await getLocalStorage(STORAGE_KEYS.ACCESS_TOKEN, null);
      const legacyUserId = await getLocalStorage(STORAGE_KEYS.USER_ID, null);
      const legacyExpires = await getLocalStorage(STORAGE_KEYS.TOKEN_EXPIRES_AT, null);
      
      if (legacyToken) {
        logger.info('Migrating legacy auth data to per-server storage', 'storage.service');
        // Migrate to new structure
        await saveAuthData(legacyToken, legacyUserId, legacyExpires);
        // Clean up old storage
        await removeLocalStorage(STORAGE_KEYS.ACCESS_TOKEN);
        await removeLocalStorage(STORAGE_KEYS.USER_ID);
        await removeLocalStorage(STORAGE_KEYS.TOKEN_EXPIRES_AT);
        
        return { accessToken: legacyToken, userId: legacyUserId, tokenExpiresAt: legacyExpires };
      }
    }
    
    return {
      accessToken: serverAuth.accessToken || null,
      userId: serverAuth.userId || null,
      tokenExpiresAt: serverAuth.tokenExpiresAt || null
    };
  } catch (error) {
    handleError(error, 'storage.service.getAuthData');
    logger.error(`Error getting auth data: ${error.message}`, 'storage.service');
    return { accessToken: null, userId: null, tokenExpiresAt: null };
  }
}

/**
 * Save authentication data to storage for current server
 * @param {string} accessToken - The access token
 * @param {string} userId - The user ID
 * @param {number} expiresAt - Token expiration timestamp
 * @returns {Promise<boolean>} True if successful
 */
export async function saveAuthData(accessToken, userId, expiresAt) {
  try {
    // Get current server URL
    const serverUrl = await getCurrentServerUrl();
    logger.info(`Saving auth data for server: ${serverUrl}`, 'storage.service');
    
    // Get existing server auth data
    const allServerAuth = await getLocalStorage('server_auth_data', {});
    
    // Update auth data for current server
    allServerAuth[serverUrl] = {
      accessToken,
      userId,
      tokenExpiresAt: expiresAt,
      savedAt: Date.now()
    };
    
    // Save back to storage
    await setLocalStorage('server_auth_data', allServerAuth);
    
    logger.info(`Auth data saved successfully for ${serverUrl}`, 'storage.service');
    return true;
  } catch (error) {
    handleError(error, 'storage.service.saveAuthData');
    logger.error(`Error saving auth data: ${error.message}`, 'storage.service');
    return false;
  }
}

/**
 * Clear authentication data from storage for current server only
 * @returns {Promise<boolean>} True if successful
 */
export async function clearAuthData() {
  try {
    // Get current server URL
    const serverUrl = await getCurrentServerUrl();
    logger.info(`Clearing auth data for server: ${serverUrl}`, 'storage.service');

    // Get existing server auth data
    const allServerAuth = await getLocalStorage('server_auth_data', {});

    // Remove auth data for current server
    delete allServerAuth[serverUrl];

    // Save back to storage
    await setLocalStorage('server_auth_data', allServerAuth);

    // NOTE: DO NOT clear API key info on logout!
    // API keys should persist across login/logout cycles so users don't lose their keys
    // Each user's API keys are stored separately (server > user > key)
    // When they log back in, their keys will still be available

    // Clear legacy single-token storage if it exists
    await removeLocalStorage(STORAGE_KEYS.ACCESS_TOKEN);
    await removeLocalStorage(STORAGE_KEYS.USER_ID);
    await removeLocalStorage(STORAGE_KEYS.TOKEN_EXPIRES_AT);
    await removeLocalStorage('authToken');
    await removeLocalStorage('userProfile');
    await removeLocalStorage('apiKey');
    await removeLocalStorage('user_id');
    await removeLocalStorage('token_expires_at');

    logger.info(`Auth data cleared for ${serverUrl}`, 'storage.service');
    return true;
  } catch (error) {
    handleError(error, 'storage.service.clearAuthData');
    logger.error(`Error clearing auth data: ${error.message}`, 'storage.service');
    return false;
  }
}

/**
 * Clear ALL authentication data for ALL servers (complete logout)
 * @returns {Promise<boolean>} True if successful
 */
export async function clearAllAuthData() {
  try {
    logger.info('Clearing ALL auth data for ALL servers', 'storage.service');
    
    // Clear all server auth data
    await removeLocalStorage('server_auth_data');
    
    // Clear all API key info
    await removeLocalStorage('server_api_keys');
    
    // Clear legacy storage
    await removeLocalStorage(STORAGE_KEYS.ACCESS_TOKEN);
    await removeLocalStorage(STORAGE_KEYS.USER_ID);
    await removeLocalStorage(STORAGE_KEYS.TOKEN_EXPIRES_AT);
    await removeLocalStorage('authToken');
    await removeLocalStorage('userProfile');
    await removeLocalStorage('apiKey');
    await removeLocalStorage('user_id');
    await removeLocalStorage('token_expires_at');
    
    logger.info('All auth data cleared', 'storage.service');
    return true;
  } catch (error) {
    handleError(error, 'storage.service.clearAllAuthData');
    logger.error(`Error clearing all auth data: ${error.message}`, 'storage.service');
    return false;
  }
}

/**
 * Get a value from local storage
 * @param {string} key - Storage key
 * @param {any} [defaultValue=null] - Default value if key doesn't exist
 * @returns {Promise<any>} Stored value or default
 */
export async function getFromLocalStorage(key, defaultValue = null) {
  try {
    return await getLocalStorage(key, defaultValue);
  } catch (error) {
    handleError(error, 'storage.service.getFromLocalStorage');
    logger.error(`Error getting from local storage: ${error.message}`, 'storage.service');
    return defaultValue;
  }
}

/**
 * Set a value in local storage
 * @param {string} key - Storage key
 * @param {any} value - Value to store
 * @returns {Promise<boolean>} True if successful
 */
export async function setToLocalStorage(key, value) {
  try {
    await setLocalStorage(key, value);
    return true;
  } catch (error) {
    handleError(error, 'storage.service.setToLocalStorage');
    logger.error(`Error setting to local storage: ${error.message}`, 'storage.service');
    return false;
  }
}

/**
 * Remove a value from local storage
 * @param {string} key - Storage key to remove
 * @returns {Promise<boolean>} True if successful
 */
export async function removeFromLocalStorage(key) {
  try {
    await removeLocalStorage(key);
    return true;
  } catch (error) {
    handleError(error, 'storage.service.removeFromLocalStorage');
    logger.error(`Error removing from local storage: ${error.message}`, 'storage.service');
    return false;
  }
}

/**
 * Get a value from session storage
 * @param {string} key - Storage key
 * @param {any} [defaultValue=null] - Default value if key doesn't exist
 * @returns {Promise<any>} Stored value or default
 */
export async function getFromSessionStorage(key, defaultValue = null) {
  try {
    return await getSessionStorage(key, defaultValue);
  } catch (error) {
    handleError(error, 'storage.service.getFromSessionStorage');
    logger.error(`Error getting from session storage: ${error.message}`, 'storage.service');
    return defaultValue;
  }
}

/**
 * Set a value in session storage
 * @param {string} key - Storage key
 * @param {any} value - Value to store
 * @returns {Promise<boolean>} True if successful
 */
export async function setToSessionStorage(key, value) {
  try {
    await setSessionStorage(key, value);
    return true;
  } catch (error) {
    handleError(error, 'storage.service.setToSessionStorage');
    logger.error(`Error setting to session storage: ${error.message}`, 'storage.service');
    return false;
  }
}

/**
 * Remove a value from session storage
 * @param {string} key - Storage key to remove
 * @returns {Promise<boolean>} True if successful
 */
export async function removeFromSessionStorage(key) {
  try {
    await removeSessionStorage(key);
    return true;
  } catch (error) {
    handleError(error, 'storage.service.removeFromSessionStorage');
    logger.error(`Error removing from session storage: ${error.message}`, 'storage.service');
    return false;
  }
}

/**
 * Save API key info to storage for current server
 * Stores the key metadata including instance_id to ensure WebSocket sync
 * 
 * @param {Object} keyInfo - API key information
 * @param {string} keyInfo.key - The full API key (stored securely)
 * @param {string} keyInfo.id - The API key ID
 * @param {string} keyInfo.prefix - The API key prefix
 * @param {string} keyInfo.instance_id - The instance ID for this key
 * @returns {Promise<boolean>} True if successful
 */
export async function saveApiKeyInfo(keyInfo) {
  try {
    const serverUrl = await getCurrentServerUrl();

    // Get current user ID - CRITICAL for multi-user support
    const authData = await getAuthData();
    const userId = authData.userId;

    if (!userId) {
      logger.error('Cannot save API key info: No user logged in', 'storage.service');
      return false;
    }

    logger.info(`Saving API key info for server: ${serverUrl}, user: ${userId}`, 'storage.service');

    const allServerKeys = await getLocalStorage('server_api_keys', {});

    // Initialize server object if it doesn't exist
    if (!allServerKeys[serverUrl]) {
      allServerKeys[serverUrl] = {};
    }

    // Store key under server > user (multi-user support)
    allServerKeys[serverUrl][userId] = {
      key: keyInfo.key,
      id: keyInfo.id,
      prefix: keyInfo.prefix,
      instance_id: keyInfo.instance_id,
      savedAt: Date.now()
    };

    await setLocalStorage('server_api_keys', allServerKeys);

    // DO NOT overwrite the extension's own instanceId!
    // The extension's instanceId should be immutable after first generation
    // It represents THIS browser installation, not the backend's API key
    // Overwriting it breaks WebSocket routing and causes cross-user contamination

    logger.info(`API key info saved successfully for ${serverUrl}, user: ${userId}`, 'storage.service');
    return true;
  } catch (error) {
    handleError(error, 'storage.service.saveApiKeyInfo');
    logger.error(`Error saving API key info: ${error.message}`, 'storage.service');
    return false;
  }
}

/**
 * Get API key info from storage for current server and current user
 *
 * @returns {Promise<Object|null>} API key info or null if not found
 */
export async function getApiKeyInfo() {
  try {
    const serverUrl = await getCurrentServerUrl();

    // Get current user ID - CRITICAL for multi-user support
    const authData = await getAuthData();
    const userId = authData.userId;

    if (!userId) {
      logger.info('Cannot get API key info: No user logged in', 'storage.service');
      return null;
    }

    logger.info(`Getting API key info for server: ${serverUrl}, user: ${userId}`, 'storage.service');

    const allServerKeys = await getLocalStorage('server_api_keys', {});

    // Get key for current server and user
    const serverKeys = allServerKeys[serverUrl] || {};
    const keyInfo = serverKeys[userId] || null;

    if (keyInfo) {
      logger.info(`Found API key for user ${userId}`, 'storage.service');
    } else {
      logger.info(`No API key found for user ${userId}`, 'storage.service');
    }

    return keyInfo;
  } catch (error) {
    handleError(error, 'storage.service.getApiKeyInfo');
    logger.error(`Error getting API key info: ${error.message}`, 'storage.service');
    return null;
  }
}

/**
 * Clear API key info from storage for current server and current user
 *
 * @returns {Promise<boolean>} True if successful
 */
export async function clearApiKeyInfo() {
  try {
    const serverUrl = await getCurrentServerUrl();

    // Get current user ID - CRITICAL for multi-user support
    const authData = await getAuthData();
    const userId = authData.userId;

    if (!userId) {
      logger.info('Cannot clear API key info: No user logged in', 'storage.service');
      return false;
    }

    logger.info(`Clearing API key info for server: ${serverUrl}, user: ${userId}`, 'storage.service');

    const allServerKeys = await getLocalStorage('server_api_keys', {});

    // Clear key for current server and user only
    if (allServerKeys[serverUrl]) {
      delete allServerKeys[serverUrl][userId];

      // Clean up empty server objects
      if (Object.keys(allServerKeys[serverUrl]).length === 0) {
        delete allServerKeys[serverUrl];
      }
    }

    await setLocalStorage('server_api_keys', allServerKeys);

    logger.info(`API key info cleared for ${serverUrl}, user: ${userId}`, 'storage.service');
    return true;
  } catch (error) {
    handleError(error, 'storage.service.clearApiKeyInfo');
    logger.error(`Error clearing API key info: ${error.message}`, 'storage.service');
    return false;
  }
} 