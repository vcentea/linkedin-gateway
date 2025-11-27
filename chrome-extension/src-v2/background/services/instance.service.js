//@ts-check
/// <reference types="chrome"/>

/**
 * Instance management service for background script
 * Central service for managing extension instance information (v1.1.0)
 * 
 * @fileoverview Provides high-level instance management functions that coordinate
 * between instance ID, instance name, and browser info utilities. This service
 * is used by the background script to initialize and manage instance tracking.
 * 
 * NOTE: This module runs in service workers where DOM APIs like `document` are
 * not available. All code and dependencies must be service worker compatible.
 */

import { logger } from '../../shared/utils/logger.js';
import { ensureInstanceId, getInstanceId } from '../../shared/utils/instance-id.js';
import { ensureInstanceName, getInstanceName } from '../../shared/utils/instance-name.js';
import { detectBrowserInfo, getCachedBrowserInfo } from '../../shared/utils/browser-info.js';

/**
 * Default fallback instance info returned when detection fails
 */
const FALLBACK_INSTANCE_INFO = {
    instance_id: null,
    instance_name: 'Browser Extension',
    browser_info: {
        browser: 'unknown',
        browserVersion: 'unknown',
        os: 'unknown',
        platform: 'unknown',
        detectedAt: new Date().toISOString()
    }
};

/**
 * Gets complete instance information
 * Ensures all instance data exists and is up to date
 * This is the main function to call when you need all instance info
 * 
 * @param {boolean} forceRefresh - If true, refresh browser info even if cached
 * @returns {Promise<Object>} Complete instance info with instance_id, instance_name, browser_info
 */
export async function getInstanceInfo(forceRefresh = false) {
    const context = 'instance.service:getInstanceInfo';
    
    try {
        logger.info('Getting instance information', context);
        
        // 1. Ensure instance ID exists (generate if needed)
        let instanceId;
        try {
            instanceId = await ensureInstanceId();
        } catch (idError) {
            logger.warn(`Failed to get instance ID: ${idError.message}`, context);
            instanceId = 'fallback_' + Date.now();
        }
        
        // 2. Ensure instance name exists (generate if needed)
        let instanceName;
        try {
            instanceName = await ensureInstanceName();
        } catch (nameError) {
            logger.warn(`Failed to get instance name: ${nameError.message}`, context);
            instanceName = 'Browser Extension';
        }
        
        // 3. Get browser info (fresh or cached)
        let browserInfo;
        try {
            if (forceRefresh) {
                logger.info('Forcing fresh browser info detection', context);
                browserInfo = await detectBrowserInfo();
                
                // Cache the fresh info (non-blocking)
                try {
                    chrome.storage.local.set({ browserInfo }, () => {
                        if (chrome.runtime.lastError) {
                            logger.warn('Failed to cache browser info', context);
                        }
                    });
                } catch (cacheError) {
                    // Ignore cache errors
                }
            } else {
                browserInfo = await getCachedBrowserInfo();
                
                // If no cached info, detect and cache
                if (!browserInfo) {
                    browserInfo = await detectBrowserInfo();
                    try {
                        chrome.storage.local.set({ browserInfo });
                    } catch (cacheError) {
                        // Ignore cache errors
                    }
                }
            }
        } catch (browserError) {
            logger.warn(`Failed to get browser info: ${browserError.message}`, context);
            browserInfo = FALLBACK_INSTANCE_INFO.browser_info;
        }
        
        const instanceInfo = {
            instance_id: instanceId,
            instance_name: instanceName,
            browser_info: browserInfo || FALLBACK_INSTANCE_INFO.browser_info
        };
        
        logger.info(`Instance info retrieved: ID=${instanceId}, Name=${instanceName}`, context);
        
        return instanceInfo;
    } catch (error) {
        logger.error('Failed to get instance info', context, error);
        
        // Return minimal fallback info with timestamp-based ID
        return {
            ...FALLBACK_INSTANCE_INFO,
            instance_id: 'error_' + Date.now(),
            browser_info: {
                ...FALLBACK_INSTANCE_INFO.browser_info,
                detectedAt: new Date().toISOString()
            }
        };
    }
}

