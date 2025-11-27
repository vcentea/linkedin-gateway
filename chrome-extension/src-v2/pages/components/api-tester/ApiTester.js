//@ts-check
/// <reference types="chrome"/>

import { logger } from '../../../shared/utils/logger.js';
import { handleError, createError } from '../../../shared/utils/error-handler.js';
import { MESSAGE_TYPES } from '../../../shared/constants/message-types.js';
import { sendMessageToBackground } from '../../../background/services/messaging.service.js';
import appConfig from '../../../shared/config/app.config.js';
import apiConfig from '../../../shared/config/api.config.js';

import { EndpointSelector } from './EndpointSelector.js';
import { ParameterForm } from './ParameterForm.js';
import { ResponseDisplay } from './ResponseDisplay.js';
import { CustomRequestForm } from './CustomRequestForm.js';
import { LocalTestForm } from './LocalTestForm.js';

/**
 * Main ApiTester component for testing API endpoints
 * This is a refactored version that uses smaller, focused components
 */
export class ApiTester {
    /**
     * @type {HTMLElement|null}
     */
    container = null;
    
    /**
     * @type {HTMLFormElement|null}
     */
    form = null;
    
    /**
     * @type {HTMLButtonElement|null}
     */
    submitButton = null;
    
    /**
     * @type {EndpointSelector|null}
     */
    endpointSelector = null;
    
    /**
     * @type {ParameterForm|null}
     */
    parameterForm = null;
    
    /**
     * @type {ResponseDisplay|null}
     */
    responseDisplay = null;
    
    /**
     * @type {CustomRequestForm|null}
     */
    customRequestForm = null;
    
    /**
     * @type {LocalTestForm|null}
     */
    localTestForm = null;
    
    /**
     * @type {Array<any>}
     */
    endpoints = [];
    
    /**
     * @type {any|null}
     */
    currentEndpoint = null;
    
    /**
     * Creates a new ApiTester instance
     */
    constructor() {
        this.container = document.getElementById('api-tester-container');
        this.form = document.getElementById('api-form');
        
        if (!this.container || !this.form) {
            logger.error('API Tester container or form not found in DOM', 'ApiTester');
            return;
        }
        
        this.submitButton = document.getElementById('submit-api');
        
        // Initialize
        this.init();
    }
    
    /**
     * Initializes the ApiTester component
     */
    async init() {
        logger.info('Initializing API Tester component', 'ApiTester');
        
        try {
            // Initialize sub-components
            this.initializeSubComponents();
            
            // Try to fetch API schema from backend first (auto-populate)
            await this.fetchApiSchema();
            
            // If schema fetch failed or returned no endpoints, fall back to JSON file
            if (!this.endpoints || this.endpoints.length === 0) {
                logger.info('[API_TESTER] No endpoints from schema, falling back to endpoints.json', 'ApiTester');
                await this.loadEndpoints();
            }
            
            // Initialize endpoint selector with endpoints
            if (this.endpointSelector) {
                this.endpointSelector.initialize(this.endpoints);
            }
            
            // Set up main form event listener
            if (this.form) {
                this.form.addEventListener('submit', (e) => this.handleSubmit(e));
            }
            
            // Check server type and configure server_call restrictions
            await this.configureServerCallRestrictions();
            
            logger.info('API Tester component initialized successfully', 'ApiTester');
        } catch (error) {
            handleError(error, 'ApiTester.init');
            this.showError('Could not initialize API Tester: ' + error.message);
        }
    }
    
    /**
     * Initializes sub-components
     */
    initializeSubComponents() {
        // Initialize EndpointSelector
        this.endpointSelector = new EndpointSelector({
            endpointSelect: /** @type {HTMLSelectElement|null} */ (document.getElementById('endpoint-select')),
            methodDisplay: document.getElementById('method-display'),
            fullUrlDisplay: document.getElementById('full-url-display'),
            endpointDescription: document.getElementById('endpoint-description'),
            customSection: document.getElementById('custom-section'),
            onEndpointChanged: (endpoint) => this.handleEndpointChange(endpoint)
        });
        
        // Initialize ParameterForm
        this.parameterForm = new ParameterForm({
            paramsContainer: document.getElementById('params-container')
        });
        
        // Initialize ResponseDisplay
        this.responseDisplay = new ResponseDisplay({
            responseContainer: document.getElementById('response-container'),
            loadingIndicator: document.getElementById('api-loading'),
            errorBox: document.getElementById('api-error')
        });
        
        // Initialize CustomRequestForm
        this.customRequestForm = new CustomRequestForm({
            customSection: document.getElementById('custom-section'),
            customEndpointInput: /** @type {HTMLInputElement|null} */ (document.getElementById('custom-endpoint')),
            customMethodSelect: /** @type {HTMLSelectElement|null} */ (document.getElementById('custom-method')),
            customBodyTextarea: /** @type {HTMLTextAreaElement|null} */ (document.getElementById('custom-body'))
        });
        
        // Initialize LocalTestForm
        // Note: There's no separate form for local testing, just a button
        // Pass null for formElement and rely on the button
        this.localTestForm = new LocalTestForm(
            null, // No separate form element
            { // Pass other elements as options
                localTestButton: /** @type {HTMLButtonElement|null} */ (document.getElementById('test-locally-btn')),
                responseContainer: document.getElementById('response-container'),
                loadingIndicator: document.getElementById('api-loading'),
                errorBox: document.getElementById('api-error')
            }
        );
        
        // Store endpoints in a data attribute for LocalTestForm to find
        const endpointsData = document.createElement('div');
        endpointsData.id = 'endpoints-data';
        endpointsData.style.display = 'none';
        this.container.appendChild(endpointsData);
    }
    
