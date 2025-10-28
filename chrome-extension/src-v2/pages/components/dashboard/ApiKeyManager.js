/// <reference types="chrome"/>

import { logger } from '../../../shared/utils/logger.js';
import { handleError, createError } from '../../../shared/utils/error-handler.js';
import { MESSAGE_TYPES } from '../../../shared/constants/message-types.js';
import { sendMessageToBackground } from '../../../background/services/messaging.service.js';
import apiConfig from '../../../shared/config/api.config.js';

/**
 * ApiKeyManager component for handling API key operations
 */
export class ApiKeyManager {
    /**
     * @type {HTMLElement|null}
     */
    container = null;
    
    /**
     * @type {string|null}
     */
    fullApiKey = null;
    
    constructor() {
        this.container = document.getElementById('api-key-container');
        this.fullApiKey = null; // Temporarily stores the key after generation
        
        if (!this.container) {
            logger.error('API key container not found', 'ApiKeyManager');
            return;
        }
        
        logger.info('Initializing ApiKeyManager', 'ApiKeyManager');
        this.initialize();
    }
    
    /**
     * Initialize the component
     */
    initialize() {
        try {
        this.render();
            this.loadApiKeyStatus(); // Only load status/existence, not the key itself
        } catch (error) {
            handleError(error, 'ApiKeyManager.initialize');
        }
    }
    
    /**
     * Render the component UI
     */
    render() {
        logger.info('Rendering API key manager', 'ApiKeyManager');
        
        try {
        this.container.innerHTML = `
            <div class="api-key-section" style="font-size: 15px;">
                <div id="api-key-display" style="display: none;">
                    <p style="overflow-wrap: break-word; margin: 12px 0; line-height: 1.6;">
                        <strong style="color: #2c3e50;">Your API Key:</strong> 
                        <span id="api-key-value" class="masked-key" style="color: #5a6c7d;">••••••••••••••••</span>
                    </p>
                    <div class="button-group" style="display: flex; gap: 12px; margin-top: 20px; flex-wrap: wrap;">
                        <button id="toggle-key-visibility" class="button secondary" style="background-color: #ffffff; color: #5a6c7d; border: 1px solid #e0e7ee; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px; transition: all 0.2s ease;">Show Key</button>
                        <button id="copy-api-key" class="button secondary" style="background-color: #ffffff; color: #5a6c7d; border: 1px solid #e0e7ee; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px; transition: all 0.2s ease;">Copy</button>
                        <button id="delete-api-key" class="button danger" style="background-color: #ef4444; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px; transition: all 0.2s ease;">Delete</button>
                    </div>
                </div>
                
                <div id="no-api-key-message">
                    <p style="margin: 12px 0; line-height: 1.6;">You don't have an API key yet. Generate one to access the LinkedIn Gateway API.</p>
                    <button id="generate-api-key" class="button primary" style="background-color: #0077b5; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px; transition: all 0.2s ease; margin-top: 12px;">Generate API Key</button>
                </div>
                
                <div id="api-key-info" style="margin-top: 20px;">
                    <p class="info-text" style="font-size: 14px; color: #7f8c9a; line-height: 1.5; margin: 8px 0;">Your API key provides secure access to the LinkedIn Gateway API.</p>
                    <p class="info-text" style="font-size: 14px; color: #7f8c9a; line-height: 1.5; margin: 8px 0;">Keep it confidential and do not share it with others.</p>
                </div>
            </div>
        `;
        this.addEventListeners();
        } catch (error) {
            handleError(error, 'ApiKeyManager.render');
        }
    }
    
