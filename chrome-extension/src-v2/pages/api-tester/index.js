//@ts-check
/// <reference types="chrome"/>

import { ApiTester } from '../components/api-tester/ApiTester.js';
import { Header } from '../components/common/Header.js';
import { logger } from '../../shared/utils/logger.js';
import { MESSAGE_TYPES } from '../../shared/constants/message-types.js';
import { handleError } from '../../shared/utils/error-handler.js';
import { sendMessageToBackground } from '../../background/services/messaging.service.js';
import appConfig from '../../shared/config/app.config.js';
import apiConfig from '../../shared/config/api.config.js';

/**
 * Extend Window interface to include our custom functions
 * @typedef {Object} CustomWindow
 * @property {(endpoint: string, requestData: any, responseData: any) => void} displayApiTransaction
 */

/**
 * @type {Window & typeof globalThis & CustomWindow}
 */
const customWindow = window;

/**
 * DOM Elements
 * @type {HTMLButtonElement|null}
 */
const backBtn = /** @type {HTMLButtonElement|null} */ (document.getElementById('backBtn'));

/**
 * Component instances
 * @type {Header|null}
 */
let header = null;

/**
 * @type {ApiTester|null}
 */
let apiTester = null;

/**
 * Function to update the API request display dynamically
 * @param {string} endpoint - The API endpoint
 * @param {string} method - The HTTP method
 * @param {any} params - Request parameters
 */
customWindow.updateRequestDisplay = async function(endpoint, method, params) {
    const requestDisplay = document.getElementById('api-request-display');
    
    if (requestDisplay) {
        try {
            // ALWAYS get current server URL dynamically
            const serverUrls = await appConfig.getServerUrls();
            const baseUrl = serverUrls.apiUrl || '[API_URL not defined]';
            const paramsJson = JSON.stringify(params, null, 2);
            
            // Get API key from input
            const apiKeyInput = document.getElementById('api-key-input');
            const apiKey = apiKeyInput instanceof HTMLInputElement ? apiKeyInput.value : '';
            
            // Build headers object
            const headers = {
                'Content-Type': 'application/json',
                'X-API-Key': apiKey || 'your_api_key_here'
            };
            const headersJson = JSON.stringify(headers, null, 2);
            
            requestDisplay.innerHTML = `
                <strong>Method:</strong> ${method}<br>
                <strong>Endpoint:</strong> ${baseUrl}${endpoint}<br>
                <strong>Headers:</strong><pre style="margin: 0.25rem 0 0 0;">${headersJson}</pre>
                <strong>Body/Parameters:</strong><pre style="margin: 0.25rem 0 0 0;">${paramsJson}</pre>
            `;
        } catch (error) {
            requestDisplay.innerHTML = `<span class="error-message"><strong>Error:</strong> ${error.message}</span>`;
        }
    }
};

/**
 * Function to display API response
 * @param {any} responseData - Response data
 */
customWindow.displayApiResponse = function(responseData) {
    const responseDisplay = document.getElementById('api-response-display');
    
    if (responseDisplay) {
        responseDisplay.innerHTML = `<pre>${JSON.stringify(responseData, null, 2)}</pre>`;
    }
};

/**
 * Initialize the API Tester page
 */
async function init() {
    logger.info('API Tester page initializing', 'index.js');
    
    try {
    // Create request/response display elements
    createDisplayElements();
    
    // Initialize components
    header = new Header();
    apiTester = new ApiTester();
    
    // Set up event listeners
    setupEventListeners();
    
    // Load user profile to populate header
    await loadUserProfile();
        
        logger.info('API Tester page initialized successfully', 'index.js');
    } catch (error) {
        handleError(error, 'init');
        showError('Failed to initialize API Tester page: ' + error.message);
    }
}

/**
 * Create display elements for request/response - insert before submit button
 */
