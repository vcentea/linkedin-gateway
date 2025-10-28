//@ts-check

/**
 * API-specific configuration
 * 
 * @fileoverview Configuration constants for API interaction.
 * Defines base URLs, timeouts, retry logic, and headers for backend communication.
 * Environment-specific values (e.g., API_URL for dev vs. prod) should be managed here.
 */

import appConfig from './app.config.js';

/**
 * API configuration object with API-specific settings
 * @typedef {Object} ApiConfig
 * @property {string} API_URL - Base URL for the backend API
 * @property {Object} HEADERS - Default headers for API requests
 * @property {number} TIMEOUT - Default timeout for API requests in ms
 * @property {number} RETRY_ATTEMPTS - Number of retry attempts for failed requests
 * @property {number} RETRY_DELAY - Delay between retry attempts in ms
 */

/**
 * API configuration
 * Consider environment-specific overrides here.
 * Example: const isDevelopment = chrome.runtime.id === 'your-dev-extension-id';
 * const resolvedApiUrl = isDevelopment ? 'http://localhost:8000' : 'https://lgprod.ainnovate.tech'; // Example production URL
 * @type {ApiConfig}
 */
const apiConfig = {
  API_URL: appConfig.API_URL, // Currently uses the URL from app.config.js
  // API_URL: resolvedApiUrl, // Example using environment variable
  HEADERS: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  },
  TIMEOUT: 30000, // 30 seconds
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000 // 1 second
};

export default apiConfig; 