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
     */
    buildParameterInputs(params) {
        if (!this.paramsContainer) {
            logger.warn('Parameter container element not found', 'ParameterForm');
            return;
        }
        
        this.paramsContainer.innerHTML = '';
        
        if (!params || params.length === 0) {
            this.paramsContainer.innerHTML = '<p style="font-style: italic; color: #666;">No parameters for this endpoint.</p>';
            return;
        }
        
        params.forEach(param => {
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
                    params[input.name] = input.value;
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
} 