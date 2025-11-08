//@ts-check

/**
 * Multi-Key API Client Functions (v1.1.0)
 * 
 * Provides API functions for managing multiple API keys per user with instance tracking.
 * These functions interact with the /v1/api-keys endpoints.
 * 
 * @fileoverview Multi-key management API client functions
 */

import appConfig from '../config/app.config.js';
import { logger } from '../utils/logger.js';
import { handleError } from '../utils/error-handler.js';

/**
 * List all API keys for the current user
 * Calls GET /v1/api-keys/list
 * 
 * @param {string} accessToken - User's access token for authentication
 * @returns {Promise<{keys: Array, total: number, active_count: number}>} List of API keys with metadata
 * @throws {Error} If the API request fails
 */
export async function listApiKeys(accessToken) {
    const logContext = 'keys.api:listApiKeys';
    logger.info('Fetching all API keys for user', logContext);
    
    if (!accessToken) {
        logger.error('Attempted to list API keys without access token', logContext);
        throw new Error('No access token provided');
    }
    
    // Get current server URL dynamically
    const { apiUrl } = await appConfig.getServerUrls();
    
    try {
        const response = await fetch(`${apiUrl}/v1/api-keys/list`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        if (response.status === 404) {
            logger.warn('Multi-key endpoint not found - backend may not support v1.1.0', logContext);
            throw new Error('Multi-key API not supported by backend (404)');
        }
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        logger.info(`Retrieved ${data.total} API keys (${data.active_count} active)`, logContext);
        
        return data;
    } catch (error) {
        handleError(error, logContext);
        throw error;
    }
}

/**
 * Delete a specific API key by its ID
 * Calls DELETE /v1/api-keys/{keyId}
 * 
 * @param {string} accessToken - User's access token for authentication
 * @param {string} keyId - UUID of the API key to delete
 * @returns {Promise<{success: boolean, message?: string, error?: string}>} Deletion result
 * @throws {Error} If the API request fails
 */
export async function deleteApiKeyById(accessToken, keyId) {
    const logContext = 'keys.api:deleteApiKeyById';
    logger.info(`Deleting API key: ${keyId}`, logContext);
    
    if (!accessToken) {
        logger.error('Attempted to delete API key without access token', logContext);
        throw new Error('No access token provided');
    }
    
    if (!keyId) {
        logger.error('Attempted to delete API key without key ID', logContext);
        throw new Error('No key ID provided');
    }
    
    // Get current server URL dynamically
    const { apiUrl } = await appConfig.getServerUrls();
    
    try {
        const response = await fetch(`${apiUrl}/v1/api-keys/${keyId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        if (response.status === 404) {
            logger.warn('API key not found or already deleted', logContext);
            return { success: false, error: 'API key not found' };
        }
        
        if (response.status === 403) {
            logger.error('Permission denied to delete API key', logContext);
            return { success: false, error: 'Permission denied' };
        }
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        logger.info('API key deleted successfully', logContext);
        
        return { success: true, message: data.message };
    } catch (error) {
        handleError(error, logContext);
        throw error;
    }
}

/**
 * Update the instance name for a specific API key
 * Calls PATCH /v1/api-keys/{keyId}/name
 * 
 * @param {string} accessToken - User's access token for authentication
 * @param {string} keyId - UUID of the API key
 * @param {string} newName - New instance name (1-100 characters)
 * @returns {Promise<{success: boolean, message?: string, error?: string}>} Update result
 * @throws {Error} If the API request fails
 */
export async function updateInstanceName(accessToken, keyId, newName) {
    const logContext = 'keys.api:updateInstanceName';
    logger.info(`Updating instance name for key ${keyId} to: ${newName}`, logContext);
    
    if (!accessToken) {
        logger.error('Attempted to update instance name without access token', logContext);
        throw new Error('No access token provided');
    }
    
    if (!keyId) {
        logger.error('Attempted to update instance name without key ID', logContext);
        throw new Error('No key ID provided');
    }
    
    if (!newName || typeof newName !== 'string') {
        logger.error('Invalid instance name provided', logContext);
        throw new Error('Invalid instance name');
    }
    
    const trimmedName = newName.trim();
    if (trimmedName.length === 0 || trimmedName.length > 100) {
        logger.error('Instance name must be between 1 and 100 characters', logContext);
        throw new Error('Instance name must be between 1 and 100 characters');
    }
    
    // Get current server URL dynamically
    const { apiUrl } = await appConfig.getServerUrls();
    
    try {
        const response = await fetch(`${apiUrl}/v1/api-keys/${keyId}/name`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({ instance_name: trimmedName })
        });
        
        if (response.status === 404) {
            logger.warn('API key not found', logContext);
            return { success: false, error: 'API key not found' };
        }
        
        if (response.status === 403) {
            logger.error('Permission denied to update instance name', logContext);
            return { success: false, error: 'Permission denied' };
        }
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        logger.info('Instance name updated successfully', logContext);
        
        return { success: true, message: data.message };
    } catch (error) {
        handleError(error, logContext);
        throw error;
    }
}

/**
 * Get a specific API key by ID
 * Calls GET /v1/api-keys/{keyId}
 * 
 * @param {string} accessToken - User's access token for authentication
 * @param {string} keyId - UUID of the API key
 * @returns {Promise<Object>} API key object with metadata
 * @throws {Error} If the API request fails
 */
export async function getApiKeyById(accessToken, keyId) {
    const logContext = 'keys.api:getApiKeyById';
    logger.info(`Fetching API key: ${keyId}`, logContext);
    
    if (!accessToken) {
        logger.error('Attempted to get API key without access token', logContext);
        throw new Error('No access token provided');
    }
    
    if (!keyId) {
        logger.error('Attempted to get API key without key ID', logContext);
        throw new Error('No key ID provided');
    }
    
    // Get current server URL dynamically
    const { apiUrl } = await appConfig.getServerUrls();
    
    try {
        const response = await fetch(`${apiUrl}/v1/api-keys/${keyId}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        if (response.status === 404) {
            logger.warn('API key not found', logContext);
            throw new Error('API key not found');
        }
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        logger.info('API key retrieved successfully', logContext);
        
        return data;
    } catch (error) {
        handleError(error, logContext);
        throw error;
    }
}

/**
 * Update webhook configuration for a specific API key
 * @param {string} accessToken - User access token
 * @param {string} keyId - API key UUID
 * @param {{webhook_url: string, webhook_headers?: Object}} payload - Webhook config
 * @returns {Promise<Object|null>} Updated API key info (if backend returns it)
 */
export async function updateWebhookConfig(accessToken, keyId, payload) {
    const logContext = 'keys.api:updateWebhookConfig';
    logger.info(`Updating webhook for key ${keyId}`, logContext);
    return webhookRequest(accessToken, `/v1/api-keys/${keyId}/webhook`, 'PATCH', payload, logContext);
}

/**
 * Delete webhook configuration for a specific API key
 * @param {string} accessToken - User access token
 * @param {string} keyId - API key UUID
 * @returns {Promise<Object|null>} Updated API key info (if backend returns it)
 */
export async function deleteWebhookConfig(accessToken, keyId) {
    const logContext = 'keys.api:deleteWebhookConfig';
    logger.info(`Deleting webhook for key ${keyId}`, logContext);
    return webhookRequest(accessToken, `/v1/api-keys/${keyId}/webhook`, 'DELETE', undefined, logContext);
}

/**
 * Update webhook configuration for legacy single-key backend
 * @param {string} accessToken - User access token
 * @param {{webhook_url: string, webhook_headers?: Object}} payload - Webhook config
 * @returns {Promise<Object|null>} Updated API key info (if backend returns it)
 */
export async function updateLegacyWebhookConfig(accessToken, payload) {
    const logContext = 'keys.api:updateLegacyWebhookConfig';
    logger.info('Updating legacy webhook configuration', logContext);
    return webhookRequest(accessToken, `/users/me/api-key/webhook`, 'PATCH', payload, logContext);
}

/**
 * Delete webhook configuration for legacy single-key backend
 * @param {string} accessToken - User access token
 * @returns {Promise<Object|null>} Updated API key info (if backend returns it)
 */
export async function deleteLegacyWebhookConfig(accessToken) {
    const logContext = 'keys.api:deleteLegacyWebhookConfig';
    logger.info('Deleting legacy webhook configuration', logContext);
    return webhookRequest(accessToken, `/users/me/api-key/webhook`, 'DELETE', undefined, logContext);
}

/**
 * Shared helper for webhook API requests
 * @param {string} accessToken - User access token
 * @param {string} path - Endpoint path
 * @param {'PATCH'|'DELETE'} method - HTTP method
 * @param {Object} [payload] - Optional JSON payload
 * @param {string} logContext - Logger context label
 * @returns {Promise<Object|null>} Parsed response or null
 */
async function webhookRequest(accessToken, path, method, payload, logContext) {
    if (!accessToken) {
        logger.error('Attempted webhook request without access token', logContext);
        throw new Error('No access token provided');
    }

    // For key-specific calls ensure ID exists
    if (path.includes('/v1/api-keys/') && !/\/v1\/api-keys\/[^/]+/i.test(path)) {
        logger.error('Attempted webhook request without key ID', logContext);
        throw new Error('No key ID provided');
    }

    const { apiUrl } = await appConfig.getServerUrls();

    try {
        const response = await fetch(`${apiUrl}${path}`, {
            method,
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                ...(payload ? { 'Content-Type': 'application/json' } : {})
            },
            body: payload ? JSON.stringify(payload) : undefined
        });

        return await processWebhookResponse(response, logContext);
    } catch (error) {
        handleError(error, logContext);
        throw error;
    }
}

/**
 * Process webhook API response and normalize errors
 * @param {Response} response - Fetch response
 * @param {string} logContext - Logger context
 * @returns {Promise<Object|null>} Parsed JSON or null
 */
async function processWebhookResponse(response, logContext) {
    if (response.status === 404) {
        const error = new Error('Webhook feature not available on this backend (404).');
        error.code = 'WEBHOOK_NOT_SUPPORTED';
        logger.warn('Webhook endpoint not found on backend', logContext);
        throw error;
    }

    if (response.status === 204) {
        return null;
    }

    if (!response.ok) {
        const errorText = await response.text();
        const error = new Error(`API error: ${response.status} ${response.statusText} - ${errorText}`);
        error.code = `HTTP_${response.status}`;
        throw error;
    }

    try {
        return await response.json();
    } catch {
        return null;
    }
}