    /**
     * Add event listeners to buttons
     */
    addEventListeners() {
        try {
            /** @type {HTMLButtonElement | null} */
            const generateButton = document.getElementById('generate-api-key');
            /** @type {HTMLButtonElement | null} */
            const toggleButton = document.getElementById('toggle-key-visibility');
            /** @type {HTMLButtonElement | null} */
            const copyButton = document.getElementById('copy-api-key');
            /** @type {HTMLButtonElement | null} */
            const deleteButton = document.getElementById('delete-api-key');
            
            if (generateButton) {
                generateButton.addEventListener('click', () => this.generateApiKey());
                this.addButtonHoverEffects(generateButton, true);
            }
            if (toggleButton) {
                // Hide toggle button initially until a key is generated in this session
                toggleButton.style.display = 'none';
                toggleButton.addEventListener('click', () => this.toggleKeyVisibility());
                this.addButtonHoverEffects(toggleButton, false);
            }
            if (copyButton) {
                // Hide copy button initially until a key is generated in this session
                copyButton.style.display = 'none';
                copyButton.addEventListener('click', () => this.copyApiKey());
                this.addButtonHoverEffects(copyButton, false);
            }
            if (deleteButton) {
                deleteButton.addEventListener('click', () => this.deleteApiKey());
                this.addButtonHoverEffects(deleteButton, false, true);
            }
        } catch (error) {
            handleError(error, 'ApiKeyManager.addEventListeners');
        }
    }
    
    /**
     * Add hover effects to buttons
     * @param {HTMLButtonElement} button - The button element
     * @param {boolean} isPrimary - Whether it's a primary button
     * @param {boolean} isDanger - Whether it's a danger button
     */
    addButtonHoverEffects(button, isPrimary, isDanger = false) {
        button.addEventListener('mouseover', () => {
            if (button.disabled) return;
            if (isPrimary) {
                button.style.backgroundColor = '#006097';
                button.style.transform = 'translateY(-1px)';
                button.style.boxShadow = '0 4px 8px rgba(0,119,181,0.2)';
            } else if (isDanger) {
                button.style.backgroundColor = '#dc2626';
                button.style.transform = 'translateY(-1px)';
                button.style.boxShadow = '0 4px 8px rgba(239,68,68,0.2)';
            } else {
                button.style.backgroundColor = '#f8fafc';
                button.style.borderColor = '#cbd5e0';
            }
        });
        
        button.addEventListener('mouseout', () => {
            if (button.disabled) return;
            if (isPrimary) {
                button.style.backgroundColor = '#0077b5';
                button.style.transform = 'translateY(0)';
                button.style.boxShadow = 'none';
            } else if (isDanger) {
                button.style.backgroundColor = '#ef4444';
                button.style.transform = 'translateY(0)';
                button.style.boxShadow = 'none';
            } else {
                button.style.backgroundColor = '#ffffff';
                button.style.borderColor = '#e0e7ee';
            }
        });
    }
    