function createDisplayElements() {
    const apiForm = document.getElementById('api-form');
    if (!apiForm) return;
    
    // Find the actions div (contains submit buttons)
    const actionsDiv = apiForm.querySelector('.actions');
    if (!actionsDiv) return;
    
    // Create request display section
    const requestSection = document.createElement('div');
    requestSection.className = 'request-section';
    requestSection.style.marginBottom = '1.5rem';
    requestSection.innerHTML = `
        <h3 style="margin-top: 0; margin-bottom: 0.5rem;">API Request Preview</h3>
        <div id="api-request-display" class="code-display">
            <em style="color: #666;">Select an endpoint and fill in parameters to see the request preview...</em>
        </div>
    `;
    
    // Insert request display before the actions div
    apiForm.insertBefore(requestSection, actionsDiv);
    
    // Create response display section after the form
    const container = document.getElementById('api-tester-container');
    if (!container) return;
    
    const responseSection = document.createElement('div');
    responseSection.className = 'response-section';
    responseSection.style.marginTop = '1.5rem';
    responseSection.innerHTML = `
        <h3 style="margin-top: 0; margin-bottom: 0.5rem;">API Response</h3>
        <div id="api-response-display" class="code-display" style="display: none;">
            <em style="color: #666;">Response will appear here after sending the request...</em>
        </div>
    `;
    
    // Append response section after the form
    container.appendChild(responseSection);
    
    // Add styles
    const style = document.createElement('style');
    style.textContent = `
        .code-display {
            background-color: #f5f5f5;
            padding: 1rem;
            border-radius: 4px;
            font-family: monospace;
            font-size: 13px;
            white-space: pre-wrap;
            overflow-x: auto;
            border: 1px solid #ddd;
            min-height: 60px;
        }
        .code-display pre {
            margin: 0;
        }
        .code-display p {
            margin: 0.25rem 0;
        }
    `;
    document.head.appendChild(style);
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Back button click handler
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            logger.info('Back button clicked, navigating to dashboard', 'index.js');
            window.location.href = '/dashboard/index.html';
        });
    } else {
        logger.warn('Error: Back button not found in DOM', 'index.js');
    }
}

/**
 * Load user profile data
 */
async function loadUserProfile() {
    logger.info('Requesting user profile from background service worker for header', 'index.js');
    
    try {
        // Request user profile from background service worker using sendMessageToBackground
        // Use a timeout to prevent indefinite hanging if backend is down
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Request timeout')), 5000);
        });
        
        const response = await Promise.race([
            sendMessageToBackground({ type: MESSAGE_TYPES.GET_USER_PROFILE }),
            timeoutPromise
        ]);
        
        logger.info('User profile response received for header', 'index.js');
        
        if (!response || !response.authenticated) {
            logger.warn('Header: Not authenticated or invalid response. Redirecting to login.', 'index.js');
            // Redirect to login page if not authenticated
            window.location.href = '/auth/login.html';
            return; // Stop further execution
        }
        
        // We have a valid user profile, update the header
        if (response.userData && header) {
            header.updateUserInfo(response.userData);
            logger.info('Header updated successfully.', 'index.js');
        } else {
            logger.warn('Header: User data missing in response or header component not initialized.', 'index.js');
            showError('Could not load user information for the header.');
        }

    } catch (error) {
        handleError(error, 'loadUserProfile');
        showError(`Could not load your profile for the header: ${error.message}. Please try reloading or logging in again.`);
        
        // Optionally, hide elements that require user data or show a placeholder
        const userNameElement = document.getElementById('userName');
        if (userNameElement) userNameElement.textContent = 'Error';
    }
}

/**
 * Show error message in a dedicated area or console
 * @param {string} message - Error message to display
 */
function showError(message) {
    logger.error(`Error displayed: ${message}`, 'index.js'); // Log error for debugging
    // Attempt to display error in the API tester's error box if available
    const errorBox = document.getElementById('api-error'); 
    if (errorBox) {
        errorBox.textContent = message;
        errorBox.style.display = 'block';
    } else {
        // Fallback: Insert error at the top of main
        const main = document.querySelector('main');
        if (main) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-box'; // Use existing style if possible
            errorDiv.style.display = 'block';
            errorDiv.style.backgroundColor = 'rgba(211, 47, 47, 0.1)';
            errorDiv.style.color = '#d32f2f';
            errorDiv.style.padding = '1rem';
            errorDiv.style.borderRadius = '4px';
            errorDiv.style.marginBottom = '1.5rem';
            errorDiv.textContent = `Error: ${message}`;
            main.insertBefore(errorDiv, main.firstChild);
        } else {
            console.error("Could not display error message in UI: ", message); // Log to console as last resort
        }
    }
}

// Initialize on DOM content loaded
document.addEventListener('DOMContentLoaded', init); 