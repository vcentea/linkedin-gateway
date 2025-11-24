//@ts-check
/// <reference types="chrome"/>

/**
 * Login page script handling the authentication flow
 * 
 * @fileoverview Login page script that initializes the UI and handles the authentication flow
 */

import { logger } from '../../shared/utils/logger.js';
import appConfig from '../../shared/config/app.config.js';
import apiConfig from '../../shared/config/api.config.js';
import { MESSAGE_TYPES } from '../../shared/constants/message-types.js';
import { checkBackendCompatibility } from '../../shared/utils/version-check.js';

// DOM elements - will be initialized in init()
/** @type {HTMLElement|null} */
let loginButton = null;
/** @type {HTMLElement|null} */
let statusMessage = null;
/** @type {HTMLSelectElement|null} */
let serverSelect = null;
/** @type {HTMLInputElement|null} */
let customApiInput = null;
/** @type {HTMLElement|null} */
let customFieldsContainer = null;
/** @type {HTMLElement|null} */
let serverHealthContainer = null;
/** @type {HTMLElement|null} */
let healthIndicator = null;
/** @type {HTMLElement|null} */
let healthStatus = null;
/** @type {HTMLButtonElement|null} */
let connectServerBtn = null;
/** @type {HTMLElement|null} */
let emailLoginForm = null;
/** @type {HTMLElement|null} */
let linkedinLoginContainer = null;
/** @type {HTMLInputElement|null} */
let emailInput = null;
/** @type {HTMLInputElement|null} */
let passwordInput = null;
/** @type {HTMLButtonElement|null} */
let emailLoginBtn = null;
/** @type {HTMLElement|null} */
let forgotPasswordLink = null;
/** @type {HTMLElement|null} */
let loginDivider = null;

// Track server health state
let isServerOnline = true; // Default to true for MAIN server
let healthCheckTimeout = null;
let healthCheckInterval = null;

// Track LinkedIn config state
let linkedinConfigured = true; // Default to true, will be checked
let linkedinConfigCheckInterval = null;

/**
 * Shows a status message to the user
 * @param {string} message - The message to display
 * @param {string} type - The type of message ('info', 'error', etc)
 */
function showMessage(message, type) {
    if (!statusMessage) return;
    
    statusMessage.textContent = message;
    statusMessage.className = `status-message ${type}`;
    statusMessage.style.display = 'block';
    
    // Hide after 5 seconds if it's an info message
    if (type === 'info') {
        setTimeout(() => {
            if (statusMessage) {
                statusMessage.style.display = 'none';
            }
        }, 5000);
    }
}

// Initialize the login page
function init() {
    logger.info('Initializing login page');
    
    // Get DOM element references
    loginButton = document.getElementById('loginButton');
    statusMessage = document.getElementById('statusMessage');
    serverSelect = document.getElementById('server-select');
    customApiInput = document.getElementById('custom-api-url');
    customFieldsContainer = document.getElementById('custom-server-fields');
    serverHealthContainer = document.getElementById('server-health');
    healthIndicator = document.getElementById('health-indicator');
    healthStatus = document.getElementById('health-status');
    connectServerBtn = document.getElementById('connect-server-btn');
    emailLoginForm = document.getElementById('email-login-form');
    linkedinLoginContainer = document.getElementById('linkedin-login-container');
    emailInput = document.getElementById('email-input');
    passwordInput = document.getElementById('password-input');
    emailLoginBtn = document.getElementById('email-login-btn');
    forgotPasswordLink = document.getElementById('forgot-password-link');
    loginDivider = document.getElementById('login-divider');
    
    // Ensure server select has MAIN selected by default
    if (serverSelect && !serverSelect.value) {
        serverSelect.value = 'MAIN';
    }
    
    // Load saved server settings
    loadServerSettings();
    
    // Add click event to login button
    if (loginButton) {
        loginButton.addEventListener('click', handleLoginClick);
    }
    
    // Add change event to server select
    if (serverSelect) {
        serverSelect.addEventListener('change', handleServerSelectChange);
    }
    
    // Add click event to connect server button
    if (connectServerBtn) {
        connectServerBtn.addEventListener('click', handleConnectServerClick);
    }
    
    // Add input event to custom URL field for saving only (no permission checks)
    if (customApiInput) {
        customApiInput.addEventListener('input', handleCustomUrlInput);
    }
    
    // Add click event to email login button
    if (emailLoginBtn) {
        emailLoginBtn.addEventListener('click', handleEmailLoginClick);
    }
    
    // Add click event to forgot password link
    if (forgotPasswordLink) {
        forgotPasswordLink.addEventListener('click', handleForgotPasswordClick);
    }
    
    // Add enter key support for email/password inputs
    if (emailInput) {
        emailInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleEmailLoginClick();
        });
    }
    if (passwordInput) {
        passwordInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleEmailLoginClick();
        });
    }
    
    // Check backend version compatibility (Phase 3.3)
    checkBackendVersion();
    
    // Check server health in background (non-blocking)
    checkServerHealth();
    
    // Start health polling for all servers
    startHealthPolling();
    
    // Check if already authenticated on page load (non-blocking)
    checkExistingAuth();
}

