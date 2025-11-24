//@ts-check

import { logger } from '../../../shared/utils/logger.js';
import { handleError, createError } from '../../../shared/utils/error-handler.js';
import { MESSAGE_TYPES } from '../../../shared/constants/message-types.js';
import { sendMessageToBackground } from '../../../shared/utils/chrome-messaging.js';

/**
 * Component for running local tests of utility functions
 */
export class LocalTestForm {
    /**
     * @type {HTMLFormElement|null}
     */
    formElement = null;

    /**
     * @type {HTMLButtonElement|null}
     */
    localTestButton = null;
    
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
     * Creates a new LocalTestForm instance
     * @param {HTMLFormElement|null} formElement - The form element for local testing.
     * @param {Object} options - Configuration options
     * @param {HTMLButtonElement|null} [options.localTestButton] - The button to trigger local test.
     * @param {HTMLElement|null} [options.responseContainer] - The container to display test results.
     * @param {HTMLElement|null} [options.loadingIndicator] - Optional loading indicator element.
     * @param {HTMLElement|null} [options.errorBox] - Optional error display element.
     * @param {Object} [options.functionMap] - Map of function names to functions.
     */
    constructor(formElement, options = {}) {
        this.formElement = formElement;
        this.localTestButton = options.localTestButton || null;
        this.responseContainer = options.responseContainer || null;
        this.loadingIndicator = options.loadingIndicator || null;
        this.errorBox = options.errorBox || null;
        // this.functionMap = options.functionMap || {}; // functionMap is not used in this class directly
        
        // Bind event handlers
        this.handleLocalTestSubmit = this.handleLocalTestSubmit.bind(this);
        
        // Initialize
        this.init();
    }
    
    /**
     * Initialize the form
     */
    init() {
        if (this.formElement) {
            this.formElement.addEventListener('submit', this.handleLocalTestSubmit);
        }
        if (this.localTestButton && !this.formElement) { // If form not present, button triggers
            this.localTestButton.addEventListener('click', this.handleLocalTestSubmit);
        }
    }
    
