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

import { fetchUserProfile, logoutBackend, getApiKey as apiGetApiKey, generateApiKey as apiGenerateApiKey, deleteApiKey as apiDeleteApiKey, updateCsrfToken as apiUpdateCsrfToken, updateLinkedInCookies as apiUpdateLinkedInCookies } from '../../shared/api/index.js';
import { getAuthData, clearAuthData, saveAuthData } from '../services/storage.service.js';
import { logger } from '../../shared/utils/logger.js';
import { isTokenExpired } from './auth.helpers.js';
import { handleError } from '../../shared/utils/error-handler.js';

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
        
        // Check if token exists and isn't expired
        if (!accessToken || isTokenExpired(tokenExpiresAt)) {
            logger.info('No valid token found via getAuthData', 'auth.service');
            
            // Try direct storage access as fallback
            return new Promise((resolve) => {
                chrome.storage.local.get(['access_token', 'token_expires_at'], async (result) => {
                    if (result.access_token && !isTokenExpired(result.token_expires_at)) {
                        logger.info('Found valid token via direct storage', 'auth.service');
                        try {
                            const fetchedUserData = await fetchUserProfile(result.access_token);
                            userData = fetchedUserData; // Cache user data
                            resolve({ authenticated: true, userData: fetchedUserData });
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
            userData: fetchedUserData
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
 * 
 * @returns {Promise<{success: boolean, backendError?: string}>} Logout result
 */
export async function performLogout() {
    try {
        // Get current token
        const { accessToken } = await getAuthData();
        
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
            return { success: true, keyExists: response.keyExists };
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
 * 
 * @returns {Promise<{success: boolean, key?: string, error?: string}>} API key generation result
 */
export async function generateApiKey() {
    logger.info('Generating new API key via backend', 'auth.service');
    try {
        const { accessToken } = await getAuthData();
        if (!accessToken) {
            throw new Error('Not authenticated');
        }
        
        // Get current CSRF token and LinkedIn cookies to store with the new key
        let csrfToken = null;
        let linkedinCookies = null;
        
        try {
            // Import linkedin controller dynamically
            const linkedinController = await import('../controllers/linkedin.controller.js');
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
        
        const response = await apiGenerateApiKey(accessToken, csrfToken || undefined, linkedinCookies || undefined);
        // Assuming backend returns { key: '...', id: '...', ... }
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
        const { accessToken, tokenExpiresAt } = await getAuthData();
        
        // Return true if token exists and isn't expired
        return !!(accessToken && !isTokenExpired(tokenExpiresAt));
    } catch (error) {
        handleError(error, 'auth.service.hasValidToken');
        logger.error(`Error checking token validity: ${error.message}`, 'auth.service');
        return false;
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
            try {
                const websocketService = await import('../services/websocket.service.js');
                logger.info('Triggering WebSocket connection after successful login', 'auth.service');
                websocketService.initWebSocket();
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
            try {
                const websocketService = await import('../services/websocket.service.js');
                logger.info('Triggering WebSocket connection after successful login', 'auth.service');
                websocketService.initWebSocket();
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