/**
 * Load server settings from localStorage
 */
function loadServerSettings() {
    chrome.storage.local.get(['serverType', 'customApiUrl'], (result) => {
        if (serverSelect) {
            // Ensure we have a valid server type, default to MAIN
            const serverType = result.serverType || 'MAIN';
            
            // Set the select value
            serverSelect.value = serverType;
            
            // If still showing empty, force set to MAIN
            if (!serverSelect.value || serverSelect.selectedIndex === -1) {
                serverSelect.value = 'MAIN';
            }
            
            // Update login UI based on server type
            updateLoginUIForServerType(serverType);
            
            if (serverType === 'CUSTOM') {
                showCustomFields();
                if (customApiInput) customApiInput.value = result.customApiUrl || '';
                
                // Only check LinkedIn OAuth config for custom servers
                checkLinkedInConfig();
                startLinkedInConfigPolling();
            } else {
                hideCustomFields();
                
                // For main server, LinkedIn is always configured
                linkedinConfigured = true;
                if (loginButton) {
                    loginButton.disabled = false;
                    loginButton.style.opacity = '1';
                    loginButton.style.cursor = 'pointer';
                    loginButton.style.filter = 'none';
                    loginButton.title = '';
                }
                
                // Clear any OAuth warning message
                if (statusMessage) {
                    if (statusMessage.classList.contains('oauth-warning')) {
                        statusMessage.textContent = '';
                        statusMessage.style.display = 'none';
                        statusMessage.className = 'status-message';
                    }
                }
            }
        }
    });
}

/**
 * Request runtime permissions for a custom server URL
 * @param {string} url - The custom server URL
 * @returns {Promise<boolean>} - True if permission granted, false otherwise
 */
async function requestCustomServerPermission(url) {
    try {
        const urlObj = new URL(url);
        const origin = `${urlObj.protocol}//${urlObj.host}/*`;
        
        logger.info(`Requesting permission for: ${origin}`);
        
        // Check if we already have permission
        const hasPermission = await chrome.permissions.contains({
            origins: [origin]
        });
        
        if (hasPermission) {
            logger.info('Permission already granted');
            return true;
        }
        
        // Request permission from user
        const granted = await chrome.permissions.request({
            origins: [origin]
        });
        
        if (granted) {
            logger.info('Permission granted by user');
        } else {
            logger.warn('Permission denied by user');
            showMessage('Permission denied. The extension needs access to communicate with your custom server.', 'error');
        }
        
        return granted;
    } catch (error) {
        logger.error('Error requesting permission:', error);
        showMessage('Failed to request permission. Please try again.', 'error');
        return false;
    }
}

/**
 * Handle server select change
 */
