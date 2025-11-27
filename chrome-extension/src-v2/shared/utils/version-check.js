/**
 * Version compatibility checker
 */

import { logger } from './logger.js';
import appConfig from '../config/app.config.js';

const EXTENSION_VERSION = chrome.runtime.getManifest().version;
const MIN_BACKEND_VERSION = "1.8.0";  // Minimum backend version for this extension

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

/**
 * Check if backend supports required features
 * @param {string} [accessToken] - Optional access token for authentication
 * @returns {Promise<{compatible: boolean, backendVersion?: string, extensionVersion?: string, message?: string, warningType?: string}>}
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
                extensionVersion: EXTENSION_VERSION,
                message: "Backend needs to be updated to v1.8.0 or higher. Please ask your administrator to update the LinkedIn Gateway backend.",
                warningType: "backend_outdated"
            };
        }
        
        const versionInfo = await response.json();
        const backendVersion = versionInfo.version;
        const minExtensionVersion = versionInfo.min_extension_version || "1.0.0";
        
        logger.info(`Backend version: ${backendVersion}, Extension version: ${EXTENSION_VERSION}`, context);
        logger.info(`Min backend required: ${MIN_BACKEND_VERSION}, Min extension required: ${minExtensionVersion}`, context);
        
        // Check 1: Backend version is too old for this extension
        if (compareVersions(backendVersion, MIN_BACKEND_VERSION) < 0) {
            logger.warn(`Backend version ${backendVersion} is older than required ${MIN_BACKEND_VERSION}`, context);
            return {
                compatible: false,
                backendVersion: backendVersion,
                extensionVersion: EXTENSION_VERSION,
                message: `Backend version ${backendVersion} is outdated. Please update backend to v${MIN_BACKEND_VERSION} or higher.`,
                warningType: "backend_outdated"
            };
        }
        
        // Check 2: Extension version is too old for this backend
        if (compareVersions(EXTENSION_VERSION, minExtensionVersion) < 0) {
            logger.warn(`Extension version ${EXTENSION_VERSION} is older than required ${minExtensionVersion}`, context);
            return {
                compatible: false,
                backendVersion: backendVersion,
                extensionVersion: EXTENSION_VERSION,
                message: `Extension version ${EXTENSION_VERSION} is outdated. Please update the extension to v${minExtensionVersion} or higher.`,
                warningType: "extension_outdated"
            };
        }
        
        // Check 3: Versions don't match (warning but still compatible)
        if (backendVersion !== EXTENSION_VERSION) {
            logger.warn(`Version mismatch: Backend ${backendVersion} vs Extension ${EXTENSION_VERSION}`, context);
            return {
                compatible: true,
                backendVersion: backendVersion,
                extensionVersion: EXTENSION_VERSION,
                message: `Version mismatch: Backend v${backendVersion}, Extension v${EXTENSION_VERSION}. Consider updating to match versions.`,
                warningType: "version_mismatch"
            };
        }
        
        // Check 4: Legacy - backend missing multi-key support
        if (!versionInfo.features?.multi_key_support) {
            return {
                compatible: false,
                backendVersion: backendVersion,
                extensionVersion: EXTENSION_VERSION,
                message: "Backend does not support multi-key feature. Please update backend to v1.1 or higher.",
                warningType: "backend_outdated"
            };
        }
        
        // Fully compatible - versions match
        logger.info(`Versions compatible: Backend ${backendVersion}, Extension ${EXTENSION_VERSION}`, context);
        return {
            compatible: true,
            backendVersion: backendVersion,
            extensionVersion: EXTENSION_VERSION
        };
        
    } catch (error) {
        logger.error(`Error checking backend compatibility: ${error.message}`, context);
        return {
            compatible: false,
            backendVersion: "unknown",
            extensionVersion: EXTENSION_VERSION,
            message: "Could not verify backend version. Extension may have limited functionality.",
            warningType: "connection_error"
        };
    }
}
