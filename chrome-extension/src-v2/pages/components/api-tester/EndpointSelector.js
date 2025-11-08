//@ts-check
/// <reference types="chrome"/>

import { logger } from '../../../shared/utils/logger.js';
import { handleError, createError } from '../../../shared/utils/error-handler.js';
import appConfig from '../../../shared/config/app.config.js';
import apiConfig from '../../../shared/config/api.config.js';

/**
 * Component for selecting API endpoints from a dropdown
 */
export class EndpointSelector {
    /**
     * @type {HTMLSelectElement|null}
     */
    endpointSelect = null;
    
    /**
     * @type {HTMLElement|null}
     */
    methodDisplay = null;
    
    /**
     * @type {HTMLElement|null}
     */
    fullUrlDisplay = null;
    
    /**
     * @type {HTMLElement|null}
     */
    endpointDescription = null;
    
    /**
     * @type {HTMLElement|null}
     */
    customSection = null;
    
    /**
     * @type {Array<any>}
     */
    endpoints = [];
    
    /**
     * @type {Function|null}
     */
    onEndpointChanged = null;

    /**
     * Creates a new EndpointSelector instance
     * @param {Object} options - Configuration options
     * @param {HTMLSelectElement} options.endpointSelect - The endpoint select element
     * @param {HTMLElement} options.methodDisplay - The method display element
     * @param {HTMLElement} options.fullUrlDisplay - The full URL display element
     * @param {HTMLElement} options.endpointDescription - The endpoint description element
     * @param {HTMLElement} options.customSection - The custom section element
     * @param {Function} options.onEndpointChanged - Callback for when endpoint selection changes
     */
    constructor({ endpointSelect, methodDisplay, fullUrlDisplay, endpointDescription, customSection, onEndpointChanged }) {
        this.endpointSelect = endpointSelect;
        this.methodDisplay = methodDisplay;
        this.fullUrlDisplay = fullUrlDisplay;
        this.endpointDescription = endpointDescription;
        this.customSection = customSection;
        this.onEndpointChanged = onEndpointChanged;
        
        // Setup event listeners
        if (this.endpointSelect) {
            this.endpointSelect.addEventListener('change', () => this.handleEndpointChange());
        } else {
            logger.warn('Endpoint select element not provided', 'EndpointSelector');
        }
    }
    
    /**
     * Initializes the endpoint selector with the provided endpoints
     * @param {Array<any>} endpoints - The endpoints to populate the selector with
     */
    initialize(endpoints) {
        this.endpoints = endpoints;
        this.populateEndpointDropdown();
    }
    
    /**
     * Populates the endpoint dropdown with the available endpoints
     */
    populateEndpointDropdown() {
        if (!this.endpointSelect) {
            logger.warn('Endpoint select element not found in DOM', 'EndpointSelector');
            return;
        }

        this.endpointSelect.innerHTML = '';
        
        this.endpoints.forEach(endpoint => {
            const option = document.createElement('option');
            option.value = endpoint.endpoint;
            option.textContent = endpoint.name;
            if (endpoint.description) {
                option.title = endpoint.description;
            }
            this.endpointSelect.appendChild(option);
        });
        
        // Trigger change to populate initial parameters
        this.handleEndpointChange();
    }
    
    /**
     * Handles endpoint selection change event
     */
    async handleEndpointChange() {
        if (!this.endpointSelect) return;
        
        const selectedEndpointValue = this.endpointSelect.value;
        const endpointConfig = this.endpoints.find(e => e.endpoint === selectedEndpointValue);
        
        if (!endpointConfig) return;
        
        // Update method display
        if (this.methodDisplay) {
            this.methodDisplay.textContent = selectedEndpointValue === 'custom' 
                ? 'Method: Select from custom section below'
                : `Method: ${endpointConfig.method}`;
        }
        
        // Update URL display
        if (this.fullUrlDisplay) {
            if (selectedEndpointValue === 'custom') {
                this.fullUrlDisplay.textContent = 'URL: Enter custom endpoint below';
            } else {
                try {
                    // ALWAYS get current server URL dynamically
                    const serverUrls = await appConfig.getServerUrls();
                    const baseUrl = serverUrls.apiUrl;
                    if (!baseUrl) {
                        throw createError('ConfigError', 'API_URL is not defined from appConfig.getServerUrls()', 'EndpointSelector.handleEndpointChange');
                    }
                    this.fullUrlDisplay.textContent = `URL: ${baseUrl}${endpointConfig.endpoint}`;
                } catch (error) {
                    handleError(error, 'EndpointSelector.handleEndpointChange');
                    this.fullUrlDisplay.textContent = `Error: API URL configuration issue`;
                }
            }
        }
        
        // Update description
        if (this.endpointDescription && endpointConfig.description) {
            this.endpointDescription.textContent = endpointConfig.description;
            this.endpointDescription.style.display = 'block';
        } else if (this.endpointDescription) {
            this.endpointDescription.style.display = 'none';
        }
        
        // Show/hide custom section
        if (this.customSection) {
            this.customSection.style.display = selectedEndpointValue === 'custom' ? 'block' : 'none';
        }
        
        // Notify parent of the change
        if (this.onEndpointChanged && typeof this.onEndpointChanged === 'function') {
            this.onEndpointChanged(endpointConfig);
        }
    }
    
    /**
     * Gets the currently selected endpoint
     * @returns {any|null} The selected endpoint configuration or null if not found
     */
    getSelectedEndpoint() {
        if (!this.endpointSelect) return null;
        
        const selectedEndpointValue = this.endpointSelect.value;
        return this.endpoints.find(e => e.endpoint === selectedEndpointValue) || null;
    }
} 