async function handleServerSelectChange() {
    if (!serverSelect) return;
    
    const serverType = serverSelect.value;
    
    // Save server type immediately
    await saveServerType(serverType);
    
    // Clear existing WebSocket connection when switching servers
    // Send message to background script to close WebSocket
    try {
        logger.info('[SERVER_SWITCH] Requesting WebSocket closure due to server change');
        chrome.runtime.sendMessage({
            type: 'close_websocket',
            clearServerUrl: true
        }, (response) => {
            logger.info('[SERVER_SWITCH] WebSocket closure response:', response);
        });
    } catch (e) {
        logger.warn('Could not send WebSocket close message:', e);
    }
    
    // Update UI based on server type
    updateLoginUIForServerType(serverType);
    
    // Re-check backend version when server changes
    clearPreviousVersionWarning();
    checkBackendVersion();
    
    if (serverType === 'CUSTOM') {
        showCustomFields();
        
        // Start checking LinkedIn OAuth config for custom servers
        checkLinkedInConfig();
        startLinkedInConfigPolling();
        
        // Load saved custom URL if exists
        chrome.storage.local.get(['customApiUrl'], async (result) => {
            if (result.customApiUrl && customApiInput) {
                customApiInput.value = result.customApiUrl;
                
                // Check if we already have permission for this saved URL
                // If yes, auto-check health. If no, wait for user to click Connect
                try {
                    const urlObj = new URL(result.customApiUrl);
                    const origin = `${urlObj.protocol}//${urlObj.host}/*`;
                    const hasPermission = await chrome.permissions.contains({
                        origins: [origin]
                    });
                    
                    if (hasPermission) {
                        // Already have permission, check health
                        logger.info('Saved URL already has permission, checking health');
                        checkServerHealth();
                    } else {
                        // No permission yet, wait for Connect button
                        updateLoginButtonState(false);
                        if (serverHealthContainer) {
                            serverHealthContainer.style.display = 'none';
                        }
                    }
                } catch (e) {
                    // Invalid URL, wait for user to fix
                    updateLoginButtonState(false);
                    if (serverHealthContainer) {
                        serverHealthContainer.style.display = 'none';
                    }
                }
            } else {
                // No URL yet, disable login
                updateLoginButtonState(false);
                if (serverHealthContainer) {
                    serverHealthContainer.style.display = 'none';
                }
            }
        });
    } else {
        hideCustomFields();
        
        // Stop LinkedIn OAuth polling for main server (always configured)
        stopLinkedInConfigPolling();
        
        // Reset LinkedIn button to enabled state for main server
        linkedinConfigured = true;
        if (loginButton) {
            loginButton.disabled = false;
            loginButton.style.opacity = '1';
            loginButton.style.cursor = 'pointer';
            loginButton.style.filter = 'none';
            loginButton.title = '';
        }
        
        // Clear any OAuth warning message
        if (statusMessage) {
            if (statusMessage.classList.contains('oauth-warning')) {
                statusMessage.textContent = '';
                statusMessage.style.display = 'none';
                statusMessage.className = 'status-message';
            }
        }
        
        // For MAIN server, check health
        checkServerHealth();
    }
    
    // Re-check backend version after server configuration is complete
    setTimeout(() => {
        clearPreviousVersionWarning();
        checkBackendVersion();
    }, 500);
}

/**
 * Handle custom URL input (just save, no permission checks)
 */
function handleCustomUrlInput() {
    if (!customApiInput) return;
    
    const url = customApiInput.value.trim();
    
    // Save custom URL immediately to storage
    if (url) {
        chrome.storage.local.set({ customApiUrl: url }, () => {
            logger.info('Custom URL saved to storage');
        });
    }
    
    // Hide health indicator while typing
    if (serverHealthContainer) {
        serverHealthContainer.style.display = 'none';
    }
    
    // Disable login until Connect is clicked
    updateLoginButtonState(false);
}

/**
 * Handle Connect Server button click
 */
async function handleConnectServerClick() {
    if (!customApiInput) return;
    
    const url = customApiInput.value.trim();
    
    if (!url) {
        showMessage('Please enter a server URL.', 'error');
        return;
    }
    
    // Validate URL format
    try {
        new URL(url);
    } catch (e) {
        showMessage('Please enter a valid URL.', 'error');
        if (healthIndicator) {
            healthIndicator.className = 'health-indicator offline';
        }
        if (healthStatus) {
            healthStatus.textContent = 'Invalid URL format';
        }
        if (serverHealthContainer) {
            serverHealthContainer.style.display = 'flex';
        }
        return;
    }
    
    // Request permission
    const hasPermission = await requestCustomServerPermission(url);
    
    if (hasPermission) {
        // Save and check health
        chrome.storage.local.set({ customApiUrl: url }, () => {
            logger.info('Custom URL saved and permission granted');
        });
        checkServerHealth();
    } else {
        // Permission denied
        updateLoginButtonState(false);
        if (healthIndicator) {
            healthIndicator.className = 'health-indicator offline';
        }
        if (healthStatus) {
            healthStatus.textContent = 'Permission required';
        }
        if (serverHealthContainer) {
            serverHealthContainer.style.display = 'flex';
        }
    }
}

