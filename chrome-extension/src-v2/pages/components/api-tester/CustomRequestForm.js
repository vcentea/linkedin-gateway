//@ts-check
/// <reference types="chrome"/>

import { logger } from '../../../shared/utils/logger.js';

/**
 * Component for handling custom API requests
 */
export class CustomRequestForm {
    /**
     * @type {HTMLElement|null}
     */
    customSection = null;
    
    /**
     * @type {HTMLInputElement|null}
     */
    customEndpointInput = null;
    
    /**
     * @type {HTMLSelectElement|null}
     */
    customMethodSelect = null;
    
    /**
     * @type {HTMLTextAreaElement|null}
     */
    customBodyTextarea = null;
    
    /**
     * Creates a new CustomRequestForm instance
     * @param {Object} options - Configuration options
     * @param {HTMLElement} options.customSection - The container for custom request form
     * @param {HTMLInputElement} options.customEndpointInput - The custom endpoint input
     * @param {HTMLSelectElement} options.customMethodSelect - The custom method select
     * @param {HTMLTextAreaElement} options.customBodyTextarea - The custom body textarea
     */
    constructor({ customSection, customEndpointInput, customMethodSelect, customBodyTextarea }) {
        this.customSection = customSection;
        this.customEndpointInput = customEndpointInput;
        this.customMethodSelect = customMethodSelect;
        this.customBodyTextarea = customBodyTextarea;
    }
    
    /**
     * Resets the custom request form
     */
    resetForm() {
        if (this.customEndpointInput) {
            this.customEndpointInput.value = '';
        }
        
        if (this.customMethodSelect) {
            this.customMethodSelect.selectedIndex = 0;
        }
        
        if (this.customBodyTextarea) {
            this.customBodyTextarea.value = '';
        }
    }
    
    /**
     * Validates the custom request form
     * @returns {boolean} True if form is valid
     */
    validateForm() {
        // Check if endpoint is entered
        if (!this.customEndpointInput || !this.customEndpointInput.value.trim()) {
            logger.warn('Custom endpoint is required', 'CustomRequestForm');
            return false;
        }
        
        // Check if method is selected
        if (!this.customMethodSelect || !this.customMethodSelect.value) {
            logger.warn('Custom method is required', 'CustomRequestForm');
            return false;
        }
        
        // For POST/PUT/PATCH methods, body should be valid JSON if provided
        if (this.customBodyTextarea && 
            this.customBodyTextarea.value.trim() !== '' && 
            this.customMethodSelect.value.match(/^(POST|PUT|PATCH)$/i)) {
            
            try {
                JSON.parse(this.customBodyTextarea.value);
            } catch (error) {
                logger.warn(`Invalid JSON body for ${this.customMethodSelect.value} request`, 'CustomRequestForm');
                return false;
            }
        }
        
        return true;
    }
    
    /**
     * Gets the custom request data
     * @returns {Object|null} The custom request data or null if invalid
     */
    getRequestData() {
        if (!this.validateForm()) {
            return null;
        }
        
        const requestData = {
            endpoint: this.customEndpointInput?.value.trim() ?? '',
            method: this.customMethodSelect?.value ?? 'GET'
        };
        
        // Add body for POST/PUT/PATCH methods if provided
        if (this.customBodyTextarea && 
            this.customBodyTextarea.value.trim() !== '' && 
            requestData.method.match(/^(POST|PUT|PATCH)$/i)) {
            
            try {
                requestData.body = JSON.parse(this.customBodyTextarea.value);
            } catch (error) {
                // This should not happen if validateForm was called first
                logger.error('Invalid JSON body in getRequestData', 'CustomRequestForm');
                return null;
            }
        }
        
        return requestData;
    }
    
    /**
     * Shows or hides the custom request form
     * @param {boolean} visible - Whether to show the form
     */
    setVisible(visible) {
        if (this.customSection) {
            this.customSection.style.display = visible ? 'block' : 'none';
        }
    }
} 