    /**
     * Load *status* of API key from backend (checks if metadata exists)
     */
    async loadApiKeyStatus() {
        const logContext = 'ApiKeyManager:loadApiKeyStatus';
        logger.info('Starting API key status check', logContext);
        this.fullApiKey = null; // Ensure key is cleared on load
        
        try {
            logger.info('Sending GET_API_KEY message to background', logContext);
            
            // Use a timeout to prevent indefinite hanging if backend is down
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('Request timeout')), 5000);
            });
            
            // Background now returns { success, keyExists, error? }
            const response = await Promise.race([
                sendMessageToBackground({ type: MESSAGE_TYPES.GET_API_KEY }),
                timeoutPromise
            ]);
            
            logger.info(`Received response from background for GET_API_KEY: ${JSON.stringify(response)}`, logContext);
            
            // Check if the call was successful and if the key exists
            if (response && response.success) { 
                logger.info(`API key exists: ${response.keyExists ? 'Yes' : 'No'}`, logContext);
                this.updateApiKeyUI(response.keyExists); // Update UI based on existence flag
            } else {
                logger.error(`Failed to get API key status: ${response?.error || 'Unknown error'}`, logContext);
                this.updateApiKeyUI(false); // Update UI to show no key message on failure
            }
        } catch (error) {
            // Catch errors from sendMessageToBackground itself or timeout
            handleError(error, logContext);
            logger.error(`Error sending message during API key status check: ${error.message}`, logContext);
            this.updateApiKeyUI(false); // Assume no key on error
        }
    }
    
    /**
     * Generate a new API key
     */
    async generateApiKey() {
        logger.info('Generating new API key', 'ApiKeyManager');
        const confirmGenerate = confirm('Are you sure you want to generate a new API key? This will invalidate any existing key.');
        if (!confirmGenerate) return;
        
        // Optionally add a loading state here
        
        try {
            const response = await sendMessageToBackground({ type: MESSAGE_TYPES.GENERATE_API_KEY });
            
            if (response && response.success && response.key) {
                this.fullApiKey = response.key; // Store the newly generated key
                this.updateApiKeyUI(true, true); // Update UI and show the key immediately
                
                // Show buttons now that we have the key stored temporarily
                const toggleButton = document.getElementById('toggle-key-visibility');
                const copyButton = document.getElementById('copy-api-key');
                
                if (toggleButton instanceof HTMLButtonElement) toggleButton.style.display = 'inline-block';
                if (copyButton instanceof HTMLButtonElement) copyButton.style.display = 'inline-block';
                
                alert('API key generated successfully! Please copy it now, it won\'t be shown again after reload.');
            } else {
                logger.warn('Generate API key response negative or missing key', 'ApiKeyManager', response);
                alert('Failed to generate API key. Please try again.');
                this.fullApiKey = null;
                this.updateApiKeyUI(false);
            }
        } catch (error) {
            handleError(error, 'ApiKeyManager.generateApiKey');
            alert('Failed to generate API key. Please try again.');
            this.fullApiKey = null;
            this.updateApiKeyUI(false);
        }
    }
    
    /**
     * Delete the current API key
     */
    async deleteApiKey() {
        logger.info('Deleting API key', 'ApiKeyManager');
        const confirmDelete = confirm('Are you sure you want to delete your API key? This action cannot be undone.');
        if (!confirmDelete) return;

        // Optionally add a loading state here
        
        try {
            const response = await sendMessageToBackground({ type: MESSAGE_TYPES.DELETE_API_KEY });
            
            if (response && response.success) {
                this.fullApiKey = null; // Clear the stored key
                this.updateApiKeyUI(false); // Update UI to show no key message
                
                 // Ensure toggle/copy buttons are hidden
                const toggleButton = document.getElementById('toggle-key-visibility');
                const copyButton = document.getElementById('copy-api-key');
                
                if (toggleButton instanceof HTMLButtonElement) toggleButton.style.display = 'none';
                if (copyButton instanceof HTMLButtonElement) copyButton.style.display = 'none';
                
                alert('API key deleted successfully!');
            } else {
                logger.warn('Delete API key response negative', 'ApiKeyManager', response);
                alert('Failed to delete API key. Please try again.');
            }
        } catch (error) {
            handleError(error, 'ApiKeyManager.deleteApiKey');
            alert('Failed to delete API key. Please try again.');
        }
    }
    
    /**
     * Toggle API key visibility (uses temporarily stored key)
     */
    toggleKeyVisibility() {
        try {
        const keyElement = document.getElementById('api-key-value');
        const toggleButton = document.getElementById('toggle-key-visibility');
        
            if (!keyElement || !toggleButton) {
                throw createError('DomError', 'Required key elements not found', 'ApiKeyManager.toggleKeyVisibility');
            }
        
        if (this.fullApiKey) { // Only toggle if key is stored from recent generation
            if (keyElement.classList.contains('masked-key')) {
                keyElement.textContent = this.fullApiKey;
                keyElement.classList.remove('masked-key');
                toggleButton.textContent = 'Hide Key';
            } else {
                keyElement.textContent = '••••••••••••••••';
                keyElement.classList.add('masked-key');
                toggleButton.textContent = 'Show Key';
            }
        } else {
                logger.warn('Toggle visibility called but no fullApiKey is stored (key not generated in this session?)', 'ApiKeyManager');
             // Optionally alert the user they need to generate a key to see it
                alert('Please generate a new key to view it.');
            }
        } catch (error) {
            handleError(error, 'ApiKeyManager.toggleKeyVisibility');
        }
    }
    
    /**
     * Copy API key to clipboard (uses temporarily stored key)
     */
    async copyApiKey() {
        try {
        if (!this.fullApiKey) {
                logger.warn('Copy attempted but no key available (key not generated in this session?)', 'ApiKeyManager');
            alert('API key not available to copy. Please generate a key first.');
            return;
        }
        
            logger.info('Copying API key to clipboard', 'ApiKeyManager');
            await navigator.clipboard.writeText(this.fullApiKey);
                alert('API key copied to clipboard!');
        } catch (error) {
            handleError(error, 'ApiKeyManager.copyApiKey');
                alert('Failed to copy API key to clipboard.');
        }
    }
    
    /**
     * Test API key by making a request to the API using the API controller
     */
    async testApiKeyWithFeedRequest() {
        logger.info('Testing API key with API request', 'ApiKeyManager');

        try {
        if (!this.fullApiKey) {
                logger.warn('Cannot test API key: Key not available (was it generated this session?)', 'ApiKeyManager');
            alert('API key is not available for testing. Please generate the key first in this session.');
            return;
        }

            // Use the API_REQUEST message type to test the key through the background service
            const requestData = {
                method: 'POST',
                endpoint: '/posts/request-feed',
                params: {
                    start_index: 0,
                    count: 5
                },
                headers: {
                    'X-API-Key': this.fullApiKey
                }
            };

            const message = {
                type: MESSAGE_TYPES.API_REQUEST,
                data: requestData
            };
            
            logger.info('Sending test API request', 'ApiKeyManager');

            const response = await sendMessageToBackground(message);
            
            if (!response) {
                throw createError('ApiError', 'No response received from API', 'ApiKeyManager.testApiKeyWithFeedRequest');
            }
            
            if (response.success) {
                logger.info('Test API key successful!', 'ApiKeyManager');
                alert('Successfully tested API key! The API is working correctly.');
            } else {
                logger.warn('Test API key failed', 'ApiKeyManager', response.error);
                alert(`Failed to test API key: ${response.error || 'Unknown error'}`);
            }
        } catch (error) {
            handleError(error, 'ApiKeyManager.testApiKeyWithFeedRequest');
            alert('An error occurred while testing the API key. Make sure the backend service is running.');
        }
    }
    
    /**
     * Update the UI based on key presence and visibility choice
     * @param {boolean} keyExists - Whether an API key exists (based on metadata check)
     * @param {boolean} showKey - Whether to show the key value immediately (only after generation)
     */
    updateApiKeyUI(keyExists, showKey = false) {
        try {
            const keyDisplay = document.getElementById('api-key-display');
            const noKeyMessage = document.getElementById('no-api-key-message');
            const keyElement = document.getElementById('api-key-value');
            const toggleButton = document.getElementById('toggle-key-visibility');
            const copyButton = document.getElementById('copy-api-key');
            
            if (!keyDisplay || !noKeyMessage || !keyElement || !toggleButton || !copyButton) {
                throw createError('DomError', 'UI elements for API key not found during update', 'ApiKeyManager.updateApiKeyUI');
            }

            if (keyExists) {
                keyDisplay.style.display = 'block';
                noKeyMessage.style.display = 'none';
                
                // Only show show/copy buttons if we actually have the key stored temporarily
                const showButtons = !!this.fullApiKey;
                toggleButton.style.display = showButtons ? 'inline-block' : 'none';
                copyButton.style.display = showButtons ? 'inline-block' : 'none';

                if (showKey && this.fullApiKey) {
                    keyElement.textContent = this.fullApiKey;
                    keyElement.classList.remove('masked-key');
                    toggleButton.textContent = 'Hide Key';
                } else {
                    keyElement.textContent = '••••••••••••••••';
                    keyElement.classList.add('masked-key');
                    toggleButton.textContent = 'Show Key';
                }
            } else {
                keyDisplay.style.display = 'none';
                noKeyMessage.style.display = 'block';
                this.fullApiKey = null; // Ensure stored key is cleared
                toggleButton.style.display = 'none';
                copyButton.style.display = 'none';
            }
        } catch (error) {
            handleError(error, 'ApiKeyManager.updateApiKeyUI');
        }
    }
    
    /**
     * Show or hide the toggle and copy buttons
     * @param {boolean} show - Whether to show or hide the buttons
     */
    enableKeyActionButtons(show) {
        try {
            /** @type {HTMLButtonElement | null} */
            const toggleButton = document.getElementById('toggle-key-visibility');
            /** @type {HTMLButtonElement | null} */
            const copyButton = document.getElementById('copy-api-key');
            
            if (toggleButton) toggleButton.style.display = show ? 'inline-block' : 'none';
            if (copyButton) copyButton.style.display = show ? 'inline-block' : 'none';
        } catch (error) {
            handleError(error, 'ApiKeyManager.enableKeyActionButtons');
        }
    }
} 