/**
 * Show custom server fields
 */
function showCustomFields() {
    if (customFieldsContainer) {
        customFieldsContainer.style.display = 'block';
    }
}

/**
 * Hide custom server fields
 */
function hideCustomFields() {
    if (customFieldsContainer) {
        customFieldsContainer.style.display = 'none';
    }
}

/**
 * Save just the server type to localStorage
 * @param {string} serverType - The server type to save
 * @returns {Promise<void>}
 */
async function saveServerType(serverType) {
    return new Promise((resolve, reject) => {
        chrome.storage.local.set({ serverType }, () => {
            if (chrome.runtime.lastError) {
                reject(chrome.runtime.lastError);
            } else {
                logger.info(`Server type ${serverType} saved`);
                resolve();
            }
        });
    });
}

/**
 * Save server settings to localStorage
 * @returns {Promise<void>}
 */
async function saveServerSettings() {
    if (!serverSelect) {
        return Promise.resolve();
    }
    
    const serverType = serverSelect.value;
    
    return new Promise((resolve, reject) => {
        if (serverType === 'CUSTOM') {
            // Validate custom URL
            if (!customApiInput) {
                reject(new Error('Custom URL input not found'));
                return;
            }
            
            const apiUrl = customApiInput.value.trim();
            
            if (!apiUrl) {
                showMessage('Please enter a server URL.', 'error');
                reject(new Error('Missing custom URL'));
                return;
            }
            
            // Basic URL validation
            try {
                new URL(apiUrl);
            } catch (e) {
                showMessage('Please enter a valid URL.', 'error');
                reject(new Error('Invalid URL'));
                return;
            }
            
            // Save custom URL (serverType already saved by handleServerSelectChange)
            chrome.storage.local.set({
                serverType: 'CUSTOM',
                customApiUrl: apiUrl
            }, () => {
                if (chrome.runtime.lastError) {
                    reject(chrome.runtime.lastError);
                } else {
                    logger.info('Custom server settings saved');
                    resolve();
                }
            });
        } else {
            // Server type already saved by handleServerSelectChange
            logger.info(`Server type ${serverType} already saved`);
            resolve();
        }
    });
}

/**
 * Update login button state based on server health
 * @param {boolean} enabled - Whether login should be enabled
 */
function updateLoginButtonState(enabled) {
    if (!loginButton) return;
    
    if (enabled) {
        loginButton.disabled = false;
        loginButton.style.opacity = '1';
        loginButton.style.cursor = 'pointer';
    } else {
        loginButton.disabled = true;
        loginButton.style.opacity = '0.5';
        loginButton.style.cursor = 'not-allowed';
    }
}

/**
 * Check LinkedIn OAuth configuration status
 */
async function checkLinkedInConfig() {
    try {
        // Get server URL
        const serverUrls = await appConfig.getServerUrls();
        const configUrl = `${serverUrls.apiUrl}/auth/linkedin/config-status`;
        
        logger.info(`Checking LinkedIn OAuth config at ${configUrl}`);
        
        // Simple fetch with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        
        const response = await fetch(configUrl, {
            method: 'GET',
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
            const config = await response.json();
            linkedinConfigured = config.is_configured;
            
            logger.info(`LinkedIn OAuth configured: ${linkedinConfigured}`);
            
            // Update UI based on configuration status
            updateLinkedInButtonState(linkedinConfigured, config.setup_instructions);
        } else {
            // Server responded but with error - assume configured to not block users
            linkedinConfigured = true;
            updateLinkedInButtonState(true, null);
            logger.warn(`LinkedIn config check returned: ${response.status}`);
        }
    } catch (error) {
        // If check fails, assume configured to not block users on network issues
        linkedinConfigured = true;
        updateLinkedInButtonState(true, null);
        logger.warn('LinkedIn config check failed:', error);
    }
}

/**
 * Start polling LinkedIn OAuth configuration every 10 seconds
 */
function startLinkedInConfigPolling() {
    // Clear any existing interval
    if (linkedinConfigCheckInterval) {
        clearInterval(linkedinConfigCheckInterval);
    }
    
    // Check every 10 seconds
    linkedinConfigCheckInterval = setInterval(() => {
        checkLinkedInConfig();
    }, 10000);
    
    logger.info('Started LinkedIn OAuth config polling (every 10 seconds)');
}

/**
 * Stop polling LinkedIn OAuth configuration
 */
function stopLinkedInConfigPolling() {
    if (linkedinConfigCheckInterval) {
        clearInterval(linkedinConfigCheckInterval);
        linkedinConfigCheckInterval = null;
        logger.info('Stopped LinkedIn OAuth config polling');
    }
}

/**
 * Start polling server health every 10 seconds
 */
function startHealthPolling() {
    // Clear any existing interval
    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
    }
    
    // Check every 10 seconds (same as OAuth polling)
    healthCheckInterval = setInterval(() => {
        checkServerHealth();
    }, 10000);
    
    logger.info('Started server health polling (every 10 seconds)');
}

