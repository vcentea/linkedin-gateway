//@ts-check
/// <reference types="chrome"/>

/**
 * Auth Service for authentication operations
 * 
 * This service manages authentication state, token handling, and API key operations.
 * It provides an interface for the auth controller to interact with the backend API
 * and local storage.
 * 
 * @fileoverview Authentication service implementation
 */

import { fetchUserProfile, logoutBackend, getApiKey as apiGetApiKey, generateApiKey as apiGenerateApiKey, deleteApiKey as apiDeleteApiKey, updateCsrfToken as apiUpdateCsrfToken, updateLinkedInCookies as apiUpdateLinkedInCookies, updateGeminiCredentials as apiUpdateGeminiCredentials } from '../../shared/api/index.js';
import { getAuthData, clearAuthData, saveAuthData, saveApiKeyInfo, clearApiKeyInfo } from '../services/storage.service.js';
import { logger } from '../../shared/utils/logger.js';
import { handleError } from '../../shared/utils/error-handler.js';
import * as instanceService from './instance.service.js';
import * as websocketService from './websocket.service.js';
// Import linkedinController statically to avoid dynamic import issues in Service Worker
import * as linkedinController from '../controllers/linkedin.controller.js';
// Import Gemini controller for credential cleanup on logout and status refresh
import { clearCredentials as clearGeminiCredentials, triggerStatusRefresh as refreshGeminiStatus } from '../controllers/gemini.controller.js';

// User data cache
let userData = null;

/**
 * Checks if user is authenticated and fetches profile if they are
 * First tries the storage wrapper, then falls back to direct chrome.storage.local
 * 
 * @returns {Promise<{authenticated: boolean, userData?: Object, error?: string}>} Authentication status and user data
 */
export async function checkAuthAndGetProfile() {
    try {
        // Get auth data from storage (new per-server system)
        const { accessToken, userId, tokenExpiresAt } = await getAuthData();
        
        logger.info('Auth data from storage:', 'auth.service');
        logger.info(`- accessToken: ${accessToken ? 'exists' : 'missing'}`, 'auth.service');
        logger.info(`- userId: ${userId ? 'exists' : 'missing'}`, 'auth.service');
        logger.info(`- tokenExpiresAt: ${tokenExpiresAt ? 'exists' : 'missing'}`, 'auth.service');
        
        // Check if token exists (let backend validate expiration)
        if (!accessToken) {
            logger.info('No valid token found via getAuthData', 'auth.service');

            // Try direct storage access as fallback
            return new Promise((resolve) => {
                chrome.storage.local.get(['access_token'], async (result) => {
                    if (result.access_token) {
                        logger.info('Found valid token via direct storage', 'auth.service');
                        try {
                            const fetchedUserData = await fetchUserProfile(result.access_token);
                            userData = fetchedUserData; // Cache user data
                            resolve({ authenticated: true, userData: fetchedUserData, accessToken: result.access_token });
                            return;
                        } catch (error) {
                            logger.error(`Error with direct token: ${error.message}`, 'auth.service');
                        }
                    }
                    logger.info('No valid token found in either method', 'auth.service');
                    resolve({ authenticated: false });
                });
            });
        }
        
        // Fetch user profile from backend
        const fetchedUserData = await fetchUserProfile(accessToken);
        userData = fetchedUserData; // Cache user data
        return { 
            authenticated: true,
            userData: fetchedUserData,
            accessToken: accessToken
        };
    } catch (error) {
        handleError(error, 'auth.service.checkAuthAndGetProfile');
        logger.error(`Auth check failed: ${error.message}`, 'auth.service');
        // If error is 401, clear auth data
        if (error.message && error.message.includes('401')) {
            await clearAuthData();
        }
        return { authenticated: false, error: error.message };
    }
}

/**
 * Handle user logout
 * Logs out from the backend API and clears local storage
 * Also clears Gemini credentials to prevent cross-user credential leakage
 * 
 * @returns {Promise<{success: boolean, backendError?: string}>} Logout result
 */