    /**
     * Handle form submission for local function test
     * @param {Event} event - The submit event
     */
    async handleLocalTestSubmit(event) {
        event.preventDefault();
        
        // Clear previous results and errors
        if (this.responseContainer) {
            this.responseContainer.innerHTML = '';
        }
        if (this.errorBox) {
            this.errorBox.textContent = '';
            this.errorBox.style.display = 'none';
        }
        this.showLoading(true);
        
        const endpointSelect = /** @type {HTMLSelectElement|null} */ (document.getElementById('endpoint-select'));
        const selectedEndpointValue = endpointSelect ? endpointSelect.value : null;

        if (!selectedEndpointValue) {
            this.showError('No endpoint selected for local testing.');
            this.showLoading(false);
            return;
        }
        
        try {
            const endpointConfig = this.findEndpointConfig(selectedEndpointValue);
            if (!endpointConfig) {
                throw createError('ConfigError', 'Could not find endpoint configuration for local testing.', 'LocalTestForm.handleLocalTestSubmit');
            }
            if (!endpointConfig.localTestUtility) {
                 throw createError('ConfigError', 'This endpoint does not support local testing.', 'LocalTestForm.handleLocalTestSubmit');
            }

            const params = this.collectParameters();
            logger.info(`Collected params for local test: ${JSON.stringify(params)}`, 'LocalTestForm.handleLocalTestSubmit');
            
            // Execute the function
            const result = await this.executeFunctionViaBackground(endpointConfig.localTestUtility, params);
            
            // Display results
            this.displayResult(result);
            
        } catch (error) {
            const err = (error instanceof Error) ? error : createError('UnknownError', String(error), 'LocalTestForm.handleLocalTestSubmit');
            handleError(err, 'LocalTestForm.handleLocalTestSubmit');
            this.showError(err.message);
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Finds the endpoint configuration by endpoint value from a data attribute
     * @param {string} endpointValue - The endpoint value to find
     * @returns {any|null} The endpoint configuration or null if not found
     */
    findEndpointConfig(endpointValue) {
        const endpointsDataElement = document.getElementById('endpoints-data');
        if (!endpointsDataElement || !endpointsDataElement.dataset || !endpointsDataElement.dataset.endpoints) {
            logger.warn('Endpoints data element or dataset not found', 'LocalTestForm.findEndpointConfig');
            return null;
        }
        
        try {
            const endpoints = JSON.parse(endpointsDataElement.dataset.endpoints);
            return endpoints.find(e => e.endpoint === endpointValue) || null;
        } catch (error) {
            const err = (error instanceof Error) ? error : createError('ParseError', 'Error parsing endpoints data', 'LocalTestForm.findEndpointConfig');
            handleError(err, 'LocalTestForm.findEndpointConfig');
            return null;
        }
    }
    
    /**
     * Collects parameter values from the form fields within 'params-container'
     * @returns {Object} Object containing parameter values
     */
    collectParameters() {
        const paramsContainer = document.getElementById('params-container');
        if (!paramsContainer) {
            return {};
        }
        
        const params = {};
        const inputs = paramsContainer.querySelectorAll('input, select, textarea');
        
        inputs.forEach((inputEl) => {
            // Ensure inputEl is an instance of a form element that has name and value
            if (inputEl instanceof HTMLInputElement || 
                inputEl instanceof HTMLSelectElement || 
                inputEl instanceof HTMLTextAreaElement) {
                
                if (inputEl.name && inputEl.value.trim() !== '') {
                    const paramValueStr = inputEl.value;
                    let paramValueProcessed = /** @type {string|number|any} */ (paramValueStr); // Initialize with string value, allow reassignment to number/any
                    
                    // Try to parse as JSON if it starts with [ or {
                    if ((paramValueStr.startsWith('{') && paramValueStr.endsWith('}')) ||
                        (paramValueStr.startsWith('[') && paramValueStr.endsWith(']'))) {
                        try {
                            paramValueProcessed = JSON.parse(paramValueStr);
                        } catch (e) {
                            // If parsing fails, keep as string
                            logger.warn(`Failed to parse JSON parameter ${inputEl.name}: ${(e instanceof Error? e.message : String(e))}`);
                        }
                    } else if (paramValueStr.trim() !== '' && !isNaN(Number(paramValueStr))) {
                        // Convert numeric strings to numbers if they are not empty strings and are valid numbers
                        paramValueProcessed = Number(paramValueStr);
                    }
                    params[inputEl.name] = paramValueProcessed;
                }
            }
        });
        
        return params;
    }
    
    /**
     * Executes a function via background script
     * Uses the background script to execute the LinkedIn function directly
     * 
     * @param {string} functionName - The name of the function to execute
     * @param {Object} params - The parameters to pass to the function
     * @returns {Promise<any>} - The result of the function execution
     */
    async executeFunctionViaBackground(functionName, params) {
        const logContext = 'LocalTestForm:executeFunctionViaBackground';
        logger.info(`Executing local function ${functionName} via background script...`, logContext);
        
        try {
            // 1. Check if LinkedIn is connected first
            logger.info(`Checking LinkedIn connection status...`, logContext);
            const statusResponse = await sendMessageToBackground({
                type: MESSAGE_TYPES.GET_LINKEDIN_STATUS
            });
            
            if (!statusResponse || !statusResponse.enabled) {
                throw createError('ConnectionError', 'LinkedIn is not connected. Please log in to LinkedIn first.');
            }
            
            // 2. Execute function directly using EXECUTE_FUNCTION message
            logger.info(`Executing function ${functionName} with params: ${JSON.stringify(params)}`, logContext);
            const response = await sendMessageToBackground({
                type: MESSAGE_TYPES.EXECUTE_FUNCTION,
                data: {
                    functionName,
                    params
                }
            });
            
            // 3. Process response
            if (!response) {
                throw createError('ExecutionError', 'No response from background script for EXECUTE_FUNCTION');
            }
            if (response.error) {
                throw createError('ExecutionError', `Error executing function: ${response.error}`);
            }
            
            logger.info(`Function ${functionName} executed successfully`, logContext);
            return response.data;
            
        } catch (error) {
            const err = error instanceof Error ? error : createError('UnknownError', String(error), logContext);
            handleError(err, logContext); // Log the original or created error
            throw err; // Re-throw the error to be caught by the caller
        }
    }
    
    /**
     * Display the result in the responseContainer
     * @param {any} data - The result to display
     */
    displayResult(data) {
        if (!this.responseContainer) {
            logger.warn('Response container not found for displaying results.', 'LocalTestForm');
            return;
        }
        
        try {
            this.responseContainer.style.display = 'block';
            let resultText;
            if (typeof data === 'string') {
                resultText = data;
            } else if (data === undefined) {
                resultText = '[No data returned]';
            } else {
                resultText = JSON.stringify(data, null, 2);
            }
            this.responseContainer.innerHTML = `<pre>${resultText}</pre>`;
        } catch (error) {
            const errMessage = error instanceof Error ? error.message : String(error);
            this.responseContainer.innerHTML = `<p class="error">Error displaying results: ${errMessage}</p>`;
            handleError(createError('DisplayError', `Error rendering result: ${errMessage}`, 'LocalTestForm.displayResult'));
        }
    }

    /**
     * Shows an error message in the errorBox
     * @param {string} message - The error message to display
     */
    showError(message) {
        if (this.errorBox) {
            this.errorBox.textContent = message;
            this.errorBox.style.display = 'block';
        } else {
            // Fallback if no specific errorBox is configured
            const errorToShow = createError('DisplayError', `Error to display (no errorBox): ${message}`, 'LocalTestForm');
            logger.error(errorToShow); // Pass Error object to logger
            if (this.responseContainer) {
                this.responseContainer.innerHTML = `<p class="error">Error: ${message}</p>`;
                this.responseContainer.style.display = 'block';
            } else {
                alert(`Error: ${message}`); // Last resort
            }
        }
    }
    
    /**
     * Shows or hides the loading indicator and updates button state
     * @param {boolean} isLoading - Whether to show loading state
     */
    showLoading(isLoading) {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = isLoading ? 'block' : 'none';
        }
        
        if (this.localTestButton) {
            this.localTestButton.disabled = isLoading;
            this.localTestButton.textContent = isLoading ? 'Testing...' : 'Test Locally';
        }
    }
} 