/**
 * Stop polling server health
 */
function stopHealthPolling() {
    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
        healthCheckInterval = null;
        logger.info('Stopped server health polling');
    }
}

/**
 * Update LinkedIn login button state based on OAuth configuration
 * @param {boolean} isConfigured - Whether LinkedIn OAuth is configured
 * @param {string|null} instructions - Setup instructions if not configured
 */
function updateLinkedInButtonState(isConfigured, instructions) {
    if (!loginButton || !statusMessage) return;
    
    if (isConfigured) {
        // LinkedIn is configured - enable button and clear message
        loginButton.disabled = false;
        loginButton.style.opacity = '1';
        loginButton.style.cursor = 'pointer';
        loginButton.style.filter = 'none';
        
        // Hide OAuth warning message if it was showing
        if (statusMessage.classList.contains('oauth-warning')) {
            statusMessage.style.display = 'none';
            statusMessage.classList.remove('oauth-warning');
        }
    } else {
        // LinkedIn is NOT configured - disable button and show message
        loginButton.disabled = true;
        loginButton.style.opacity = '0.5';
        loginButton.style.cursor = 'not-allowed';
        loginButton.style.filter = 'grayscale(100%)';
        
        // Show warning message
        statusMessage.textContent = 'LinkedIn OAuth not configured on this server. Please configure LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET.';
        statusMessage.className = 'status-message error oauth-warning';
        statusMessage.style.display = 'block';
        
        logger.warn('LinkedIn OAuth not configured:', instructions);
    }
}

/**
 * Check server health (non-blocking)
 */
