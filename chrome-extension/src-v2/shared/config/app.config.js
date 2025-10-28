//@ts-check

/**
 * Main application configuration
 * 
 * @fileoverview Central configuration constants for the LinkedIn Gateway extension.
 * Defines global settings. Domain-specific settings (API, WebSocket) are in their respective config files.
 * URLs can be customized via localStorage server settings.
 */

/**
 * Application configuration object
 * @typedef {Object} AppConfig
 * @property {string} API_URL - Base URL for backend API
 * @property {string} WSS_URL - WebSocket server URL
 * @property {number} MIN_CHECK_INTERVAL - Minimum time between status checks in ms
 * @property {number} ACTIVE_CHECK_INTERVAL - Interval for active status checks in ms
 * @property {Function} getServerUrls - Async function to get current server URLs from storage
 */

/**
 * Server configuration options
 */
const SERVER_CONFIGS = {
  MAIN: {
    apiUrl: 'https://lg.ainnovate.tech'
  }
};

/**
 * Derive WebSocket URL from API URL
 * @param {string} apiUrl - API base URL
 * @returns {string} WebSocket URL
 */
function getWebSocketUrl(apiUrl) {
  const url = new URL(apiUrl);
  const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${url.host}/ws`;
}

/**
 * Get server URLs from localStorage
 * @returns {Promise<{apiUrl: string, wssUrl: string}>}
 */
async function getServerUrls() {
  return new Promise((resolve) => {
    if (typeof chrome !== 'undefined' && chrome.storage) {
      chrome.storage.local.get(['serverType', 'customApiUrl'], (result) => {
        const serverType = result.serverType || 'MAIN';
        
        let apiUrl;
        if (serverType === 'CUSTOM') {
          apiUrl = result.customApiUrl || SERVER_CONFIGS.MAIN.apiUrl;
        } else {
          const config = SERVER_CONFIGS[serverType] || SERVER_CONFIGS.MAIN;
          apiUrl = config.apiUrl;
        }
        
        resolve({
          apiUrl: apiUrl,
          wssUrl: getWebSocketUrl(apiUrl)
        });
      });
    } else {
      // Fallback for build-time (webpack) or non-extension context
      const apiUrl = process.env.API_URL || SERVER_CONFIGS.MAIN.apiUrl;
      resolve({
        apiUrl: apiUrl,
        wssUrl: getWebSocketUrl(apiUrl)
      });
    }
  });
}

/**
 * Application configuration
 * URLs are loaded from localStorage or use defaults
 * @type {AppConfig}
 */
const appConfig = {
  // Default URLs (will be overridden by localStorage settings)
  API_URL: process.env.API_URL || SERVER_CONFIGS.MAIN.apiUrl,
  WSS_URL: process.env.WSS_URL || getWebSocketUrl(process.env.API_URL || SERVER_CONFIGS.MAIN.apiUrl),
  
  // Status checking constants (General app behavior)
  MIN_CHECK_INTERVAL: 20 * 1000, // 20 seconds minimum between checks
  ACTIVE_CHECK_INTERVAL: 2 * 60 * 1000, // 2 minutes
  
  // WebSocket reconnection settings
  WS_INITIAL_RECONNECT_DELAY: 1000, // 1 second
  WS_MAX_RECONNECT_DELAY: 30000, // 30 seconds
  WS_RECONNECT_MULTIPLIER: 1.5,
  WS_PING_INTERVAL: 30000, // 30 seconds
  WS_PONG_TIMEOUT: 5000, // 5 seconds
  
  // Function to get current server URLs
  getServerUrls
};

export default appConfig;

// Backward compatibility exports removed. Import `appConfig` directly or use domain-specific configs.
/*
export const { 
  API_URL, 
  WSS_URL, 
  WS_INITIAL_RECONNECT_DELAY,
  WS_MAX_RECONNECT_DELAY,
  WS_RECONNECT_MULTIPLIER,
  WS_PING_INTERVAL,
  WS_PONG_TIMEOUT,
  MIN_CHECK_INTERVAL,
  ACTIVE_CHECK_INTERVAL
} = appConfig; 
*/ 