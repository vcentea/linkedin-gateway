//@ts-check
/// <reference types="chrome"/>

/**
 * Instance ID generation and management utilities
 * Provides unique, persistent identifiers for browser extension instances (v1.1.0)
 * 
 * @fileoverview Generates and manages unique instance IDs for multi-key support.
 * Format: {browser}_{timestamp}_{random}
 * Example: chrome_1699123456789_a9b8c7d6
 */

import { logger } from './logger.js';
import { detectBrowserInfo } from './browser-info.js';

/**
 * Generates a cryptographically random hex string
 * @param {number} length - Number of random bytes (result will be length*2 hex chars)
 * @returns {string} Random hex string
 */
function generateRandomHex(length = 4) {
    const bytes = new Uint8Array(length);
    crypto.getRandomValues(bytes);
    return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Generates a unique instance ID
 * Format: {browser}_{timestamp}_{random}
 * Example: chrome_1699123456789_a9b8c7d6
 * 
 * @param {Object} browserInfo - Browser info from detectBrowserInfo()
 * @returns {string} Unique instance ID
 */
export function generateInstanceId(browserInfo) {
    const context = 'instance-id:generateInstanceId';
    
    try {
        // 1. Get browser prefix (max 6 chars, lowercase)
        const browser = browserInfo.browser.toLowerCase().substring(0, 6);
        
        // 2. Get timestamp (milliseconds since epoch)
        const timestamp = Date.now();
        
        // 3. Generate random hex string (8 characters = 4 bytes)
        const random = generateRandomHex(4);
        
        // Format: {browser}_{timestamp}_{random}
        const instanceId = `${browser}_${timestamp}_${random}`;
        
        logger.info(`Generated instance ID: ${instanceId}`, context);
        
        return instanceId;
    } catch (error) {
        logger.error('Failed to generate instance ID', context, error);
        
        // Fallback: generate with minimal info
        const timestamp = Date.now();
        const random = generateRandomHex(4);
        return `unknown_${timestamp}_${random}`;
    }
}

/**
 * Retrieves the current instance ID from storage
 * @returns {Promise<string|null>} Instance ID or null if not set
 */
export async function getInstanceId() {
    return new Promise((resolve) => {
        chrome.storage.local.get(['instanceId'], (result) => {
            if (chrome.runtime.lastError) {
                logger.error('Failed to get instance ID from storage', 'instance-id', chrome.runtime.lastError);
                resolve(null);
            } else {
                resolve(result.instanceId || null);
            }
        });
    });
}

/**
 * Stores the instance ID in chrome.storage.local
 * @param {string} instanceId - The instance ID to store
 * @returns {Promise<void>}
 */
export async function setInstanceId(instanceId) {
    return new Promise((resolve, reject) => {
        chrome.storage.local.set({ instanceId }, () => {
            if (chrome.runtime.lastError) {
                logger.error('Failed to store instance ID', 'instance-id', chrome.runtime.lastError);
                reject(chrome.runtime.lastError);
            } else {
                logger.info(`Instance ID stored: ${instanceId}`, 'instance-id');
                resolve();
            }
        });
    });
}

/**
 * Ensures instance ID exists, generates if needed
 * This is the main entry point for getting an instance ID
 * @returns {Promise<string>} The current or newly generated instance ID
 */
export async function ensureInstanceId() {
    const context = 'instance-id:ensureInstanceId';
    
    try {
        // Try to get existing instance ID
        let instanceId = await getInstanceId();
        
        if (instanceId) {
            logger.info(`Using existing instance ID: ${instanceId}`, context);
            return instanceId;
        }
        
        // No instance ID exists, generate a new one
        logger.info('No instance ID found, generating new one', context);
        
        const browserInfo = await detectBrowserInfo();
        instanceId = generateInstanceId(browserInfo);
        
        await setInstanceId(instanceId);
        
        logger.info(`New instance ID generated and stored: ${instanceId}`, context);
        
        return instanceId;
    } catch (error) {
        logger.error('Failed to ensure instance ID', context, error);
        
        // Last resort: generate temporary ID (not stored)
        const browserInfo = await detectBrowserInfo();
        return generateInstanceId(browserInfo);
    }
}

/**
 * Validates instance ID format
 * Expected format: {browser}_{timestamp}_{random}
 * @param {string} instanceId - Instance ID to validate
 * @returns {boolean} True if valid format
 */
export function validateInstanceId(instanceId) {
    if (!instanceId || typeof instanceId !== 'string') {
        return false;
    }
    
    // Check format: {browser}_{timestamp}_{random}
    const parts = instanceId.split('_');
    
    if (parts.length !== 3) {
        return false;
    }
    
    const [browser, timestamp, random] = parts;
    
    // Validate browser (1-6 chars, alphanumeric)
    if (!/^[a-z0-9]{1,6}$/.test(browser)) {
        return false;
    }
    
    // Validate timestamp (13 digits for milliseconds)
    if (!/^\d{13}$/.test(timestamp)) {
        return false;
    }
    
    // Validate random (8 hex chars)
    if (!/^[a-f0-9]{8}$/.test(random)) {
        return false;
    }
    
    return true;
}

/**
 * Clears the instance ID from storage (for testing/debugging)
 * WARNING: This will cause a new instance ID to be generated
 * @returns {Promise<void>}
 */
export async function clearInstanceId() {
    return new Promise((resolve, reject) => {
        chrome.storage.local.remove(['instanceId'], () => {
            if (chrome.runtime.lastError) {
                logger.error('Failed to clear instance ID', 'instance-id', chrome.runtime.lastError);
                reject(chrome.runtime.lastError);
            } else {
                logger.warn('Instance ID cleared from storage', 'instance-id');
                resolve();
            }
        });
    });
}