export async function performLogout() {
    try {
        // Get current token
        const { accessToken } = await getAuthData();
        
        // Close WebSocket connection before logout
        try {
            logger.info('Closing WebSocket connection on logout', 'auth.service');
            websocketService.closeWebSocket(false); // Don't clear server URL, just close connection
        } catch (wsError) {
            logger.warn(`Could not close WebSocket on logout: ${wsError.message}`, 'auth.service');
        }
        
        // Clear Gemini credentials BEFORE clearing auth data
        // This must happen while we still have userId context
        try {
            logger.info('Clearing Gemini credentials on logout', 'auth.service');
            await clearGeminiCredentials();
        } catch (geminiError) {
            logger.warn(`Could not clear Gemini credentials: ${geminiError.message}`, 'auth.service');
        }
        
        // Send logout request to backend if token exists
        if (accessToken) {
            await logoutBackend(accessToken);
        }
        
        // Always clear local storage
        await clearAuthData();
        userData = null; // Clear cached user data
        
        return { success: true };
    } catch (error) {
        handleError(error, 'auth.service.performLogout');
        logger.error(`Logout error: ${error.message}`, 'auth.service');
        // Still try to clear storage
        try {
            await clearGeminiCredentials();
        } catch (e) {
            // Ignore
        }
        await clearAuthData();
        userData = null; // Clear cached user data
        return { success: true, backendError: error.message };
    }
}

/**
 * Get API Key from backend
 * 
 * @returns {Promise<{success: boolean, keyExists: boolean, error?: string}>} API key result
 */
export async function getApiKey() {
    const logContext = 'auth.service:getApiKey';
    logger.info('Starting API key retrieval', logContext);
    try {
        const { accessToken } = await getAuthData();
        if (!accessToken) {
            logger.warn('No access token found, cannot get API key', logContext);
            return { success: false, keyExists: false, error: 'Not authenticated' };
        }
        
        logger.info('Calling apiGetApiKey from shared/api/index.js', logContext);
        // apiGetApiKey now returns { success, keyExists, apiKeyInfo?, error? }
        const response = await apiGetApiKey(accessToken);
        
        logger.info(`Received response from apiGetApiKey: ${JSON.stringify(response)}`, logContext);
        
        // Pass the relevant information back to the controller
        if (response.success) {
            // Successfully determined key status (exists or not)
            logger.info(`API Key status determined. Exists: ${response.keyExists}`, logContext);
            // Include apiKeyInfo for gemini_credentials and other data
            return { 
                success: true, 
                keyExists: response.keyExists,
                apiKeyInfo: response.apiKeyInfo
            };
        } else {
            // API call failed
            logger.error(`apiGetApiKey failed: ${response.error}`, logContext);
            return { success: false, keyExists: false, error: response.error || 'API key retrieval failed' };
        }
        
    } catch (error) {
        // Catch any unexpected errors during the service execution itself
        handleError(error, logContext);
        logger.error(`Unexpected error during API key retrieval: ${error.message}`, logContext);
        return { success: false, keyExists: false, error: error.message };
    }
}

/**
 * Generate new API Key via backend
 * Automatically captures and stores current CSRF token and LinkedIn cookies if available.
 * Includes instance tracking information for multi-key support (v1.1.0).
 * 
 * @returns {Promise<{success: boolean, key?: string, error?: string}>} API key generation result
 */