async function checkServerHealth() {
    try {
        // Show health indicator
        if (serverHealthContainer) {
            serverHealthContainer.style.display = 'flex';
        }
        
        // Reset to checking state
        if (healthIndicator) {
            healthIndicator.className = 'health-indicator checking';
        }
        if (healthStatus) {
            healthStatus.textContent = 'Checking server...';
        }
        
        // For custom server, use the input value directly
        let healthUrl;
        if (serverSelect && serverSelect.value === 'CUSTOM' && customApiInput) {
            const customUrl = customApiInput.value.trim();
            if (!customUrl) {
                // No URL entered yet
                updateLoginButtonState(false);
                return;
            }
            healthUrl = `${customUrl}/health`;
        } else {
            // Get configured server URL
            const serverUrls = await appConfig.getServerUrls();
            healthUrl = `${serverUrls.apiUrl}/health`;
        }
        
        logger.info(`Checking server health at ${healthUrl}`);
        
        // Simple fetch with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        
        const response = await fetch(healthUrl, {
            method: 'GET',
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
            // Server is online
            isServerOnline = true;
            if (healthIndicator) {
                healthIndicator.className = 'health-indicator online';
            }
            if (healthStatus) {
                healthStatus.textContent = 'Server is online';
            }
            logger.info('Server health check: ONLINE');
            
            // Enable login button
            updateLoginButtonState(true);
        } else {
            // Server responded but with error
            isServerOnline = false;
            if (healthIndicator) {
                healthIndicator.className = 'health-indicator offline';
            }
            if (healthStatus) {
                healthStatus.textContent = 'Server returned an error';
            }
            logger.warn(`Server health check: ERROR (${response.status})`);
            
            // Disable login button for ALL servers when offline
            updateLoginButtonState(false);
        }
    } catch (error) {
        // Server is offline or unreachable
        isServerOnline = false;
        if (healthIndicator) {
            healthIndicator.className = 'health-indicator offline';
        }
        if (healthStatus) {
            healthStatus.textContent = 'Server is offline';
        }
        logger.warn('Server health check: OFFLINE', error);
        
        // Disable login button for ALL servers when offline
        updateLoginButtonState(false);
    }
}

// Check if user is already authenticated
function checkExistingAuth() {
    // This check is non-blocking and doesn't prevent page load
    try {
        chrome.storage.local.get(['access_token'], function(result) {
            logger.info('Checking existing auth, token: ' + (result.access_token ? 'exists' : 'not found'));
            if (result.access_token) {
                logger.info('Already authenticated, redirecting to main page...');
                window.location.href = 'main.html';
            }
        });
    } catch (error) {
        // Silently handle errors - page should still be functional
        logger.warn('Failed to check existing auth', error);
    }
}

// Handle login button click
async function handleLoginClick() {
    // Check if server is online for ALL servers
    if (!isServerOnline) {
        const serverType = serverSelect ? serverSelect.value : 'MAIN';
        const serverName = serverType === 'CUSTOM' ? 'Custom server' : 'Main server';
        showMessage(`Cannot login: ${serverName} is offline. Please check the server status.`, 'error');
        return;
    }
    
    // For custom servers, ensure we have permission
    if (serverSelect && serverSelect.value === 'CUSTOM' && customApiInput) {
        const customUrl = customApiInput.value.trim();
        if (customUrl) {
            const hasPermission = await requestCustomServerPermission(customUrl);
            if (!hasPermission) {
                showMessage('Permission required to connect to custom server. Please grant permission and try again.', 'error');
                return;
            }
        }
    }
    
    // Save server settings before login
    await saveServerSettings();
    
    // Get current server URLs
    const serverUrls = await appConfig.getServerUrls();
    const authUrl = `${serverUrls.apiUrl}/auth/login/linkedin`; // URL to login endpoint
    const width = 600, height = 600;
    const left = (screen.width / 2) - (width / 2);
    const top = (screen.height / 2) - (height / 2);
    
    // Show loading message
    showMessage('Opening LinkedIn login...', 'info');
    
    // Open popup window for authentication
    const authWindow = window.open(
        authUrl, 
        "Authentication", 
        `toolbar=no, location=no, directories=no, status=no, menubar=no, scrollbars=yes, resizable=yes, copyhistory=no, width=${width}, height=${height}, top=${top}, left=${left}`
    );
    
    if (!authWindow) {
        showMessage('Failed to open authentication window. Please check your popup blocker settings.', 'error');
        logger.error("Failed to open authentication window");
        return;
    }
    
    // Add a timeout for the login window
    const authTimeout = setTimeout(() => {
        if (authWindow) {
            authWindow.close();
            showMessage('Authentication timed out. Please try again.', 'error');
            logger.error("Authentication timed out");
        }
    }, 120000); // 2 minute timeout
    
    // Listen for messages from the popup window
    window.addEventListener('message', async function handleAuthMessage(event) {
        logger.info(`Received message event from ${event.origin}`);
        
        // Get current server URLs for origin check
        const serverUrls = await appConfig.getServerUrls();
        
        // Check the origin
        if (event.origin !== serverUrls.apiUrl) {
            logger.warn(`Received message from untrusted origin: ${event.origin}`);
            return;
        }
        
        clearTimeout(authTimeout);
        
        // Handle the received authentication data
        logger.info('Sending message to background script...');
        
        // Send the message in the correct format expected by saveAuthSession
        // The data comes directly from the server, no need to transform it
        chrome.runtime.sendMessage({ 
            action: 'auth_session', 
            data: event.data  // The server already sends data in the correct format
        }, function(response) {
            logger.info(`Background script response: ${JSON.stringify(response)}`);
            
            if (response && response.success) {
                logger.info('Authentication successful, redirecting...');
                showMessage('Authentication successful! Redirecting...', 'info');
                // Redirect to main page after successful authentication
                setTimeout(() => {
                    window.location.href = 'dashboard/index.html'; // Updated to correct dashboard path
                }, 1500);
            } else {
                logger.error('Authentication failed');
                showMessage('Authentication failed. Please try again.', 'error');
            }
        });
        
        // Remove this listener after processing
        window.removeEventListener('message', handleAuthMessage);
    });
}

/**
 * Update login UI based on server type
 * @param {string} serverType - The selected server type (MAIN or CUSTOM)
 */
function updateLoginUIForServerType(serverType) {
    if (serverType === 'CUSTOM') {
        // Show email/password form for custom servers
        if (emailLoginForm) {
            emailLoginForm.style.display = 'block';
        }
        // Show divider between options
        if (loginDivider) {
            loginDivider.style.display = 'block';
        }
        // Show LinkedIn button for custom servers too (might be disabled)
        if (linkedinLoginContainer) {
            linkedinLoginContainer.style.display = 'block';
        }
        // Check LinkedIn config for custom servers
        checkLinkedInConfig();
    } else {
        // Hide email/password form for main server
        if (emailLoginForm) {
            emailLoginForm.style.display = 'none';
        }
        // Hide divider for main server
        if (loginDivider) {
            loginDivider.style.display = 'none';
        }
        // Show LinkedIn button for main server (always enabled)
        if (linkedinLoginContainer) {
            linkedinLoginContainer.style.display = 'block';
        }
        if (loginButton) {
            loginButton.disabled = false;
            loginButton.style.opacity = '1';
            loginButton.style.cursor = 'pointer';
        }
    }
}

/**
 * Validate redirect URI matches current server
 * @param {string} serverUrl - The server URL (e.g., https://your-server.com)
 * @returns {Promise<boolean>} - True if redirect URI is valid for this server
 */
async function validateRedirectUri(serverUrl) {
    try {
        // Expected redirect URI format: {serverUrl}/auth/user/callback
        const expectedCallback = `${serverUrl}/auth/user/callback`;
        
        // For custom servers, we can't easily check the LinkedIn app config
        // So we just verify the format is correct and use HTTPS
        const url = new URL(serverUrl);
        
        // Check if using HTTPS (required by LinkedIn)
        if (url.protocol !== 'https:' && !serverUrl.includes('localhost')) {
            logger.warn(`[LINKEDIN_CONFIG] Server not using HTTPS: ${serverUrl}`);
            return false;
        }
        
        logger.info(`[LINKEDIN_CONFIG] Redirect URI validation passed for: ${expectedCallback}`);
        return true;
        
    } catch (error) {
        logger.error(`[LINKEDIN_CONFIG] Error validating redirect URI:`, error);
        return false;
    }
}

/**
 * Handle email login button click
 */
async function handleEmailLoginClick() {
    if (!emailInput || !passwordInput) return;
    
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    
    // Validate inputs
    if (!email) {
        showMessage('Please enter your email address.', 'error');
        return;
    }
    
    if (!password) {
        showMessage('Please enter your password.', 'error');
        return;
    }
    
    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showMessage('Please enter a valid email address.', 'error');
        return;
    }
    
    // Check if server is online
    if (!isServerOnline) {
        showMessage('Cannot login: Server is offline. Please check the server status.', 'error');
        return;
    }
    
    // Disable button during login
    if (emailLoginBtn) {
        emailLoginBtn.disabled = true;
        emailLoginBtn.textContent = 'Logging in...';
    }
    
    try {
        showMessage('Logging in...', 'info');
        
        // Get current server URLs
        const serverUrls = await appConfig.getServerUrls();
        const loginUrl = `${serverUrls.apiUrl}/auth/login/email`;
        
        logger.info(`[EMAIL_LOGIN] Attempting login to: ${loginUrl}`);
        
        // Make login request
        const response = await fetch(loginUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email,
                password: password
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            logger.info('[EMAIL_LOGIN] Login successful');
            showMessage('Login successful! Redirecting...', 'info');
            
            // Save auth session (same format as LinkedIn OAuth)
            chrome.runtime.sendMessage({ 
                action: 'auth_session', 
                data: data
            }, function(saveResponse) {
                logger.info(`[EMAIL_LOGIN] Auth session saved: ${JSON.stringify(saveResponse)}`);
                
                if (saveResponse && saveResponse.success) {
                    // Redirect to dashboard
                    setTimeout(() => {
                        window.location.href = 'dashboard/index.html';
                    }, 1000);
                } else {
                    showMessage('Login successful but failed to save session. Please try again.', 'error');
                    if (emailLoginBtn) {
                        emailLoginBtn.disabled = false;
                        emailLoginBtn.textContent = 'Login / Register';
                    }
                }
            });
        } else {
            // Login failed
            logger.error(`[EMAIL_LOGIN] Login failed: ${data.detail || data.message}`);
            const errorMessage = data.detail || data.message || 'Login failed. Please try again.';
            showMessage(errorMessage, 'error');
            
            if (emailLoginBtn) {
                emailLoginBtn.disabled = false;
                emailLoginBtn.textContent = 'Login / Register';
            }
        }
    } catch (error) {
        logger.error('[EMAIL_LOGIN] Error during login:', error);
        showMessage('Error connecting to server. Please check your connection and try again.', 'error');
        
        if (emailLoginBtn) {
            emailLoginBtn.disabled = false;
            emailLoginBtn.textContent = 'Login / Register';
        }
    }
}