/**
 * Initialize instance tracking on extension install/update
 * This should be called during chrome.runtime.onInstalled
 */
export async function initializeInstance() {
    const context = 'instance.service:initializeInstance';
    
    try {
        logger.info('Initializing extension instance...', context);
        
        // Force fresh browser info on initialization
        const instanceInfo = await getInstanceInfo(true);
        
        logger.info(`Instance initialized successfully:`, context);
        logger.info(`  - ID: ${instanceInfo.instance_id}`, context);
        logger.info(`  - Name: ${instanceInfo.instance_name}`, context);
        logger.info(`  - Browser: ${instanceInfo.browser_info.browser} ${instanceInfo.browser_info.browserVersion}`, context);
        logger.info(`  - OS: ${instanceInfo.browser_info.os}`, context);
        
        return instanceInfo;
    } catch (error) {
        logger.error('Failed to initialize instance', context, error);
        throw error;
    }
}

/**
 * Verifies instance data integrity
 * Checks if all required instance data is present and valid
 * @returns {Promise<Object>} Verification result with status and issues
 */
export async function verifyInstanceIntegrity() {
    const context = 'instance.service:verifyInstanceIntegrity';
    
    try {
        logger.info('Verifying instance data integrity', context);
        
        const issues = [];
        
        // Check instance ID
        const instanceId = await getInstanceId();
        if (!instanceId) {
            issues.push('Instance ID is missing');
        }
        
        // Check instance name
        const instanceName = await getInstanceName();
        if (!instanceName) {
            issues.push('Instance name is missing');
        }
        
        // Check browser info
        const browserInfo = await getCachedBrowserInfo();
        if (!browserInfo) {
            issues.push('Browser info is not cached');
        }
        
        const isValid = issues.length === 0;
        
        if (isValid) {
            logger.info('Instance data integrity verified successfully', context);
        } else {
            logger.warn(`Instance data integrity issues found: ${issues.join(', ')}`, context);
        }
        
        return {
            valid: isValid,
            issues: issues,
            instanceId: instanceId,
            instanceName: instanceName,
            browserInfo: browserInfo
        };
    } catch (error) {
        logger.error('Failed to verify instance integrity', context, error);
        return {
            valid: false,
            issues: ['Verification failed: ' + error.message],
            instanceId: null,
            instanceName: null,
            browserInfo: null
        };
    }
}

/**
 * Repairs instance data if needed
 * Regenerates missing or invalid instance data
 * @returns {Promise<Object>} Repair result
 */
export async function repairInstanceData() {
    const context = 'instance.service:repairInstanceData';
    
    try {
        logger.info('Repairing instance data', context);
        
        // Verify integrity first
        const verification = await verifyInstanceIntegrity();
        
        if (verification.valid) {
            logger.info('Instance data is valid, no repair needed', context);
            return {
                repaired: false,
                message: 'Instance data is valid'
            };
        }
        
        // Repair by calling getInstanceInfo (which ensures all data exists)
        logger.info('Regenerating missing instance data', context);
        const instanceInfo = await getInstanceInfo(true);
        
        logger.info('Instance data repaired successfully', context);
        
        return {
            repaired: true,
            message: 'Instance data regenerated',
            instanceInfo: instanceInfo,
            issues: verification.issues
        };
    } catch (error) {
        logger.error('Failed to repair instance data', context, error);
        throw error;
    }
}

/**
 * Gets a summary of instance status for debugging/logging
 * @returns {Promise<Object>} Instance status summary
 */
export async function getInstanceStatus() {
    const context = 'instance.service:getInstanceStatus';
    
    try {
        const verification = await verifyInstanceIntegrity();
        const instanceInfo = verification.valid ? await getInstanceInfo() : null;
        
        return {
            initialized: verification.valid,
            instanceId: verification.instanceId,
            instanceName: verification.instanceName,
            browserInfo: verification.browserInfo,
            issues: verification.issues,
            fullInfo: instanceInfo
        };
    } catch (error) {
        logger.error('Failed to get instance status', context, error);
        return {
            initialized: false,
            error: error.message
        };
    }
}

