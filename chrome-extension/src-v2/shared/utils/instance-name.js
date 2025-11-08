//@ts-check
/// <reference types="chrome"/>

/**
 * Instance name management utilities
 * Manages user-friendly names for extension instances (v1.1.0)
 * 
 * @fileoverview Provides functions to get, set, and manage instance names.
 * Instance names are human-readable labels like "Chrome on Windows" that
 * help users identify different browser installations in the multi-key UI.
 */

import { logger } from './logger.js';
import { detectBrowserInfo, generateFriendlyBrowserName } from './browser-info.js';

/**
 * Gets the current instance name from storage
 * @returns {Promise<string|null>} Instance name or null if not set
 */
export async function getInstanceName() {
    return new Promise((resolve) => {
        chrome.storage.local.get(['instanceName'], (result) => {
            if (chrome.runtime.lastError) {
                logger.error('Failed to get instance name from storage', 'instance-name', chrome.runtime.lastError);
                resolve(null);
            } else {
                resolve(result.instanceName || null);
            }
        });
    });
}

/**
 * Sets a custom instance name
 * @param {string} name - The new instance name
 * @returns {Promise<void>}
 */
export async function setInstanceName(name) {
    return new Promise((resolve, reject) => {
        if (!name || typeof name !== 'string') {
            reject(new Error('Instance name must be a non-empty string'));
            return;
        }
        
        // Trim and validate length (max 100 chars)
        const trimmedName = name.trim();
        if (trimmedName.length === 0) {
            reject(new Error('Instance name cannot be empty'));
            return;
        }
        
        if (trimmedName.length > 100) {
            reject(new Error('Instance name too long (max 100 characters)'));
            return;
        }
        
        chrome.storage.local.set({ instanceName: trimmedName }, () => {
            if (chrome.runtime.lastError) {
                logger.error('Failed to store instance name', 'instance-name', chrome.runtime.lastError);
                reject(chrome.runtime.lastError);
            } else {
                logger.info(`Instance name updated: ${trimmedName}`, 'instance-name');
                resolve();
            }
        });
    });
}

/**
 * Generates default instance name if not set
 * This is the main entry point for getting an instance name
 * @returns {Promise<string>} Instance name (existing or generated)
 */
export async function ensureInstanceName() {
    const context = 'instance-name:ensureInstanceName';
    
    try {
        // Try to get existing instance name
        let instanceName = await getInstanceName();
        
        if (instanceName) {
            logger.info(`Using existing instance name: ${instanceName}`, context);
            return instanceName;
        }
        
        // No instance name exists, generate default
        logger.info('No instance name found, generating default', context);
        
        const browserInfo = await detectBrowserInfo();
        instanceName = generateFriendlyBrowserName(browserInfo);
        
        await setInstanceName(instanceName);
        
        logger.info(`Default instance name generated and stored: ${instanceName}`, context);
        
        return instanceName;
    } catch (error) {
        logger.error('Failed to ensure instance name', context, error);
        
        // Fallback: return generic name
        return 'Browser Extension';
    }
}

/**
 * Validates instance name
 * @param {string} name - Name to validate
 * @returns {boolean} True if valid
 */
export function validateInstanceName(name) {
    if (!name || typeof name !== 'string') {
        return false;
    }
    
    const trimmed = name.trim();
    
    // Must be between 1 and 100 characters
    if (trimmed.length === 0 || trimmed.length > 100) {
        return false;
    }
    
    // Should not contain control characters
    if (/[\x00-\x1F\x7F]/.test(trimmed)) {
        return false;
    }
    
    return true;
}

/**
 * Updates instance name with a custom value
 * This is the function to call when user customizes their instance name
 * @param {string} newName - The new custom name
 * @returns {Promise<string>} The updated instance name
 */
export async function updateInstanceName(newName) {
    const context = 'instance-name:updateInstanceName';
    
    try {
        // Validate the new name
        if (!validateInstanceName(newName)) {
            throw new Error('Invalid instance name');
        }
        
        const trimmedName = newName.trim();
        
        await setInstanceName(trimmedName);
        
        logger.info(`Instance name updated to: ${trimmedName}`, context);
        
        return trimmedName;
    } catch (error) {
        logger.error('Failed to update instance name', context, error);
        throw error;
    }
}

/**
 * Resets instance name to default (based on browser info)
 * @returns {Promise<string>} The new default instance name
 */
export async function resetInstanceNameToDefault() {
    const context = 'instance-name:resetInstanceNameToDefault';
    
    try {
        const browserInfo = await detectBrowserInfo();
        const defaultName = generateFriendlyBrowserName(browserInfo);
        
        await setInstanceName(defaultName);
        
        logger.info(`Instance name reset to default: ${defaultName}`, context);
        
        return defaultName;
    } catch (error) {
        logger.error('Failed to reset instance name', context, error);
        throw error;
    }
}

/**
 * Clears the instance name from storage (for testing/debugging)
 * WARNING: This will cause a new default name to be generated
 * @returns {Promise<void>}
 */
export async function clearInstanceName() {
    return new Promise((resolve, reject) => {
        chrome.storage.local.remove(['instanceName'], () => {
            if (chrome.runtime.lastError) {
                logger.error('Failed to clear instance name', 'instance-name', chrome.runtime.lastError);
                reject(chrome.runtime.lastError);
            } else {
                logger.warn('Instance name cleared from storage', 'instance-name');
                resolve();
            }
        });
    });
}

