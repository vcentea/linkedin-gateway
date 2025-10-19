//@ts-check
/// <reference types="chrome"/>

import { logger } from '../../../shared/utils/logger.js';

/**
 * Component for displaying API responses
 */
export class ResponseDisplay {
    /**
     * @type {HTMLElement|null}
     */
    responseContainer = null;
    
    /**
     * @type {HTMLElement|null}
     */
    loadingIndicator = null;
    
    /**
     * @type {HTMLElement|null}
     */
    errorBox = null;
    
    /**
     * Creates a new ResponseDisplay instance
     * @param {Object} options - Configuration options
     * @param {HTMLElement} options.responseContainer - The container to display the response
     * @param {HTMLElement} [options.loadingIndicator] - Optional loading indicator element
     * @param {HTMLElement} [options.errorBox] - Optional error display element
     */
    constructor({ responseContainer, loadingIndicator, errorBox }) {
        this.responseContainer = responseContainer;
        this.loadingIndicator = loadingIndicator || null;
        this.errorBox = errorBox || null;
    }
    
    /**
     * Displays the API response
     * @param {any} data - The response data to display
     */
    displayResponse(data) {
        if (!this.responseContainer) {
            logger.warn('Response container element not found', 'ResponseDisplay');
            return;
        }
        
        // Clear loading state
        this.showLoading(false);
        
        // Clear any previous error
        this.clearError();
        
        try {
            // Show response container
            this.responseContainer.style.display = 'block';
            
            // Create a formatted display of the response
            let responseHtml = '';
            
            if (typeof data === 'object') {
                // Pretty-print JSON
                responseHtml = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
            } else {
                // Handle string or other types
                responseHtml = `<pre>${data}</pre>`;
            }
            
            this.responseContainer.innerHTML = responseHtml;
            
            logger.info('Response displayed successfully', 'ResponseDisplay');
        } catch (error) {
            logger.error(`Error displaying response: ${error.message}`, 'ResponseDisplay');
            this.responseContainer.innerHTML = `<p class="error">Error displaying response: ${error.message}</p>`;
        }
    }
    
    /**
     * Displays an error message
     * @param {string} message - The error message to display
     */
    showError(message) {
        logger.error(`API Error: ${message}`, 'ResponseDisplay');
        
        if (this.errorBox) {
            this.errorBox.textContent = message;
            this.errorBox.style.display = 'block';
        } else if (this.responseContainer) {
            // Fallback to showing error in response container
            this.responseContainer.innerHTML = `<p class="error">Error: ${message}</p>`;
            this.responseContainer.style.display = 'block';
        }
    }
    
    /**
     * Clears any displayed error
     */
    clearError() {
        if (this.errorBox) {
            this.errorBox.textContent = '';
            this.errorBox.style.display = 'none';
        }
    }
    
    /**
     * Clears the response display
     */
    clearResponse() {
        if (this.responseContainer) {
            this.responseContainer.innerHTML = '';
            this.responseContainer.style.display = 'none';
        }
    }
    
    /**
     * Shows or hides the loading indicator
     * @param {boolean} isLoading - Whether to show loading state
     */
    showLoading(isLoading) {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = isLoading ? 'block' : 'none';
        }
    }
} 