//@ts-check
/// <reference types="chrome"/>

/**
 * Browser and system information detection utilities
 * Used for instance tracking and multi-key support (v1.1.0)
 * 
 * @fileoverview Detects browser name, version, OS, and platform information
 * for creating unique instance identifiers and user-friendly display names.
 * 
 * NOTE: This module is used in service workers where DOM APIs like `document`
 * are not available. All code must be service worker compatible.
 */

import { logger } from './logger.js';

/**
 * Safely gets user agent string
 * Service workers have navigator but it may not be immediately available
 * @returns {string} User agent string or empty string if not available
 */
function safeGetUserAgent() {
    try {
        if (typeof navigator !== 'undefined' && navigator.userAgent) {
            return navigator.userAgent;
        }
    } catch (e) {
        // Silently fail - navigator might not be available
    }
    return '';
}

/**
 * Safely gets platform string
 * @returns {string} Platform string or empty string if not available
 */
function safeGetPlatform() {
    try {
        if (typeof navigator !== 'undefined' && navigator.platform) {
            return navigator.platform;
        }
    } catch (e) {
        // Silently fail
    }
    return '';
}

/**
 * Detects browser name from user agent
 * @returns {string} Browser name (chrome, edge, brave, opera, or unknown)
 */
function detectBrowserName() {
    const userAgent = safeGetUserAgent().toLowerCase();
    
    if (!userAgent) {
        return 'unknown';
    }
    
    // Check for specific browsers (order matters - check most specific first)
    if (userAgent.includes('edg/')) {
        return 'edge';
    } else if (userAgent.includes('brave')) {
        return 'brave';
    } else if (userAgent.includes('opr/') || userAgent.includes('opera')) {
        return 'opera';
    } else if (userAgent.includes('chrome')) {
        return 'chrome';
    } else if (userAgent.includes('chromium')) {
        return 'chromium';
    }
    
    return 'unknown';
}

/**
 * Detects browser version
 * @returns {string} Browser version or 'unknown'
 */
function detectBrowserVersion() {
    try {
        const userAgent = safeGetUserAgent();
        
        if (!userAgent) {
            // Fallback: try to get from extension manifest
            if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getManifest) {
                return chrome.runtime.getManifest().version;
            }
            return 'unknown';
        }
        
        // Try to extract version from user agent
        // Chrome/Edge format: "Chrome/120.0.6099.109" or "Edg/120.0.2210.91"
        const chromeMatch = userAgent.match(/Chrome\/(\d+\.\d+\.\d+\.\d+)/);
        const edgeMatch = userAgent.match(/Edg\/(\d+\.\d+\.\d+\.\d+)/);
        const operaMatch = userAgent.match(/OPR\/(\d+\.\d+\.\d+\.\d+)/);
        
        if (edgeMatch) {
            return edgeMatch[1];
        } else if (operaMatch) {
            return operaMatch[1];
        } else if (chromeMatch) {
            return chromeMatch[1];
        }
        
        // Fallback: try to get from extension manifest
        if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getManifest) {
            return chrome.runtime.getManifest().version;
        }
    } catch (error) {
        logger.error('Failed to detect browser version', 'browser-info', error);
    }
    
    return 'unknown';
}

/**
 * Detects operating system
 * @returns {string} OS name (windows, mac, linux, chromeos, android, ios, or unknown)
 */
function detectOS() {
    try {
        const userAgent = safeGetUserAgent().toLowerCase();
        const platform = safeGetPlatform().toLowerCase();
        
        // Check user agent for specific OS signatures
        if (userAgent) {
            if (userAgent.includes('win')) {
                return 'windows';
            } else if (userAgent.includes('mac')) {
                // Distinguish between macOS and iOS
                if (userAgent.includes('iphone') || userAgent.includes('ipad')) {
                    return 'ios';
                }
                return 'mac';
            } else if (userAgent.includes('linux')) {
                // Check if it's ChromeOS
                if (userAgent.includes('cros')) {
                    return 'chromeos';
                }
                return 'linux';
            } else if (userAgent.includes('android')) {
                return 'android';
            } else if (userAgent.includes('cros')) {
                return 'chromeos';
            }
        }
        
        // Fallback to platform detection
        if (platform) {
            if (platform.includes('win')) {
                return 'windows';
            } else if (platform.includes('mac')) {
                return 'mac';
            } else if (platform.includes('linux')) {
                return 'linux';
            }
        }
    } catch (error) {
        logger.error('Failed to detect OS', 'browser-info', error);
    }
    
    return 'unknown';
}