    /**
     * Configures server_call restrictions based on server type
     */
    async configureServerCallRestrictions() {
        try {
            // Get server type from storage
            const result = await new Promise((resolve) => {
                chrome.storage.local.get(['serverType'], resolve);
            });
            
            const serverType = result.serverType || 'MAIN';
            const isDefaultServer = serverType === 'MAIN';
            
            logger.info(`[API_TESTER] Server type: ${serverType}, is default: ${isDefaultServer}`, 'configureServerCallRestrictions');
            
            // Store this information for use in endpoint handling
            this.isDefaultServer = isDefaultServer;
            
            const serverCallToggle = document.getElementById('server-call-toggle');
            const serverCallLabel = /** @type {HTMLElement|null} */ (document.querySelector('label[for="server-call-toggle"]'));
            const serverCallHelp = serverCallLabel?.nextElementSibling;
            
            if (serverCallToggle instanceof HTMLInputElement) {
                if (isDefaultServer) {
                    // Default server: disable server_call checkbox
                    serverCallToggle.checked = false;
                    serverCallToggle.disabled = true;
                    
                    if (serverCallLabel) {
                        serverCallLabel.style.opacity = '0.6';
                        serverCallLabel.title = 'Server-side execution is not available on the default production server';
                    }
                    
                    if (serverCallHelp && serverCallHelp.tagName === 'SMALL') {
                        serverCallHelp.textContent = '⚠️ Server-side execution requires your own private server. All requests on the default server use the secure proxy.';
                        serverCallHelp.style.color = '#f59e0b';
                        serverCallHelp.style.fontWeight = '500';
                    }
                } else {
                    // Custom server: enable server_call checkbox
                    serverCallToggle.disabled = false;
                    serverCallToggle.checked = false; // Default to proxy mode
                    
                    if (serverCallLabel) {
                        serverCallLabel.style.opacity = '1';
                        serverCallLabel.title = 'Toggle between server-side and proxy execution (via browser extension)';
                    }
                    
                    if (serverCallHelp && serverCallHelp.tagName === 'SMALL') {
                        serverCallHelp.textContent = 'When enabled, LinkedIn API calls execute on the backend server. When disabled (default), calls execute via client/WebSocket.';
                        serverCallHelp.style.color = '#666';
                        serverCallHelp.style.fontWeight = 'normal';
                    }
                }
            }
        } catch (error) {
            handleError(error, 'ApiTester.configureServerCallRestrictions');
            logger.warn('Failed to configure server call restrictions, continuing anyway', 'ApiTester');
        }
    }
    
    /**
     * Handles endpoint change events from the EndpointSelector
     * @param {any} endpoint - The selected endpoint
     */
    handleEndpointChange(endpoint) {
        this.currentEndpoint = endpoint;
        
        logger.info(`[API_TESTER] Endpoint changed to: ${endpoint.name}`, 'ApiTester.handleEndpointChange');
        logger.info(`[API_TESTER] Endpoint has ${endpoint.params?.length || 0} parameters:`, 'ApiTester.handleEndpointChange', endpoint.params);
        logger.info(`[API_TESTER] Endpoint rawBody mode: ${!!endpoint.rawBody}`, 'ApiTester.handleEndpointChange');
        
        // Build parameter inputs based on the selected endpoint
        // Pass the full endpoint config for rawBody endpoints
        if (this.parameterForm) {
            this.parameterForm.buildParameterInputs(endpoint.params || [], endpoint);
        }
        
        // Handle server_call toggle for all endpoints
        const serverCallToggle = document.getElementById('server-call-toggle');
        const serverCallLabel = /** @type {HTMLElement|null} */ (document.querySelector('label[for="server-call-toggle"]'));
        const serverCallContainer = serverCallToggle?.closest('.form-group');
        
        if (serverCallToggle instanceof HTMLInputElement) {
            // Check if using default server (set in configureServerCallRestrictions)
            const isDefaultServer = this.isDefaultServer !== undefined ? this.isDefaultServer : true;
            
            // For Gemini endpoints, hide the server_call toggle entirely (always server-side)
            if (endpoint.geminiAuth) {
                serverCallToggle.checked = false; // Not used, but set to false
                serverCallToggle.disabled = true;
                if (serverCallContainer) {
                    serverCallContainer.style.display = 'none';
                }
            } else if (isDefaultServer) {
                // Default server: always disabled for LinkedIn endpoints
                if (serverCallContainer) {
                    serverCallContainer.style.display = '';
                }
                serverCallToggle.checked = false;
                serverCallToggle.disabled = true;
                if (serverCallLabel) {
                    serverCallLabel.style.opacity = '0.6';
                    serverCallLabel.title = 'Server-side execution is not available on the default production server. You need your own private server.';
                }
            } else if (endpoint.serverOnly) {
                // Custom server with server-only endpoint: checked and disabled
                if (serverCallContainer) {
                    serverCallContainer.style.display = '';
                }
                serverCallToggle.checked = true;
                serverCallToggle.disabled = true;
                if (serverCallLabel) {
                    serverCallLabel.style.opacity = '0.6';
                    serverCallLabel.title = 'This endpoint only supports server-side execution';
                }
            } else {
                // Custom server with dual-mode endpoint: enabled
                if (serverCallContainer) {
                    serverCallContainer.style.display = '';
                }
                serverCallToggle.disabled = false;
                serverCallToggle.checked = false; // Default to proxy mode
                if (serverCallLabel) {
                    serverCallLabel.style.opacity = '1';
                    serverCallLabel.title = 'Toggle between server-side and proxy execution (via browser extension)';
                }
            }
        }
        
        // Update URL display and custom form visibility
        if (endpoint.endpoint === 'custom') {
            if (this.customRequestForm) {
                this.customRequestForm.setVisible(true);
            }
        } else {
            if (this.customRequestForm) {
                this.customRequestForm.setVisible(false);
            }
        }
        
        // Update test locally button visibility and enabled state
        const localTestButton = /** @type {HTMLButtonElement|null} */ (document.getElementById('test-locally-btn'));
        if (localTestButton) {
            const supportsLocalTest = !!endpoint.localTestUtility;
            localTestButton.style.display = supportsLocalTest ? 'inline-block' : 'none';
            localTestButton.disabled = !supportsLocalTest; // Enable if supported, disable otherwise
        }
        
        // Clear any previous responses
        if (this.responseDisplay) {
            this.responseDisplay.clearResponse();
            this.responseDisplay.clearError();
        }
        
        // Store updated endpoints data for LocalTestForm
        const endpointsData = document.getElementById('endpoints-data');
        if (endpointsData) {
            endpointsData.dataset.endpoints = JSON.stringify(this.endpoints);
        }
        
        // Update request preview
        this.updateRequestPreview();
        
        // Set up listeners for parameter changes
        this.setupParameterChangeListeners();
    }
    
