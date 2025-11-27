//@ts-check
/// <reference types="chrome"/>

import { logger } from '../../../shared/utils/logger.js';

/**
 * Component for handling API parameter inputs
 */
export class ParameterForm {
    /**
     * @type {HTMLElement|null}
     */
    paramsContainer = null;
    
    /**
     * Creates a new ParameterForm instance
     * @param {Object} options - Configuration options
     * @param {HTMLElement} options.paramsContainer - The container for parameter inputs
     */
    constructor({ paramsContainer }) {
        this.paramsContainer = paramsContainer;
    }
    
    /**
     * Builds parameter input fields based on the endpoint definition
     * @param {Array<any>} params - The parameter definitions
     * @param {Object} [endpointConfig] - Optional endpoint configuration for rawBody mode
     */
    buildParameterInputs(params, endpointConfig = null) {
        if (!this.paramsContainer) {
            logger.warn('Parameter container element not found', 'ParameterForm');
            return;
        }
        
        this.paramsContainer.innerHTML = '';
        
        // Check if this is a rawBody endpoint (like native Gemini API)
        if (endpointConfig && endpointConfig.rawBody) {
            // First build any path parameters (like model_path)
            if (params && params.length > 0) {
                params.forEach(param => {
                    if (param.hidden) return;
                    this._buildSingleParamInput(param);
                });
            }
            // Then build the raw body textarea
            this._buildRawBodyInput(endpointConfig);
            return;
        }
        
        if (!params || params.length === 0) {
            this.paramsContainer.innerHTML = '<p style="font-style: italic; color: #666;">No parameters for this endpoint.</p>';
            return;
        }
        
        params.forEach(param => {
            // Skip hidden parameters (e.g., key for Gemini endpoints - already sent via header)
            if (param.hidden) {
                return;
            }
            
            const paramDiv = document.createElement('div');
            paramDiv.className = 'param-group';
            
            const label = document.createElement('label');
            // Use label field if provided, otherwise format the parameter name
            const displayName = param.label || param.name.split('_').map(word => 
                word.charAt(0).toUpperCase() + word.slice(1)
            ).join(' ');
            label.textContent = `${displayName}${param.required ? ' *' : ''}:`;
            label.htmlFor = `param-${param.name}`;
            
            let input;
            if (param.type === 'textarea') {
                input = document.createElement('textarea');
                input.id = `param-${param.name}`;
                input.name = param.name;
                input.placeholder = param.placeholder || '';
                input.rows = param.rows || 4;
            } else if (param.type === 'json') {
                // JSON type - use textarea with JSON formatting
                input = document.createElement('textarea');
                input.id = `param-${param.name}`;
                input.name = param.name;
                input.dataset.type = 'json'; // Mark as JSON for parsing
                input.placeholder = param.placeholder || 'Enter valid JSON...';
                input.rows = param.rows || 6;
                input.style.fontFamily = 'monospace';
                input.style.fontSize = '12px';
            } else if (param.type === 'select' && param.options) {
                input = document.createElement('select');
                input.id = `param-${param.name}`;
                input.name = param.name;
                
                // Add options to select
                param.options.forEach(option => {
                    const optionEl = document.createElement('option');
                    optionEl.value = option.value;
                    optionEl.textContent = option.label;
                    input.appendChild(optionEl);
                });
            } else {
                input = document.createElement('input');
                input.type = param.type || 'text';
                input.id = `param-${param.name}`;
                input.name = param.name;
                
                // Set placeholder - use provided placeholder, or format default if available
                if (param.placeholder) {
                    input.placeholder = param.placeholder;
                } else if (param.default !== undefined) {
                    input.placeholder = `Default: ${param.default}`;
                } else {
                    input.placeholder = '';
                }
                
                // Add min/max constraints for number inputs
                if (input.type === 'number') {
                    if (param.min !== undefined) {
                        input.min = param.min.toString();
                    }
                    if (param.max !== undefined) {
                        input.max = param.max.toString();
                    }
                }
            }
            
            // Add common attributes
            if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement || input instanceof HTMLSelectElement) {
                input.required = !!param.required;
                
                // Set default value if provided
                if (param.default !== undefined && param.default !== null) {
                    input.value = param.default.toString();
                }
                
                // Add tooltip/description if provided
                if (param.description) {
                    input.title = param.description;
                    
                    // Also add a help icon with tooltip
                    const helpIcon = document.createElement('span');
                    helpIcon.className = 'help-icon';
                    helpIcon.textContent = 'ⓘ';
                    helpIcon.title = param.description;
                    helpIcon.style.cursor = 'help';
                    helpIcon.style.marginLeft = '5px';
                    helpIcon.style.fontSize = '0.8em';
                    helpIcon.style.color = '#555';
                    label.appendChild(helpIcon);
                }
            }
            
            paramDiv.appendChild(label);
            paramDiv.appendChild(input);
            this.paramsContainer.appendChild(paramDiv);
        });
    }
    
    /**
     * Collects parameter values from the form
     * @returns {Object} Object containing parameter values
     */
    getParameterValues() {
        if (!this.paramsContainer) {
            logger.warn('Parameter container element not found', 'ParameterForm');
            return {};
        }
        
        const params = {};
        
        // Get all input, select, and textarea elements
        const inputs = this.paramsContainer.querySelectorAll('input, select, textarea');
        
        inputs.forEach((input) => {
            if (input instanceof HTMLInputElement || 
                input instanceof HTMLSelectElement || 
                input instanceof HTMLTextAreaElement) {
                
                // Only include parameters that have values
                if (input.value.trim() !== '') {
                    // Check if this is a rawBody field - parse and return as special marker
                    if (input.dataset && input.dataset.type === 'rawBody') {
                        try {
                            // Parse JSON and store with special key
                            params._rawBody = JSON.parse(input.value);
                        } catch (e) {
                            logger.warn(`Invalid JSON in rawBody: ${e.message}`, 'ParameterForm');
                            // Store raw string so validation can catch it
                            params._rawBody = input.value;
                        }
                    }
                    // Check if this is a JSON type field
                    else if (input.dataset && input.dataset.type === 'json') {
                        try {
                            // Parse JSON and store as object/array
                            params[input.name] = JSON.parse(input.value);
                        } catch (e) {
                            // If JSON parsing fails, store as string and let validation catch it
                            logger.warn(`Invalid JSON in field ${input.name}: ${e.message}`, 'ParameterForm');
                            params[input.name] = input.value;
                        }
                    } else if (input.type === 'number') {
                        // Parse number fields
                        params[input.name] = parseFloat(input.value);
                    } else if (input.type === 'checkbox') {
                        // Handle checkbox boolean
                        params[input.name] = input.checked;
                    } else {
                        params[input.name] = input.value;
                    }
                }
            }
        });
        
        return params;
    }
    
    /**
     * Validates that all required parameters have values
     * @returns {boolean} True if all required parameters are valid
     */
    validateParameters() {
        if (!this.paramsContainer) {
            logger.warn('Parameter container element not found', 'ParameterForm');
            return true; // No parameters to validate
        }
        
        // Get all required inputs
        const requiredInputs = this.paramsContainer.querySelectorAll('input[required], select[required], textarea[required]');
        
        // Check if all required inputs have values
        for (let i = 0; i < requiredInputs.length; i++) {
            const input = requiredInputs[i];
            if (input instanceof HTMLInputElement || 
                input instanceof HTMLSelectElement || 
                input instanceof HTMLTextAreaElement) {
                
                if (!input.value.trim()) {
                    return false;
                }
            }
        }
        
        return true;
    }
    
    /**
     * Resets all parameter inputs
     */
    resetParameters() {
        if (!this.paramsContainer) {
            logger.warn('Parameter container element not found', 'ParameterForm');
            return;
        }
        
        const inputs = this.paramsContainer.querySelectorAll('input, select, textarea');
        
        inputs.forEach((input) => {
            if (input instanceof HTMLInputElement || 
                input instanceof HTMLSelectElement || 
                input instanceof HTMLTextAreaElement) {
                
                input.value = '';
            }
        });
    }
    
    /**
     * Builds a single parameter input field
     * @param {Object} param - The parameter definition
     * @private
     */
    _buildSingleParamInput(param) {
        if (!this.paramsContainer) return;
        
        const paramDiv = document.createElement('div');
        paramDiv.className = 'param-group';
        
        const label = document.createElement('label');
        const displayName = param.label || param.name.split('_').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
        label.textContent = `${displayName}${param.required ? ' *' : ''}:`;
        label.htmlFor = `param-${param.name}`;
        
        const input = document.createElement('input');
        input.type = param.type || 'text';
        input.id = `param-${param.name}`;
        input.name = param.name;
        input.required = !!param.required;
        
        if (param.placeholder) {
            input.placeholder = param.placeholder;
        } else if (param.default !== undefined) {
            input.placeholder = `Default: ${param.default}`;
        }
        
        if (param.default !== undefined && param.default !== null) {
            input.value = param.default.toString();
        }
        
        if (param.description) {
            input.title = param.description;
            const helpIcon = document.createElement('span');
            helpIcon.className = 'help-icon';
            helpIcon.textContent = 'ⓘ';
            helpIcon.title = param.description;
            helpIcon.style.cursor = 'help';
            helpIcon.style.marginLeft = '5px';
            helpIcon.style.fontSize = '0.8em';
            helpIcon.style.color = '#555';
            label.appendChild(helpIcon);
        }
        
        paramDiv.appendChild(label);
        paramDiv.appendChild(input);
        this.paramsContainer.appendChild(paramDiv);
    }
    
    /**
     * Builds a raw JSON body input for pass-through endpoints (e.g., native Gemini API)
     * @param {Object} endpointConfig - The endpoint configuration
     * @private
     */
    _buildRawBodyInput(endpointConfig) {
        if (!this.paramsContainer) return;
        
        const paramDiv = document.createElement('div');
        paramDiv.className = 'param-group';
        
        // Create label with description
        const label = document.createElement('label');
        label.textContent = 'Request Body (JSON):';
        label.htmlFor = 'param-rawBody';
        
        // Add description if provided
        if (endpointConfig.description) {
            const descDiv = document.createElement('div');
            descDiv.style.cssText = 'font-size: 12px; color: #666; margin-bottom: 8px; font-style: italic;';
            descDiv.textContent = endpointConfig.description;
            paramDiv.appendChild(descDiv);
        }
        
        // Create textarea for raw JSON body
        const textarea = document.createElement('textarea');
        textarea.id = 'param-rawBody';
        textarea.name = '_rawBody';
        textarea.dataset.type = 'rawBody';
        textarea.rows = 20;
        textarea.style.cssText = 'font-family: monospace; font-size: 12px; width: 100%; resize: vertical;';
        textarea.placeholder = 'Enter the full JSON request body...';
        textarea.required = true;
        
        // Set example body if provided
        if (endpointConfig.rawBodyExample) {
            textarea.value = endpointConfig.rawBodyExample;
        }
        
        // Add help text
        const helpText = document.createElement('small');
        helpText.style.cssText = 'display: block; margin-top: 4px; color: #888;';
        helpText.textContent = 'This body is sent directly to the API. Authentication is handled via the API Key header above.';
        
        paramDiv.appendChild(label);
        paramDiv.appendChild(textarea);
        paramDiv.appendChild(helpText);
        this.paramsContainer.appendChild(paramDiv);
    }
} 