/**
 * Detects platform architecture
 * @returns {string} Platform architecture (x86_64, arm64, or unknown)
 */
function detectPlatform() {
    try {
        // Modern browsers support navigator.userAgentData
        if (typeof navigator !== 'undefined' && navigator.userAgentData && navigator.userAgentData.platform) {
            const platform = navigator.userAgentData.platform.toLowerCase();
            
            if (platform.includes('arm')) {
                return 'arm64';
            } else if (platform.includes('x86') || platform.includes('win') || platform.includes('mac')) {
                return 'x86_64';
            }
        }
        
        // Fallback to navigator.platform
        const platform = safeGetPlatform().toLowerCase();
        if (platform) {
            if (platform.includes('arm')) {
                return 'arm64';
            } else if (platform.includes('win64') || platform.includes('x86_64') || platform.includes('x64')) {
                return 'x86_64';
            } else if (platform.includes('win32') || platform.includes('x86')) {
                return 'x86';
            }
        }
    } catch (error) {
        logger.error('Failed to detect platform', 'browser-info', error);
    }
    
    return 'unknown';
}

/**
 * Detects complete browser and system information
 * @returns {Promise<Object>} Browser info object with all detected properties
 */
export async function detectBrowserInfo() {
    const context = 'browser-info:detectBrowserInfo';
    
    try {
        const browserInfo = {
            browser: detectBrowserName(),
            browserVersion: detectBrowserVersion(),
            os: detectOS(),
            platform: detectPlatform(),
            detectedAt: new Date().toISOString()
        };
        
        logger.info(`Detected browser info: ${JSON.stringify(browserInfo)}`, context);
        
        return browserInfo;
    } catch (error) {
        logger.error('Failed to detect browser info', context, error);
        
        // Return minimal info on error
        return {
            browser: 'unknown',
            browserVersion: 'unknown',
            os: 'unknown',
            platform: 'unknown',
            detectedAt: new Date().toISOString()
        };
    }
}

/**
 * Generates user-friendly browser display name
 * @param {Object} browserInfo - Browser info from detectBrowserInfo()
 * @returns {string} Friendly name like "Chrome on Windows" or "Edge on Mac"
 */
export function generateFriendlyBrowserName(browserInfo) {
    // Capitalize browser name
    const browserNames = {
        'chrome': 'Chrome',
        'edge': 'Edge',
        'brave': 'Brave',
        'opera': 'Opera',
        'chromium': 'Chromium',
        'unknown': 'Browser'
    };
    
    // Capitalize OS name
    const osNames = {
        'windows': 'Windows',
        'mac': 'Mac',
        'linux': 'Linux',
        'chromeos': 'ChromeOS',
        'android': 'Android',
        'ios': 'iOS',
        'unknown': 'Unknown OS'
    };
    
    const browser = browserNames[browserInfo.browser] || 'Browser';
    const os = osNames[browserInfo.os] || 'Unknown OS';
    
    return `${browser} on ${os}`;
}

/**
 * Gets cached browser info from storage, or detects fresh if not available
 * @returns {Promise<Object>} Browser info object
 */
export async function getCachedBrowserInfo() {
    return new Promise((resolve) => {
        chrome.storage.local.get(['browserInfo'], async (result) => {
            if (result.browserInfo) {
                logger.info('Using cached browser info', 'browser-info');
                resolve(result.browserInfo);
            } else {
                logger.info('No cached browser info, detecting fresh', 'browser-info');
                const freshInfo = await detectBrowserInfo();
                resolve(freshInfo);
            }
        });
    });
}