    /**
     * Loads API endpoints from JSON
     */
    async loadEndpoints() {
        try {
            // We'll use the imported JSON directly
            const apiEndpointsUrl = chrome.runtime.getURL('/shared/api/endpoints.json');
            const response = await fetch(apiEndpointsUrl);
            
            if (!response.ok) {
                throw createError('FetchError', `Failed to load endpoints: ${response.status} ${response.statusText}`, 'ApiTester.loadEndpoints');
            }
            
            this.endpoints = await response.json();
            logger.info(`Loaded ${this.endpoints.length} endpoint(s) from JSON`, 'ApiTester');
        } catch (error) {
            handleError(error, 'ApiTester.loadEndpoints');
            
            // Initialize with empty array as fallback
            this.endpoints = [];
            
            throw error;
        }
    }
    
    /**
     * Fetches the OpenAPI schema from the backend server and builds endpoint list
     */
    async fetchApiSchema() {
        const context = 'ApiTester.fetchApiSchema';
        try {
            // ALWAYS get current server URL dynamically
            const serverUrls = await appConfig.getServerUrls();
            const schemaUrl = `${serverUrls.apiUrl}/openapi.json`;
            logger.info(`[API_SCHEMA] Fetching API schema from (DYNAMIC): ${schemaUrl}`, context);
            
            const response = await fetch(schemaUrl);
            
            if (!response.ok) {
                throw createError('FetchError', `Failed to fetch API schema: ${response.status} ${response.statusText}`, context);
            }
            
            const schema = await response.json();
            logger.info(`[API_SCHEMA] Successfully received API schema from backend`, context);
            logger.info(`[API_SCHEMA] Schema version: ${schema.openapi || 'unknown'}`, context);
            logger.info(`[API_SCHEMA] API title: ${schema.info?.title || 'unknown'}`, context);
            logger.info(`[API_SCHEMA] API version: ${schema.info?.version || 'unknown'}`, context);
            logger.info(`[API_SCHEMA] Total number of paths in schema: ${Object.keys(schema.paths || {}).length}`, context);
            
            // Filter to only LinkedIn-related public endpoints
            const allPaths = Object.keys(schema.paths || {});
            const linkedinPaths = allPaths.filter(path => {
                // Include only paths under /api/v1/ for LinkedIn operations
                // Exclude auth, user, websocket, debug, health, and other internal endpoints
                return path.startsWith('/api/v1/') && 
                       !path.includes('/auth') && 
                       !path.includes('/user') && 
                       !path.includes('/ws') && 
                       !path.includes('/debug');
            });
            
            logger.info(`[API_SCHEMA] Filtered to ${linkedinPaths.length} LinkedIn public endpoints`, context);
            
            // Build endpoints array from schema
            const schemaEndpoints = this.buildEndpointsFromSchema(schema, linkedinPaths);
            logger.info(`[API_SCHEMA] Built ${schemaEndpoints.length} endpoint definitions from schema`, context);
            
            // Load endpoints.json to get special properties and custom endpoints
            const { overrides: endpointsJsonOverrides, allEndpoints: jsonEndpoints } = await this.loadEndpointsJsonOverrides();
            
            // Merge special properties from endpoints.json into schema-generated endpoints
            schemaEndpoints.forEach(endpoint => {
                const override = endpointsJsonOverrides.get(endpoint.endpoint + ':' + endpoint.method);
                if (override) {
                    if (override.rawBody !== undefined) {
                        endpoint.rawBody = override.rawBody;
                    }
                    if (override.rawBodyExample !== undefined) {
                        endpoint.rawBodyExample = override.rawBodyExample;
                    }
                    if (override.description !== undefined) {
                        endpoint.description = override.description;
                    }
                    // Use params from endpoints.json if provided (for path params, custom params, etc.)
                    if (override.params && override.params.length > 0) {
                        endpoint.params = override.params;
                    }
                    logger.info(`[API_SCHEMA] Applied overrides for ${endpoint.endpoint}: rawBody=${endpoint.rawBody}, params=${endpoint.params?.length}`, context);
                }
            });
            
            // Add endpoints from endpoints.json that don't exist in schema (custom endpoints)
            const schemaEndpointKeys = new Set(schemaEndpoints.map(ep => ep.endpoint + ':' + ep.method));
            jsonEndpoints.forEach(jsonEp => {
                const key = jsonEp.endpoint + ':' + jsonEp.method;
                if (!schemaEndpointKeys.has(key)) {
                    // This endpoint is only in endpoints.json, add it directly
                    schemaEndpoints.push(jsonEp);
                    logger.info(`[API_SCHEMA] Added custom endpoint from endpoints.json: ${jsonEp.name}`, context);
                }
            });
            
            // Replace the manually loaded endpoints with merged ones
            this.endpoints = schemaEndpoints;
            
            // Log each endpoint with parameters
            schemaEndpoints.forEach(endpoint => {
                logger.info(`[API_SCHEMA]   ${endpoint.method} ${endpoint.endpoint} - ${endpoint.name}`, context);
                logger.info(`[API_SCHEMA]     Parameters (${endpoint.params.length}):`, context, endpoint.params);
            });
            
            logger.info(`[API_SCHEMA] Full OpenAPI schema object:`, context, schema);
            
        } catch (error) {
            handleError(error, context);
            logger.error(`[API_SCHEMA] Failed to fetch API schema: ${error.message}`, context);
            // Don't throw - we don't want to break initialization if schema fetch fails
        }
    }
    
