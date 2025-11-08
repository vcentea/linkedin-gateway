/**
 * Version compatibility checker
 */

import { logger } from './logger.js';
import appConfig from '../config/app.config.js';

const EXTENSION_VERSION = chrome.runtime.getManifest().version;
const MIN_BACKEND_VERSION = "1.1.0";  // Minimum backend version for this extension

/**
 * Check if backend supports required features
 * @param {string} [accessToken] - Optional access token for authentication
 * @returns {Promise<{compatible: boolean, backendVersion?: string, message?: string}>}
 */
export async function checkBackendCompatibility(accessToken) {
    const context = 'version-check:checkBackendCompatibility';
    
    try {
        const { apiUrl } = await appConfig.getServerUrls();
        
        // Prepare headers (authentication is optional)
        const headers = {};
        if (accessToken) {
            headers['Authorization'] = `Bearer ${accessToken}`;
        }
        
        // Try to fetch backend version
        const response = await fetch(`${apiUrl}/version`, {
            method: 'GET',
            headers: headers
        });
        
        if (!response.ok) {
            // /version endpoint doesn't exist = old backend
            logger.warn('Backend /version endpoint not found - assuming v1.0', context);
            return {
                compatible: false,
                backendVersion: "< 1.1.0",
                message: "Backend needs to be updated to v1.1 or higher. Please ask your administrator to update the LinkedIn Gateway backend."
            };
        }
        
        const versionInfo = await response.json();
        logger.info(`Backend version: ${versionInfo.version}`, context);
        
        // Check if backend supports multi-key
        if (!versionInfo.features?.multi_key_support) {
            return {
                compatible: false,
                backendVersion: versionInfo.version,
                message: "Backend does not support multi-key feature. Please update backend to v1.1 or higher."
            };
        }
        
        // Compatible
        return {
            compatible: true,
            backendVersion: versionInfo.version
        };
        
    } catch (error) {
        logger.error(`Error checking backend compatibility: ${error.message}`, context);
        // Assume old backend
        return {
            compatible: false,
            backendVersion: "unknown",
            message: "Could not verify backend version. Extension may have limited functionality."
        };
    }
}

/**
 * Compare semantic versions
 * @param {string} v1
 * @param {string} v2
 * @returns {number} -1 if v1 < v2, 0 if equal, 1 if v1 > v2
 */
function compareVersions(v1, v2) {
    const parts1 = v1.split('.').map(Number);
    const parts2 = v2.split('.').map(Number);
    
    for (let i = 0; i < 3; i++) {
        const p1 = parts1[i] || 0;
        const p2 = parts2[i] || 0;
        
        if (p1 > p2) return 1;
        if (p1 < p2) return -1;
    }
    
    return 0;
}