export async function generateApiKey() {
    logger.info('Generating new API key via backend', 'auth.service');
    try {
        logger.info('Getting auth data...', 'auth.service');
        const authData = await getAuthData();
        logger.info(`Auth data received: ${JSON.stringify({ hasToken: !!authData?.accessToken, hasUserId: !!authData?.userId })}`, 'auth.service');
        const { accessToken } = authData;
        if (!accessToken) {
            logger.error('No access token found - user not authenticated', 'auth.service');
            throw new Error('Not authenticated');
        }
        logger.info('Access token found, continuing...', 'auth.service');
        
        // Get instance information for multi-key support (v1.1.0)
        let instanceInfo = null;
        try {
            logger.info('Getting instance info...', 'auth.service');
            instanceInfo = await instanceService.getInstanceInfo();
            logger.info(`Instance info captured: ID=${instanceInfo.instance_id}, Name=${instanceInfo.instance_name}`, 'auth.service');
        } catch (err) {
            logger.warn(`Could not get instance info: ${err.message}`, 'auth.service');
            // Continue without it - backward compatibility
        }
        
        logger.info('Getting LinkedIn credentials...', 'auth.service');
        
        // Get current CSRF token and LinkedIn cookies to store with the new key
        let csrfToken = null;
        let linkedinCookies = null;
        
        try {
            logger.info('Getting CSRF token and cookies from linkedin controller...', 'auth.service');
            csrfToken = await linkedinController.getCsrfToken().catch(() => null);
            linkedinCookies = await linkedinController.getAllLinkedInCookies().catch(() => null);
            
            if (csrfToken) {
                logger.info('Captured CSRF token for new API key', 'auth.service');
            }
            if (linkedinCookies && Object.keys(linkedinCookies).length > 0) {
                logger.info(`Captured ${Object.keys(linkedinCookies).length} LinkedIn cookies for new API key`, 'auth.service');
            }
        } catch (err) {
            logger.warn(`Could not capture LinkedIn credentials: ${err.message}`, 'auth.service');
            // Continue without them - not critical
        }
        
        logger.info('Calling apiGenerateApiKey...', 'auth.service');
        const response = await apiGenerateApiKey(
            accessToken, 
            csrfToken || undefined, 
            linkedinCookies || undefined,
            instanceInfo || undefined  // Pass instance info (v1.1.0)
        );
        
        // Store API key info in storage (critical for WebSocket sync)
        await saveApiKeyInfo({
            key: response.key,
            id: response.id,
            prefix: response.prefix,
            instance_id: response.instance_id
        });
        
        logger.info(`API key stored with instance_id: ${response.instance_id}`, 'auth.service');

        // NOTE: We do NOT reconnect the WebSocket after generating a new key
        // The WebSocket represents the browser/extension instance (identified by instance_id)
        // The instance_id never changes (unless extension is reinstalled)
        // The backend routes requests based on api_key.instance_id
        // Reconnecting here was causing race conditions with in-flight proxy requests

        // Instead, just refresh the credentials in the backend database
        try {
            logger.info('Refreshing backend credentials with new CSRF and cookies', 'auth.service');
            await updateBackendCredentials();
        } catch (error) {
            logger.warn(`Could not refresh backend credentials: ${error.message}`, 'auth.service');
            // Non-critical - credentials will be refreshed on next WebSocket reconnect anyway
        }

        // Refresh Gemini status to sync with new API key's credentials
        // This ensures dashboard shows correct Gemini state after key regeneration
        // Small delay to ensure backend has committed the transaction
        try {
            logger.info('Triggering Gemini status refresh after API key generation', 'auth.service');
            await new Promise(resolve => setTimeout(resolve, 500)); // Wait for DB commit
            await refreshGeminiStatus();
        } catch (geminiError) {
            logger.warn(`Could not refresh Gemini status: ${geminiError.message}`, 'auth.service');
        }

        return { success: true, key: response.key };
    } catch (error) {
        handleError(error, 'auth.service.generateApiKey');
        logger.error(`Error generating API key: ${error.message}`, 'auth.service');
        throw error;
    }
}

/**
 * Update CSRF Token for API Key
 * 
 * @param {string} csrfToken - The CSRF token to update
 * @returns {Promise<{success: boolean, error?: string}>} CSRF token update result
 */