    /**
     * Loads endpoints.json and returns both overrides map and full endpoint list
     * @returns {Promise<{overrides: Map<string, Object>, allEndpoints: Array<Object>}>}
     */
    async loadEndpointsJsonOverrides() {
        const overrides = new Map();
        const allEndpoints = [];
        
        try {
            const apiEndpointsUrl = chrome.runtime.getURL('/shared/api/endpoints.json');
            const response = await fetch(apiEndpointsUrl);
            
            if (!response.ok) {
                logger.warn(`[API_SCHEMA] Could not load endpoints.json for overrides: ${response.status}`, 'loadEndpointsJsonOverrides');
                return { overrides, allEndpoints };
            }
            
            const endpointsJson = await response.json();
            
            // Build a map keyed by endpoint pattern + method AND collect all endpoints
            endpointsJson.forEach(ep => {
                const key = ep.endpoint + ':' + ep.method;
                
                // Store override properties for merging with schema endpoints
                overrides.set(key, {
                    rawBody: ep.rawBody,
                    rawBodyExample: ep.rawBodyExample,
                    params: ep.params,
                    description: ep.description,
                    geminiAuth: ep.geminiAuth,
                    serverOnly: ep.serverOnly
                });
                
                // Also store the full endpoint for adding custom endpoints not in schema
                allEndpoints.push(ep);
                
                logger.info(`[API_SCHEMA] Registered endpoint from JSON: ${key}`, 'loadEndpointsJsonOverrides');
            });
            
            logger.info(`[API_SCHEMA] Loaded ${overrides.size} endpoints from endpoints.json`, 'loadEndpointsJsonOverrides');
        } catch (error) {
            logger.warn(`[API_SCHEMA] Failed to load endpoints.json overrides: ${error.message}`, 'loadEndpointsJsonOverrides');
        }
        return { overrides, allEndpoints };
    }
    
    /**
     * Builds endpoint definitions from OpenAPI schema
     * @param {Object} schema - The OpenAPI schema
     * @param {Array<string>} paths - Filtered paths to include
     * @returns {Array<Object>} Array of endpoint definitions
     */
    buildEndpointsFromSchema(schema, paths) {
        const endpoints = [];
        
        // Store schema reference for resolving $ref
        this.openapiSchema = schema;
        
        paths.forEach(path => {
            const pathItem = schema.paths[path];
            
            // Process each HTTP method for this path
            Object.keys(pathItem).forEach(method => {
                const methodUpper = method.toUpperCase();
                if (['GET', 'POST', 'PUT', 'DELETE', 'PATCH'].includes(methodUpper)) {
                    const operation = pathItem[method];
                    
                    // Skip deprecated endpoints
                    if (operation.deprecated === true) {
                        logger.info(`[API_SCHEMA] Skipping deprecated endpoint: ${methodUpper} ${path}`, 'buildEndpointsFromSchema');
                        return;
                    }
                    
                    // Extract parameters from schema
                    const params = this.extractParametersFromOperation(operation);
                    
                    // Build endpoint object
                    const endpoint = {
                        name: operation.summary || `${methodUpper} ${path}`,
                        endpoint: path,
                        method: methodUpper,
                        description: operation.description || operation.summary || '',
                        params: params,
                        expectedResponse: this.getExpectedResponse(operation),
                        serverOnly: this.isServerOnly(operation),
                        geminiAuth: this.isGeminiAuth(operation)
                    };
                    
                    endpoints.push(endpoint);
                }
            });
        });
        
        // Sort by path for better organization
        endpoints.sort((a, b) => a.endpoint.localeCompare(b.endpoint));
        
        return endpoints;
    }
    
    /**
     * Resolves a $ref reference in the OpenAPI schema
     * @param {string} ref - The $ref string (e.g., "#/components/schemas/ScrapeProfileRequest")
     * @returns {Object|null} The resolved schema object
     */
    resolveSchemaRef(ref) {
        if (!ref || !ref.startsWith('#/')) {
            return null;
        }
        
        const path = ref.substring(2).split('/'); // Remove '#/' and split
        let current = this.openapiSchema;
        
        for (const segment of path) {
            if (current && typeof current === 'object' && segment in current) {
                current = current[segment];
            } else {
                logger.warn(`[SCHEMA_REF] Could not resolve reference: ${ref}`, 'resolveSchemaRef');
                return null;
            }
        }
        
        return current;
    }
    
