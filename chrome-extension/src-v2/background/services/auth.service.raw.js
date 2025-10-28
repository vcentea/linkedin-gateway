import { fetchUserProfile, logoutBackend, getApiKey as apiGetApiKey, generateApiKey as apiGenerateApiKey, deleteApiKey as apiDeleteApiKey } from '../shared/api.js';
import { getAuthData, clearAuthData } from '../shared/storage.js';
import { log } from '../shared/utils.js';

// Check if a token is expired
function isTokenExpired(expiresAt) {
    if (!expiresAt) return true;
    return new Date(expiresAt) <= new Date();
}

// Check if user is authenticated and fetch profile
export async function checkAuthAndGetProfile() {
    try {
        // First directly check chrome storage to compare with getAuthData result
        chrome.storage.local.get(['access_token', 'user_id', 'token_expires_at'], (directResult) => {
            log('Direct storage check:');
            log('- access_token: ' + (directResult.access_token ? 'exists' : 'missing'));
            log('- user_id: ' + (directResult.user_id ? 'exists' : 'missing'));
            log('- token_expires_at: ' + (directResult.token_expires_at ? 'exists' : 'missing'));
            
            // If we find direct access_token but not through getAuthData, use it directly
            if (directResult.access_token && !getAuthData().accessToken) {
                log('Using direct storage token since wrapper is not finding it');
                fetchUserProfile(directResult.access_token)
                  .then(userData => {
                    log('Successfully fetched user profile with direct token');
                  })
                  .catch(err => {
                    log('Error fetching profile with direct token: ' + err.message);
                  });
            }
        });
        
        // Get auth data from storage
        const { accessToken, userId, tokenExpiresAt } = await getAuthData();
        
        log('Auth data from storage:');
        log('- accessToken: ' + (accessToken ? 'exists' : 'missing'));
        log('- userId: ' + (userId ? 'exists' : 'missing'));
        log('- tokenExpiresAt: ' + (tokenExpiresAt ? 'exists' : 'missing'));
        
        // Check if token exists and isn't expired
        if (!accessToken || isTokenExpired(tokenExpiresAt)) {
            log('No valid token found via getAuthData');
            
            // Try direct storage access as fallback
            return new Promise((resolve) => {
                chrome.storage.local.get(['access_token', 'token_expires_at'], async (result) => {
                    if (result.access_token && !isTokenExpired(result.token_expires_at)) {
                        log('Found valid token via direct storage');
                        try {
                            const userData = await fetchUserProfile(result.access_token);
                            resolve({ authenticated: true, userData });
                            return;
                        } catch (error) {
                            log(`Error with direct token: ${error.message}`);
                        }
                    }
                    log('No valid token found in either method');
                    resolve({ authenticated: false });
                });
            });
        }
        
        // Fetch user profile from backend
        const userData = await fetchUserProfile(accessToken);
        return { 
            authenticated: true,
            userData
        };
    } catch (error) {
        log(`Auth check failed: ${error.message}`);
        // If error is 401, clear auth data
        if (error.message && error.message.includes('401')) {
            await clearAuthData();
        }
        return { authenticated: false, error: error.message };
    }
}

// Handle user logout
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
        
        return { success: true };
    } catch (error) {
        log(`Logout error: ${error.message}`);
        // Still try to clear storage
        await clearAuthData();
        return { success: true, backendError: error.message };
    }
}

// Get API Key
export async function getApiKey() {
    log('Getting API key from backend');
    try {
        const { accessToken } = await getAuthData();
        if (!accessToken) {
            throw new Error('Not authenticated');
        }
        const response = await apiGetApiKey(accessToken);
        return { success: true, apiKey: response.key }; // Assuming backend returns { key: '...' }
    } catch (error) {
        log(`Error getting API key: ${error.message}`, 'error');
        throw error; // Re-throw to be caught by the handler in index.js
    }
}

// Generate API Key
export async function generateApiKey() {
    log('Generating new API key via backend');
    try {
        const { accessToken } = await getAuthData();
        if (!accessToken) {
            throw new Error('Not authenticated');
        }
        const response = await apiGenerateApiKey(accessToken);
        // Assuming backend returns { key: '...', id: '...', ... }
        return { success: true, apiKey: response.key };
    } catch (error) {
        log(`Error generating API key: ${error.message}`, 'error');
        throw error;
    }
}

// Delete API Key
export async function deleteApiKey() {
    log('Deleting API key via backend');
    try {
        const { accessToken } = await getAuthData();
        if (!accessToken) {
            throw new Error('Not authenticated');
        }
        await apiDeleteApiKey(accessToken);
        return { success: true };
    } catch (error) {
        log(`Error deleting API key: ${error.message}`, 'error');
        throw error;
    }
} 