export async function updateCsrfToken(csrfToken) {
    const logContext = 'auth.service:updateCsrfToken';
    logger.info('Updating CSRF token via backend', logContext);
    try {
        const { accessToken } = await getAuthData();
        if (!accessToken) {
            return { success: false, error: 'Not authenticated' };
        }
        const result = await apiUpdateCsrfToken(accessToken, csrfToken);
        if (result.success) {
            logger.info('CSRF token updated successfully', logContext);
        } else {
            logger.warn(`Failed to update CSRF token: ${result.error}`, logContext);
        }
        return result;
    } catch (error) {
        handleError(error, logContext);
        logger.error(`Error updating CSRF token: ${error.message}`, logContext);
        return { success: false, error: error.message };
    }
}

/**
 * Update LinkedIn cookies for the user's API key
 * 
 * @param {Object} linkedinCookies - Object containing all LinkedIn cookies {name: value}
 * @returns {Promise<{success: boolean, error?: string}>} LinkedIn cookies update result
 */
export async function updateLinkedInCookies(linkedinCookies) {
    const logContext = 'auth.service:updateLinkedInCookies';
    logger.info('Updating LinkedIn cookies via backend', logContext);
    try {
        const { accessToken } = await getAuthData();
        if (!accessToken) {
            return { success: false, error: 'Not authenticated' };
        }
        const result = await apiUpdateLinkedInCookies(accessToken, linkedinCookies);
        if (result.success) {
            logger.info('LinkedIn cookies updated successfully', logContext);
        } else {
            logger.warn(`Failed to update LinkedIn cookies: ${result.error}`, logContext);
        }
        return result;
    } catch (error) {
        handleError(error, logContext);
        logger.error(`Error updating LinkedIn cookies: ${error.message}`, logContext);
        return { success: false, error: error.message };
    }
}

/**
 * Update Gemini credentials for the current user's API key (v1.2.0)
 * 
 * @param {Object} geminiCredentials - Gemini OAuth credentials object
 * @returns {Promise<{success: boolean, error?: string}>} Result of the update
 */
export async function updateGeminiCredentials(geminiCredentials) {
    const logContext = 'auth.service:updateGeminiCredentials';
    logger.info('Updating Gemini credentials via backend', logContext);
    try {
        const { accessToken } = await getAuthData();
        if (!accessToken) {
            return { success: false, error: 'Not authenticated' };
        }
        const result = await apiUpdateGeminiCredentials(accessToken, geminiCredentials);
        if (result.success) {
            logger.info('Gemini credentials updated successfully', logContext);
        } else {
            logger.warn(`Failed to update Gemini credentials: ${result.error}`, logContext);
        }
        return result;
    } catch (error) {
        handleError(error, logContext);
        logger.error(`Error updating Gemini credentials: ${error.message}`, logContext);
        return { success: false, error: error.message };
    }
}

/**
 * Update backend credentials (CSRF token and LinkedIn cookies)
 * Called after WebSocket reconnection to ensure backend has latest credentials
 *
 * @returns {Promise<{success: boolean, csrfUpdated: boolean, cookiesUpdated: boolean, error?: string}>}
 */
