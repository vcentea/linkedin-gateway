//@ts-check

/**
 * API utility functions for interacting with the backend server
 * 
 * @fileoverview This file provides utility functions for making API calls to the backend server,
 * handling authentication, and processing responses.
 */

import appConfig from '../config/app.config.js';
import { logger } from '../utils/logger.js';
import { handleError } from '../utils/error-handler.js';

// API Key endpoint path
const API_KEY_ENDPOINT = '/users/me/api-key';

/**
 * Fetch user profile from backend API
 * 
 * @param {string} accessToken - The user's access token for authentication
 * @returns {Promise<Object>} The user profile data
 * @throws {Error} If the API request fails
 */
export async function fetchUserProfile(accessToken) {
    logger.info('Fetching user profile from /me endpoint', 'api/index.js:fetchUserProfile');
    logger.info(`[fetchUserProfile] Token received: ${accessToken ? 'YES (first 20 chars: ' + accessToken.substring(0, 20) + '...)' : 'NO TOKEN!'}`, 'api/index.js:fetchUserProfile');
    
    // ALWAYS get current server URL dynamically (fixes multi-server bug)
    const { apiUrl } = await appConfig.getServerUrls();
    logger.info(`[fetchUserProfile] Using dynamic API URL: ${apiUrl}`, 'api/index.js:fetchUserProfile');
    
    try {
        const response = await fetch(`${apiUrl}/me`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        handleError(error, 'api/index.js:fetchUserProfile');
        throw error;
    }
}

/**
 * Send logout request to backend
 * 
 * @param {string} accessToken - The user's access token for authentication
 * @returns {Promise<boolean>} True if logout was successful, false otherwise
 */
export async function logoutBackend(accessToken) {
    logger.info('Sending logout request to backend', 'api/index.js:logoutBackend');
    
    // ALWAYS get current server URL dynamically
    const { apiUrl } = await appConfig.getServerUrls();
    logger.info(`[logoutBackend] Using dynamic API URL: ${apiUrl}`, 'api/index.js:logoutBackend');
    
    try {
        const response = await fetch(`${apiUrl}/auth/logout`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        return response.ok;
    } catch (error) {
        handleError(error, 'api/index.js:logoutBackend');
        // We still want to proceed with local logout, so just log the error
        return false;
    }
}

/**
 * Get API Key from backend
 * 
 * @param {string} accessToken - The user's access token for authentication
 * @returns {Promise<{success: boolean, keyExists: boolean, apiKeyInfo?: Object, error?: string}>} Object indicating if the API key exists and the key info
 * @throws {Error} If the API request fails (though we now handle errors internally)
 */
export async function getApiKey(accessToken) {
    const logContext = 'api/index.js:getApiKey';
    logger.info('Starting API key fetch', logContext);
    
    if (!accessToken) {
        logger.error('Attempted to get API key without access token', logContext);
        // Indicate failure or lack of key existence clearly
        return { success: false, keyExists: false, error: 'No access token' }; 
    }
    
    // ALWAYS get current server URL dynamically
    const { apiUrl: serverUrl } = await appConfig.getServerUrls();
    const apiUrl = `${serverUrl}${API_KEY_ENDPOINT}`;
    const headers = {
        'Authorization': `Bearer ${accessToken}`
    };
    
    logger.info(`Fetching from URL: ${apiUrl}`, logContext);
    const tokenPrefix = accessToken.substring(0, 8) + '...';
    logger.info(`Using token prefix: ${tokenPrefix}`, logContext);

    try {
        logger.info(`Making fetch request to ${apiUrl}`, logContext);
        const response = await fetch(apiUrl, {
            method: 'GET',
            headers: headers
        });

        logger.info(`Received response status: ${response.status}`, logContext);
        
        if (response.status === 404) {
            logger.warn('API returned 404 - No API key found for user.', logContext);
            // Key does not exist
            return { success: true, keyExists: false }; 
        }

        if (!response.ok) {
             const errorText = await response.text();
            logger.error(`API error: ${response.status} ${response.statusText}. Body: ${errorText}`, logContext);
             // Return failure due to API error
            return { success: false, keyExists: false, error: `API error: ${response.status} ${response.statusText}` };
        }

        // If response is OK (200), it means an active key exists, even if 'key' field isn't returned
        const apiKeyInfo = await response.json();
        logger.info(`Successfully parsed API key info: ${JSON.stringify(apiKeyInfo)}`, logContext);
        
        // Return success and indicate key exists, along with the info (excluding the full key)
        return { 
            success: true, 
            keyExists: true, 
            apiKeyInfo: apiKeyInfo // Return the metadata received
        }; 

    } catch (error) {
        handleError(error, logContext);
        // Propagate the error after handling, indicating failure
        return { success: false, keyExists: false, error: error.message }; 
    }
}

/**
 * Generate new API Key
 * Supports multi-key instance tracking (v1.1.0)
 * 
 * @param {string} accessToken - The user's access token for authentication
 * @param {string} [csrfToken] - Optional CSRF token to store with the key
 * @param {Object} [linkedinCookies] - Optional LinkedIn cookies to store with the key
 * @param {Object} [instanceInfo] - Optional instance info for multi-key support (v1.1.0)
 * @returns {Promise<{key: string}>} The newly generated API key
 * @throws {Error} If the API request fails
 */
export async function generateApiKey(accessToken, csrfToken = null, linkedinCookies = null, instanceInfo = null) {
    logger.info('Generating new API key via backend', 'api/index.js:generateApiKey');
    
    // ALWAYS get current server URL dynamically
    const { apiUrl } = await appConfig.getServerUrls();
    
    try {
        // Build request body
        const requestBody = {};
        
        // Legacy fields (backward compatible)
        if (csrfToken) {
            requestBody.csrf_token = csrfToken;
        }
        if (linkedinCookies) {
            requestBody.linkedin_cookies = linkedinCookies;
        }
        
        // New multi-key fields (v1.1.0)
        if (instanceInfo) {
            requestBody.instance_id = instanceInfo.instance_id;
            requestBody.instance_name = instanceInfo.instance_name;
            requestBody.browser_info = instanceInfo.browser_info;
            logger.info(`Including instance info: ID=${instanceInfo.instance_id}`, 'api/index.js:generateApiKey');
        }
        
        // Use new endpoint if instance info is provided, otherwise use legacy endpoint
        const endpoint = instanceInfo ? '/v1/api-keys/generate' : API_KEY_ENDPOINT;
        logger.info(`Using endpoint: ${endpoint}`, 'api/index.js:generateApiKey');
        
        const response = await fetch(`${apiUrl}${endpoint}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        return await response.json(); // Expects { key: '...newApiKey...', ...otherData }
    } catch (error) {
        handleError(error, 'api/index.js:generateApiKey');
        throw error;
    }
}

/**
 * Update CSRF Token for API Key
 * 
 * @param {string} accessToken - The user's access token for authentication
 * @param {string} csrfToken - The CSRF token to update
 * @returns {Promise<{success: boolean, error?: string}>} Object indicating if update was successful
 */
export async function updateCsrfToken(accessToken, csrfToken) {
    const logContext = 'api/index.js:updateCsrfToken';
    logger.info('Updating CSRF token via backend', logContext);
    
    if (!accessToken) {
        logger.error('Attempted to update CSRF token without access token', logContext);
        return { success: false, error: 'No access token' };
    }
    
    if (!csrfToken) {
        logger.error('Attempted to update CSRF token with empty token', logContext);
        return { success: false, error: 'No CSRF token provided' };
    }
    
    // ALWAYS get current server URL dynamically
    const { apiUrl } = await appConfig.getServerUrls();
    
    try {
        const response = await fetch(`${apiUrl}${API_KEY_ENDPOINT}/csrf-token`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({ csrf_token: csrfToken })
        });

        if (response.status === 404) {
            logger.warn('API returned 404 - No active API key found to update', logContext);
            return { success: false, error: 'No active API key found' };
        }

        if (!response.ok) {
            const errorText = await response.text();
            logger.error(`API error: ${response.status} ${response.statusText}. Body: ${errorText}`, logContext);
            return { success: false, error: `API error: ${response.status} ${response.statusText}` };
        }

        logger.info('CSRF token updated successfully', logContext);
        return { success: true };
    } catch (error) {
        handleError(error, logContext);
        return { success: false, error: error.message };
    }
}

/**
 * Update LinkedIn cookies for the user's API key
 * 
 * @param {string} accessToken - The user's access token for authentication
 * @param {Object} linkedinCookies - Object containing all LinkedIn cookies {name: value}
 * @returns {Promise<{success: boolean, error?: string}>} Object indicating if update was successful
 */
export async function updateLinkedInCookies(accessToken, linkedinCookies) {
    const logContext = 'api/index.js:updateLinkedInCookies';
    logger.info('Updating LinkedIn cookies via backend', logContext);
    
    if (!accessToken) {
        logger.error('Attempted to update LinkedIn cookies without access token', logContext);
        return { success: false, error: 'No access token' };
    }
    
    if (!linkedinCookies || typeof linkedinCookies !== 'object') {
        logger.error('Attempted to update LinkedIn cookies with invalid data', logContext);
        return { success: false, error: 'Invalid LinkedIn cookies data' };
    }
    
    // ALWAYS get current server URL dynamically
    const { apiUrl } = await appConfig.getServerUrls();
    
    try {
        const response = await fetch(`${apiUrl}${API_KEY_ENDPOINT}/linkedin-cookies`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({ linkedin_cookies: linkedinCookies })
        });

        if (response.status === 404) {
            logger.warn('API returned 404 - No active API key found to update', logContext);
            return { success: false, error: 'No active API key found' };
        }

        if (!response.ok) {
            const errorText = await response.text();
            logger.error(`API error: ${response.status} ${response.statusText}. Body: ${errorText}`, logContext);
            return { success: false, error: `API error: ${response.status} ${response.statusText}` };
        }

        logger.info('LinkedIn cookies updated successfully', logContext);
        return { success: true };
    } catch (error) {
        handleError(error, logContext);
        return { success: false, error: error.message };
    }
}

/**
 * Update Gemini credentials for the user's API key (v1.2.0)
 * 
 * @param {string} accessToken - The user's access token for authentication
 * @param {Object} geminiCredentials - Gemini OAuth credentials object
 * @returns {Promise<{success: boolean, error?: string}>} Object indicating if update was successful
 */
export async function updateGeminiCredentials(accessToken, geminiCredentials) {
    const logContext = 'api/index.js:updateGeminiCredentials';
    logger.info('Updating Gemini credentials via backend', logContext);
    
    if (!accessToken) {
        logger.error('Attempted to update Gemini credentials without access token', logContext);
        return { success: false, error: 'No access token' };
    }
    
    if (!geminiCredentials || typeof geminiCredentials !== 'object') {
        logger.error('Attempted to update Gemini credentials with invalid data', logContext);
        return { success: false, error: 'Invalid Gemini credentials data' };
    }
    
    // ALWAYS get current server URL dynamically
    const { apiUrl } = await appConfig.getServerUrls();
    
    try {
        const response = await fetch(`${apiUrl}${API_KEY_ENDPOINT}/gemini-credentials`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({ gemini_credentials: geminiCredentials })
        });

        if (response.status === 404) {
            logger.warn('API returned 404 - No active API key found to update', logContext);
            return { success: false, error: 'No active API key found' };
        }

        if (!response.ok) {
            const errorText = await response.text();
            logger.error(`API error: ${response.status} ${response.statusText}. Body: ${errorText}`, logContext);
            return { success: false, error: `API error: ${response.status} ${response.statusText}` };
        }

        logger.info('Gemini credentials updated successfully', logContext);
        return { success: true };
    } catch (error) {
        handleError(error, logContext);
        return { success: false, error: error.message };
    }
}

/**
 * Delete API Key
 * 
 * @param {string} accessToken - The user's access token for authentication
 * @returns {Promise<{success: boolean}>} Object indicating if deletion was successful
 * @throws {Error} If the API request fails
 */
export async function deleteApiKey(accessToken) {
    logger.info('Deleting API key via backend', 'api/index.js:deleteApiKey');
    
    // ALWAYS get current server URL dynamically
    const { apiUrl } = await appConfig.getServerUrls();
    
    try {
        const response = await fetch(`${apiUrl}${API_KEY_ENDPOINT}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });

        if (!response.ok && response.status !== 404) { // 404 might mean it was already deleted
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        return { success: response.ok || response.status === 404 };
    } catch (error) {
        handleError(error, 'api/index.js:deleteApiKey');
        throw error;
    }
} 