    /**
     * Extracts parameters from OpenAPI operation
     * @param {Object} operation - The OpenAPI operation object
     * @returns {Array<Object>} Array of parameter definitions
     */
    extractParametersFromOperation(operation) {
        const params = [];
        
        logger.info(`[PARAM_EXTRACT] Extracting parameters from operation`, 'extractParametersFromOperation');
        logger.info(`[PARAM_EXTRACT] Operation has parameters:`, 'extractParametersFromOperation', operation.parameters);
        logger.info(`[PARAM_EXTRACT] Operation has requestBody:`, 'extractParametersFromOperation', operation.requestBody);
        
        // Extract from path parameters
        if (operation.parameters) {
            logger.info(`[PARAM_EXTRACT] Found ${operation.parameters.length} path/query parameters`, 'extractParametersFromOperation');
            operation.parameters.forEach(param => {
                params.push({
                    name: param.name,
                    type: this.mapSchemaTypeToInputType(param.schema?.type),
                    required: param.required || false,
                    description: param.description || '',
                    default: param.schema?.default,
                    label: this.formatLabel(param.name),
                    placeholder: this.createPlaceholder(param.schema, param.description)
                });
            });
        }
        
        // Extract from request body schema
        if (operation.requestBody?.content?.['application/json']?.schema) {
            let bodySchema = operation.requestBody.content['application/json'].schema;
            logger.info(`[PARAM_EXTRACT] Found request body schema:`, 'extractParametersFromOperation', bodySchema);
            logger.info(`[PARAM_EXTRACT] bodySchema has properties?`, 'extractParametersFromOperation', !!bodySchema.properties);
            logger.info(`[PARAM_EXTRACT] bodySchema has $ref?`, 'extractParametersFromOperation', !!bodySchema.$ref);
            
            // Resolve $ref if present
            if (bodySchema.$ref) {
                logger.info(`[PARAM_EXTRACT] Resolving $ref: ${bodySchema.$ref}`, 'extractParametersFromOperation');
                const resolvedSchema = this.resolveSchemaRef(bodySchema.$ref);
                if (resolvedSchema) {
                    bodySchema = resolvedSchema;
                    logger.info(`[PARAM_EXTRACT] Resolved schema:`, 'extractParametersFromOperation', bodySchema);
                } else {
                    logger.error(`[PARAM_EXTRACT] Failed to resolve $ref: ${bodySchema.$ref}`, 'extractParametersFromOperation');
                }
            }
            
            logger.info(`[PARAM_EXTRACT] bodySchema keys after resolution:`, 'extractParametersFromOperation', Object.keys(bodySchema));
            
            if (bodySchema.properties) {
                logger.info(`[PARAM_EXTRACT] Processing ${Object.keys(bodySchema.properties).length} properties`, 'extractParametersFromOperation');
                Object.keys(bodySchema.properties).forEach(propName => {
                    const prop = bodySchema.properties[propName];
                    
                    // Skip api_key parameter - we handle this separately
                    if (propName === 'api_key') {
                        return;
                    }
                    
                    // Skip server_call parameter - we handle this with a toggle
                    if (propName === 'server_call') {
                        return;
                    }
                    
                    // Determine input type based on property characteristics
                    let inputType = this.mapSchemaTypeToInputType(prop.type);
                    
                    // Check for specific constraints
                    const hasMin = prop.minimum !== undefined || prop.exclusiveMinimum !== undefined;
                    const hasMax = prop.maximum !== undefined || prop.exclusiveMaximum !== undefined;
                    const min = prop.minimum || prop.exclusiveMinimum;
                    const max = prop.maximum || prop.exclusiveMaximum;
                    
                    params.push({
                        name: propName,
                        type: inputType,
                        required: bodySchema.required?.includes(propName) || false,
                        description: prop.description || '',
                        default: prop.default,
                        label: this.formatLabel(propName),
                        placeholder: this.createPlaceholder(prop, prop.description),
                        min: hasMin ? min : undefined,
                        max: hasMax ? max : undefined
                    });
                });
            }
        }
        
        return params;
    }
    