/**
 * Clear any previous version warning banner
 */
function clearPreviousVersionWarning() {
    const existingBanner = document.getElementById('backend-version-warning');
    if (existingBanner) {
        existingBanner.remove();
    }
}

/**
 * Check backend version compatibility (Phase 3.3)
 * Shows a warning banner if backend version is incompatible
 */
async function checkBackendVersion() {
    const context = 'login/index.checkBackendVersion';
    
    try {
        logger.info('Checking backend compatibility on login page', context);
        
        // Check compatibility without authentication
        const compatibility = await checkBackendCompatibility();
        
        if (!compatibility.compatible) {
            logger.warn(`Backend incompatible: ${compatibility.message}`, context);
            showBackendUpdateWarning(compatibility.backendVersion);
        } else {
            logger.info(`Backend compatible: v${compatibility.backendVersion}`, context);
        }
        
    } catch (error) {
        logger.error(`Version check failed: ${error.message}`, context);
        // Don't break login page if version check fails
    }
}

/**
 * Show backend update warning banner (Phase 3.3)
 * @param {string} backendVersion - Backend version detected
 */
function showBackendUpdateWarning(backendVersion) {
    const context = 'login/index.showBackendUpdateWarning';
    logger.info('Displaying backend update warning on login page', context);
    
    try {
        // Find the main container (login container)
        const loginContainer = document.querySelector('.login-container');
        if (!loginContainer) {
            logger.error('Login container not found', context);
            return;
        }
        
        // Clear any existing warning
        clearPreviousVersionWarning();
        
        // Build version message
        const MIN_VERSION = "1.1.0";
        let versionText = `Required: v${MIN_VERSION}`;
        if (backendVersion && backendVersion !== "unknown") {
            versionText += ` • Current: ${backendVersion}`;
        } else {
            versionText += ` • Current: Unknown`;
        }
        
        // Create warning banner
        const warningBanner = document.createElement('div');
        warningBanner.id = 'backend-version-warning';
        warningBanner.style.cssText = `
            background: #fef3c7;
            border: 1px solid #f59e0b;
            border-radius: 6px;
            padding: 10px 12px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        `;
        
        warningBanner.innerHTML = `
            <span style="font-size: 18px; flex-shrink: 0;">⚠️</span>
            <div style="flex: 1;">
                <strong style="color: #92400e; font-size: 13px;">Backend Update Required</strong>
                <span style="color: #78350f; font-size: 12px; margin-left: 8px;">${versionText}</span>
            </div>
        `;
        
        // Insert at the beginning of login container
        loginContainer.insertBefore(warningBanner, loginContainer.firstChild);
        
        logger.info('Backend update warning displayed on login page', context);
        
    } catch (error) {
        logger.error(`Failed to display warning banner: ${error.message}`, context);
    }
}

/**
 * Handle forgot password link click
 * @param {Event} e - Click event
 */
function handleForgotPasswordClick(e) {
    e.preventDefault();
    
    // Show contact administrator message
    showMessage(
        'To reset your password, please contact your server administrator.',
        'info'
    );
    
    logger.info('[FORGOT_PASSWORD] User requested password reset instructions');
}

// Initialize the page
document.addEventListener('DOMContentLoaded', init);

// Clean up intervals when page is unloaded
window.addEventListener('beforeunload', () => {
    stopLinkedInConfigPolling();
    stopHealthPolling();
});