export async function updateBackendCredentials() {
    const logContext = 'auth.service:updateBackendCredentials';
    logger.info('Updating backend credentials (CSRF + cookies) after reconnection', logContext);

    let csrfUpdated = false;
    let cookiesUpdated = false;

    try {
        const { accessToken } = await getAuthData();
        if (!accessToken) {
            logger.warn('Cannot update credentials - not authenticated', logContext);
            return { success: false, csrfUpdated, cookiesUpdated, error: 'Not authenticated' };
        }

        // Get current CSRF token and LinkedIn cookies
        let csrfToken = null;
        let linkedinCookies = null;

        try {
            csrfToken = await linkedinController.getCsrfToken().catch(() => null);
            linkedinCookies = await linkedinController.getAllLinkedInCookies().catch(() => null);
        } catch (err) {
            logger.warn(`Could not retrieve current credentials: ${err.message}`, logContext);
        }

        // Update CSRF token if available
        if (csrfToken) {
            try {
                const csrfResult = await apiUpdateCsrfToken(accessToken, csrfToken);
                if (csrfResult.success) {
                    logger.info('CSRF token updated in backend', logContext);
                    csrfUpdated = true;
                } else {
                    logger.warn(`Failed to update CSRF token: ${csrfResult.error}`, logContext);
                }
            } catch (error) {
                logger.warn(`Error updating CSRF token: ${error.message}`, logContext);
            }
        }

        // Update LinkedIn cookies if available
        if (linkedinCookies && Object.keys(linkedinCookies).length > 0) {
            try {
                const cookiesResult = await apiUpdateLinkedInCookies(accessToken, linkedinCookies);
                if (cookiesResult.success) {
                    logger.info(`LinkedIn cookies updated in backend (${Object.keys(linkedinCookies).length} cookies)`, logContext);
                    cookiesUpdated = true;
                } else {
                    logger.warn(`Failed to update LinkedIn cookies: ${cookiesResult.error}`, logContext);
                }
            } catch (error) {
                logger.warn(`Error updating LinkedIn cookies: ${error.message}`, logContext);
            }
        }

        const success = csrfUpdated || cookiesUpdated;
        if (success) {
            logger.info('Backend credentials update completed', logContext);
        } else {
            logger.warn('No credentials were updated in backend', logContext);
        }

        return { success, csrfUpdated, cookiesUpdated };
    } catch (error) {
        handleError(error, logContext);
        logger.error(`Error updating backend credentials: ${error.message}`, logContext);
        return { success: false, csrfUpdated, cookiesUpdated, error: error.message };
    }
}

/**
 * Delete API Key via backend
 *
 * @returns {Promise<{success: boolean, error?: string}>} API key deletion result
 */
export async function deleteApiKey() {
    logger.info('Deleting API key via backend', 'auth.service');
    try {
        const { accessToken } = await getAuthData();
        if (!accessToken) {
            throw new Error('Not authenticated');
        }
        await apiDeleteApiKey(accessToken);
        
        // Clear stored API key info
        await clearApiKeyInfo();
        logger.info('API key info cleared from storage', 'auth.service');
        
        // Clear Gemini credentials since API key is deleted
        try {
            logger.info('Clearing Gemini credentials after API key deletion', 'auth.service');
            await clearGeminiCredentials();
        } catch (geminiError) {
            logger.warn(`Could not clear Gemini credentials: ${geminiError.message}`, 'auth.service');
        }
        
        // Disconnect WebSocket since key is deleted
        try {
            logger.info('Disconnecting WebSocket after key deletion', 'auth.service');
            websocketService.closeWebSocket();
        } catch (wsError) {
            logger.warn(`Could not disconnect WebSocket after key deletion: ${wsError.message}`, 'auth.service');
        }
        
        // Refresh Gemini status to update UI (will show as disconnected)
        try {
            logger.info('Triggering Gemini status refresh after API key deletion', 'auth.service');
            await refreshGeminiStatus();
        } catch (geminiError) {
            logger.warn(`Could not refresh Gemini status: ${geminiError.message}`, 'auth.service');
        }
        
        return { success: true };
    } catch (error) {
        handleError(error, 'auth.service.deleteApiKey');
        logger.error(`Error deleting API key: ${error.message}`, 'auth.service');
        throw error;
    }
}

/**
 * Check if there is a valid authentication token
 * Used for quick authentication checks without fetching profile
 * 
 * @returns {Promise<boolean>} True if there is a valid token
 */
export async function hasValidToken() {
    try {
        // Get auth data from storage
        const { accessToken } = await getAuthData();

        // Return true if token exists (backend validates expiration)
        return !!accessToken;
    } catch (error) {
        handleError(error, 'auth.service.hasValidToken');
        logger.error(`Error checking token validity: ${error.message}`, 'auth.service');
        return false;
    }
}