    /**
     * Creates a helpful placeholder text for a parameter
     * @param {Object} schema - The parameter schema
     * @param {string} description - The parameter description
     * @returns {string} Placeholder text
     */
    createPlaceholder(schema, description) {
        if (!schema) return '';
        
        // If there's an example in the schema, use it
        if (schema.example) {
            return `e.g., ${schema.example}`;
        }
        
        // Extract example from description if present
        if (description) {
            const exampleMatch = description.match(/e\.g\.,?\s*([^)]+)/i);
            if (exampleMatch) {
                return `e.g., ${exampleMatch[1].trim()}`;
            }
            
            // Look for parenthetical examples
            const parenMatch = description.match(/\(([^)]+)\)/);
            if (parenMatch && parenMatch[1].includes('ACoA')) {
                return `e.g., ${parenMatch[1].trim()}`;
            }
        }
        
        // Type-based defaults
        if (schema.type === 'string' && description?.toLowerCase().includes('url')) {
            return 'https://www.linkedin.com/...';
        }
        if (schema.type === 'string' && description?.toLowerCase().includes('profile')) {
            return 'ACoAAAKGenkB... or https://linkedin.com/in/username';
        }
        if (schema.type === 'string' && description?.toLowerCase().includes('post')) {
            return 'urn:li:activity:... or post URL';
        }
        if (schema.type === 'integer' || schema.type === 'number') {
            if (schema.default !== undefined) {
                return `Default: ${schema.default}`;
            }
            if (schema.minimum !== undefined && schema.maximum !== undefined) {
                return `${schema.minimum}-${schema.maximum}`;
            }
        }
        
        return '';
    }
    
    /**
     * Maps OpenAPI schema type to HTML input type
     * @param {string} schemaType - OpenAPI schema type
     * @returns {string} HTML input type
     */
    mapSchemaTypeToInputType(schemaType) {
        const typeMap = {
            'string': 'text',
            'integer': 'number',
            'number': 'number',
            'boolean': 'checkbox',
            'array': 'text',
            'object': 'text'
        };
        return typeMap[schemaType] || 'text';
    }
    
    /**
     * Formats parameter name into a readable label
     * @param {string} name - Parameter name
     * @returns {string} Formatted label
     */
    formatLabel(name) {
        return name
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }
    
    /**
     * Gets expected response description from operation
     * @param {Object} operation - The OpenAPI operation object
     * @returns {string} Expected response description
     */
    getExpectedResponse(operation) {
        if (operation.responses?.['200']?.content?.['application/json']?.schema) {
            const schema = operation.responses['200'].content['application/json'].schema;
            return JSON.stringify(schema, null, 2).substring(0, 200) + '...';
        }
        return 'See API documentation';
    }
    
    /**
     * Determines if endpoint is server-only from operation
     * @param {Object} operation - The OpenAPI operation object
     * @returns {boolean} True if server-only
     */
    isServerOnly(operation) {
        // Check if operation description or summary mentions server-only
        const text = (operation.description || '') + (operation.summary || '');
        const lowerText = text.toLowerCase();
        
        // [Gemini] endpoints are always server-only
        if (text.includes('[Gemini]') || text.includes('[gemini]')) {
            return true;
        }
        
        // If it mentions "supports two execution modes" or "proxy", it's NOT server-only
        if (lowerText.includes('supports two execution modes') || 
            lowerText.includes('transparent http proxy') ||
            lowerText.includes('proxy via browser extension')) {
            return false;
        }
        
        // Only return true if it explicitly says "server-only" or "server only"
        return lowerText.includes('server-only') || 
               lowerText.includes('server only') ||
               (lowerText.includes('server-side') && lowerText.includes('only')) ||
               lowerText.includes('runs entirely on the server');
    }
    
    /**
     * Determines if endpoint uses Gemini authentication from operation
     * @param {Object} operation - The OpenAPI operation object
     * @returns {boolean} True if Gemini auth endpoint
     */
    isGeminiAuth(operation) {
        const text = (operation.description || '') + (operation.summary || '');
        return text.includes('[Gemini]') || text.includes('[gemini]');
    }
    
    /**
     * Handles form submission
     * @param {Event} e - The form submit event
     */
    async handleSubmit(e) {
        e.preventDefault();
        
        // Clear any previous responses
        if (this.responseDisplay) {
            this.responseDisplay.clearResponse();
            this.responseDisplay.clearError();
        }
        
        // Validate form before submission
        const validationError = this.validateForm();
        if (validationError) {
            if (this.responseDisplay) {
                this.responseDisplay.showError(validationError);
            }
            logger.warn(`[FORM_VALIDATION] ${validationError}`, 'ApiTester.handleSubmit');
            return; // Don't submit if validation fails
        }
        
        try {
            // Show loading state
            if (this.responseDisplay) {
                this.responseDisplay.showLoading(true);
            }
            
            // Handle the request based on endpoint type
            if (this.currentEndpoint && this.currentEndpoint.endpoint === 'custom') {
                // Handle custom API request
                await this.handleCustomApiRequest();
        } else {
                // Handle standard API request
                await this.handleStandardApiRequest();
            }
                } catch (error) {
            handleError(error, 'ApiTester.handleSubmit');
            
            if (this.responseDisplay) {
                this.responseDisplay.showError(`API Request failed: ${error.message}`);
            }
        } finally {
            // Hide loading state
            if (this.responseDisplay) {
                this.responseDisplay.showLoading(false);
            }
        }
    }
    
    /**
     * Validates the form before submission
     * @returns {string|null} Error message if validation fails, null if valid
     */
    validateForm() {
        // Check if an endpoint is selected
        if (!this.currentEndpoint) {
            return 'Please select an endpoint';
        }
        
        // Validate API key is provided
        const apiKeyInput = document.getElementById('api-key-input');
        if (apiKeyInput instanceof HTMLInputElement) {
            const apiKey = apiKeyInput.value.trim();
            if (!apiKey) {
                return 'API Key is required. Please enter your API key.';
            }
        }
        
        // For rawBody endpoints, validate the JSON body
        if (this.currentEndpoint.rawBody) {
            if (this.parameterForm) {
                const paramValues = this.parameterForm.getParameterValues();
                if (!paramValues._rawBody) {
                    return 'Request body is required. Please enter valid JSON.';
                }
                if (typeof paramValues._rawBody === 'string') {
                    return 'Invalid JSON in request body. Please check the syntax.';
                }
            }
            return null; // Validation passed for rawBody endpoint
        }
        
        // Validate required parameters (non-rawBody endpoints)
        if (this.parameterForm) {
            const isValid = this.parameterForm.validateParameters();
            if (!isValid) {
                return 'Please fill in all required fields (marked with *)';
            }
            
            // Additional validation: check for empty required fields
            const paramValues = this.parameterForm.getParameterValues();
            const requiredParams = (this.currentEndpoint.params || []).filter(p => p.required);
            
            for (const param of requiredParams) {
                const value = paramValues[param.name];
                if (value === undefined || value === null || value.toString().trim() === '') {
                    return `Required field "${param.label || param.name}" cannot be empty`;
                }
            }
        }
        
        return null; // Validation passed
    }
    
    /**
     * Handles standard API requests using configured endpoints
     */
    async handleStandardApiRequest() {
        // Get the selected endpoint
        if (!this.currentEndpoint || this.currentEndpoint.endpoint === 'custom') {
            throw createError('InputError', 'No standard endpoint selected', 'ApiTester.handleStandardApiRequest');
        }
        
        // Get parameter values from the form
        const paramValues = this.parameterForm ? this.parameterForm.getParameterValues() : {};
        
        // Get API key from input if available
        const apiKeyInput = document.getElementById('api-key-input');
        const apiKey = apiKeyInput instanceof HTMLInputElement ? apiKeyInput.value : null;
        
        // Get server_call toggle state (force true for serverOnly endpoints)
        const serverCallToggle = document.getElementById('server-call-toggle');
        let serverCall = serverCallToggle instanceof HTMLInputElement ? serverCallToggle.checked : false;
        
        // Force server_call=true for serverOnly endpoints
        if (this.currentEndpoint.serverOnly) {
            serverCall = true;
        }
        
        // Prepare API request data
        let endpoint = this.currentEndpoint.endpoint;
        const requestData = {
            method: this.currentEndpoint.method
        };
        
        const isGeminiEndpoint = !!this.currentEndpoint.geminiAuth;
        const isRawBodyEndpoint = !!this.currentEndpoint.rawBody;
        
        // Handle rawBody endpoints (pass-through like native Gemini API)
        if (isRawBodyEndpoint && paramValues._rawBody) {
            // First, replace any path parameters in the endpoint URL
            const pathParamMatches = endpoint.match(/\{([^}]+)\}/g);
            if (pathParamMatches) {
                pathParamMatches.forEach(match => {
                    const paramName = match.slice(1, -1); // Remove { and }
                    if (paramValues[paramName] !== undefined) {
                        // Replace in endpoint URL
                        endpoint = endpoint.replace(match, encodeURIComponent(paramValues[paramName]));
                    }
                });
            }
            
            requestData.endpoint = endpoint;
            // Use the raw body directly - don't add api_key to body for these endpoints
            requestData.body = paramValues._rawBody;
            
            // Add API key to headers only
            if (isGeminiEndpoint) {
                requestData.headers = {
                    'x-goog-api-key': apiKey || ''
                };
            } else {
                requestData.headers = {
                    'X-API-Key': apiKey || ''
                };
            }
            
            // Send API request using backend controller
            const response = await this.makeApiRequest(requestData);
            
            // Display the response
            if (this.responseDisplay) {
                this.responseDisplay.displayResponse(response);
            }
            
            return response;
        }
        
        // Standard parameter handling (non-rawBody endpoints)
        // Separate path parameters from body/query parameters
        const pathParams = {};
        const bodyOrQueryParams = {};
        
        // Check if endpoint has path parameters (e.g., {vanity_name})
        const pathParamMatches = endpoint.match(/\{([^}]+)\}/g);
        if (pathParamMatches) {
            // Extract path parameter names
            pathParamMatches.forEach(match => {
                const paramName = match.slice(1, -1); // Remove { and }
                if (paramValues[paramName] !== undefined) {
                    pathParams[paramName] = paramValues[paramName];
                    // Replace in endpoint URL
                    endpoint = endpoint.replace(match, encodeURIComponent(paramValues[paramName]));
                }
            });
            
            // Remaining params go to body/query
            Object.keys(paramValues).forEach(key => {
                if (!pathParams[key]) {
                    bodyOrQueryParams[key] = paramValues[key];
                }
            });
        } else {
            // No path params, all go to body/query
            Object.assign(bodyOrQueryParams, paramValues);
        }
        
        requestData.endpoint = endpoint;
        
        // Determine whether to use params or body based on HTTP method
        const method = this.currentEndpoint.method.toUpperCase();
        
        if (method === 'GET' || method === 'DELETE') {
            // For GET/DELETE, use query parameters
            requestData.params = bodyOrQueryParams;
            // Add API key to params if provided
            if (apiKey) {
                requestData.params.api_key = apiKey;
            }
            // Add server_call to params if true (not for Gemini endpoints)
            if (serverCall && !isGeminiEndpoint) {
                requestData.params.server_call = serverCall;
            }
        } else if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
            // For POST/PUT/PATCH, use request body
            requestData.body = bodyOrQueryParams;
            // Add API key to body if provided
            if (apiKey) {
                requestData.body.api_key = apiKey;
            }
            // Add server_call to body if true (not for Gemini endpoints - they're always server-side)
            if (serverCall && !isGeminiEndpoint) {
                requestData.body.server_call = serverCall;
            }
        }
        
        // Add API key to headers - use x-goog-api-key for Gemini endpoints
        if (isGeminiEndpoint) {
            requestData.headers = {
                'x-goog-api-key': apiKey || ''
            };
        } else {
            requestData.headers = {
                'X-API-Key': apiKey || ''
            };
        }
        
        // Send API request using backend controller
        const response = await this.makeApiRequest(requestData);
        
        // Display the response
        if (this.responseDisplay) {
            this.responseDisplay.displayResponse(response);
        }
        
        return response;
    }
    
    /**
     * Handles custom API requests
     */
    async handleCustomApiRequest() {
        if (!this.customRequestForm) {
            throw createError('InitError', 'Custom request form not initialized', 'ApiTester.handleCustomApiRequest');
        }
        
        // Get custom request data and validate
        const customRequestData = this.customRequestForm.getRequestData();
        if (!customRequestData) {
            throw createError('ValidationError', 'Invalid custom request data', 'ApiTester.handleCustomApiRequest');
        }
        
        // Get API key from input if available
        const apiKeyInput = document.getElementById('api-key-input');
        const apiKey = apiKeyInput instanceof HTMLInputElement ? apiKeyInput.value : null;
        
        // Get server_call toggle state
        const serverCallToggle = document.getElementById('server-call-toggle');
        const serverCall = serverCallToggle instanceof HTMLInputElement ? serverCallToggle.checked : false;
        
        // Add API key and server_call to the request based on method type
        const method = (customRequestData.method || 'GET').toUpperCase();
        if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
            // For POST/PUT/PATCH, add to body
            if (!customRequestData.body) {
                customRequestData.body = {};
            } else if (typeof customRequestData.body === 'string') {
                // Parse JSON string body if needed
                try {
                    customRequestData.body = JSON.parse(customRequestData.body);
                } catch (e) {
                    customRequestData.body = {};
                }
            }
            // Add API key to body if provided
            if (apiKey) {
                customRequestData.body.api_key = apiKey;
            }
            // Add server_call to body if true
            if (serverCall) {
                customRequestData.body.server_call = serverCall;
            }
        } else {
            // For GET/DELETE, add to params
            if (!customRequestData.params) {
                customRequestData.params = {};
            }
            // Add API key to params if provided
            if (apiKey) {
                customRequestData.params.api_key = apiKey;
            }
            // Add server_call to params if true
            if (serverCall) {
                customRequestData.params.server_call = serverCall;
            }
        }
        
        // Send API request using backend controller
        const response = await this.makeApiRequest(customRequestData);
                
        // Display the response
        if (this.responseDisplay) {
            this.responseDisplay.displayResponse(response);
        }
        
        return response;
    }
    
    /**
     * Makes an API request using the background service
     * @param {Object} requestData - The request data
     * @returns {Promise<any>} The API response
     */
    async makeApiRequest(requestData) {
        try {
            // Use the API_REQUEST message type to make the request through the background service
            const message = {
                type: MESSAGE_TYPES.API_REQUEST,
                data: requestData
            };
            
            logger.info(`Sending API request: ${requestData.method} ${requestData.endpoint}`, 'ApiTester');
            
            const response = await sendMessageToBackground(message);
            
            if (!response) {
                throw createError('ApiError', 'No response received from API', 'ApiTester.makeApiRequest');
            }
            
            if (!response.success) {
                // Handle error object from serialized error
                const errorMessage = typeof response.error === 'object' && response.error.message
                    ? response.error.message
                    : typeof response.error === 'string'
                    ? response.error
                    : 'API request failed';
                throw createError('ApiError', errorMessage, 'ApiTester.makeApiRequest');
            }
            
            return response.data;
        } catch (error) {
            handleError(error, 'ApiTester.makeApiRequest');
            throw error;
        }
    }
    
    /**
     * Shows an error message
     * @param {string} message - The error message to display
     */
    showError(message) {
        if (this.responseDisplay) {
            this.responseDisplay.showError(message);
                        } else {
            logger.error(message, 'ApiTester');
            alert(message);
        }
    }
    
    /**
     * Updates the request preview display
     */
    updateRequestPreview() {
        if (!this.currentEndpoint || this.currentEndpoint.endpoint === 'custom') {
            return;
        }
        
        // Get parameter values
        const params = this.parameterForm ? this.parameterForm.getParameterValues() : {};
        
        // Get server_call toggle state
        const serverCallToggle = document.getElementById('server-call-toggle');
        const serverCall = serverCallToggle instanceof HTMLInputElement ? serverCallToggle.checked : false;
        
        // Add server_call to preview if enabled (not for Gemini endpoints)
        if (serverCall && !this.currentEndpoint.geminiAuth) {
            params.server_call = serverCall;
        }
        
        // Update the display using the global function
        if (window.updateRequestDisplay && typeof window.updateRequestDisplay === 'function') {
            window.updateRequestDisplay(
                this.currentEndpoint.endpoint,
                this.currentEndpoint.method,
                params,
                !!this.currentEndpoint.geminiAuth  // Pass Gemini flag for correct header display
            );
        }
    }
    
    /**
     * Sets up listeners for parameter input changes
     */
    setupParameterChangeListeners() {
        const paramsContainer = document.getElementById('params-container');
        if (!paramsContainer) return;
        
        // Add input event listeners to all parameter inputs
        const inputs = paramsContainer.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            // Remove existing listener if any
            input.removeEventListener('input', this.handleParameterChange);
            // Add new listener
            input.addEventListener('input', () => this.updateRequestPreview());
        });
        
        // Also add listener to server_call toggle
        const serverCallToggle = document.getElementById('server-call-toggle');
        if (serverCallToggle) {
            serverCallToggle.removeEventListener('change', this.handleServerCallToggle);
            serverCallToggle.addEventListener('change', () => this.updateRequestPreview());
        }
        
        // Add listener to API key input to update headers in preview
        const apiKeyInput = document.getElementById('api-key-input');
        if (apiKeyInput) {
            apiKeyInput.addEventListener('input', () => this.updateRequestPreview());
        }
    }
} 