/**
 * Get the current access token
 * 
 * @returns {Promise<string|null>} The access token or null if not authenticated
 */
export async function getAccessToken() {
    try {
        const { accessToken } = await getAuthData();
        return accessToken || null;
    } catch (error) {
        handleError(error, 'auth.service.getAccessToken');
        return null;
    }
}

/**
 * Save authentication session data from login page
 * Validates and stores the token and user data
 * 
 * @param {Object} authData - Authentication data from login page
 * @param {string} [authData.accessToken] - The access token
 * @param {string} [authData.id] - The user ID
 * @param {string} [authData.token_expires_at] - The token expiration timestamp
 * @param {string} [authData.name] - User's name
 * @param {string} [authData.email] - User's email
 * @param {string} [authData.profile_picture_url] - User's profile picture URL
 * @returns {Promise<{success: boolean, error?: string}>} - Result of the save operation
 */
export async function saveAuthSession(authData) {
    try {
        logger.info('Saving auth session from login page', 'auth.service');
        
        // Check if the data is valid
        if (!authData) {
            throw new Error('Invalid authentication data: no data provided');
        }
        
        // Check for specific format (token in accessToken field)
        if (authData.accessToken && authData.id) {
            // Format from server is directly usable
            const tokenExpiresAt = authData.token_expires_at 
                ? new Date(authData.token_expires_at).getTime() 
                : Date.now() + 24 * 60 * 60 * 1000; // Default 24 hours
            
            // Save to storage using storage service
            await saveAuthData(authData.accessToken, authData.id, tokenExpiresAt);
            
            // Trigger WebSocket connection after successful login
            // Close any existing connection first to ensure clean reconnect with new user
            try {
                logger.info('Triggering WebSocket connection after successful login', 'auth.service');
                // Close existing connection if any (will be reopened with new user_id)
                websocketService.closeWebSocket(false);
                // Small delay to ensure cleanup, then reconnect
                await new Promise(resolve => setTimeout(resolve, 100));
                // FIX: Add await to ensure WebSocket connects before continuing
                await websocketService.initWebSocket();
                logger.info('WebSocket initialized successfully after login', 'auth.service');
            } catch (wsError) {
                // Don't fail login if WebSocket initialization fails
                logger.warn(`Could not initialize WebSocket after login: ${wsError.message}`, 'auth.service');
            }

            return { success: true };
        }

        // Legacy format check (token and userId fields)
        if (authData.token && authData.userId) {
            // Calculate token expiration (24 hours from now if not provided)
            const expiresAt = authData.expiresAt || Date.now() + 24 * 60 * 60 * 1000;

            // Save to storage using storage service
            await saveAuthData(authData.token, authData.userId, expiresAt);

            // Trigger WebSocket connection after successful login
            // Close any existing connection first to ensure clean reconnect with new user
            try {
                logger.info('Triggering WebSocket connection after successful login', 'auth.service');
                // Close existing connection if any (will be reopened with new user_id)
                websocketService.closeWebSocket(false);
                // Small delay to ensure cleanup, then reconnect
                await new Promise(resolve => setTimeout(resolve, 100));
                // FIX: Add await to ensure WebSocket connects before continuing
                await websocketService.initWebSocket();
                logger.info('WebSocket initialized successfully after login', 'auth.service');
            } catch (wsError) {
                // Don't fail login if WebSocket initialization fails
                logger.warn(`Could not initialize WebSocket after login: ${wsError.message}`, 'auth.service');
            }
            
            return { success: true };
        }
        
        // If we got here, data format is invalid
        throw new Error('Invalid authentication data: missing required fields');
    } catch (error) {
        handleError(error, 'auth.service.saveAuthSession');
        logger.error(`Failed to save auth session: ${error.message}`, 'auth.service');
        return { success: false, error: error.message };
    }
} 