//@ts-check
/// <reference types="chrome"/>

/**
 * API Controller for handling API-related operations
 * 
 * This controller interfaces between the messaging layer and the API functionality,
 * providing a clean interface for making API requests and managing API operations.
 * 
 * @fileoverview API controller for background service
 */

import { MESSAGE_TYPES } from '../../shared/constants/message-types.js';
import { logger } from '../../shared/utils/logger.js';
import * as storageService from '../services/storage.service.js';
// No need to import * as apiUtils if makeApiRequest is internal to this controller
import { handleError, serializeError, createError } from '../../shared/utils/error-handler.js';
import appConfig from '../../shared/config/app.config.js';
import apiConfig from '../../shared/config/api.config.js';
// Remove auth imports if not directly used by exported functions
// import { getApiKey, generateApiKey, deleteApiKey, performLogout, checkAuthAndGetProfile } from '../services/auth.service.js';

/**
 * Initializes the API controller
 * Performs any necessary setup for API handling
 */
export function init() {
  logger.info('Initializing API Controller', 'api.controller');
}

/**
 * Handles messages related to API operations
 * Routes messages to appropriate handler functions based on message type
 * 
 * @param {Object} message - The received message
 * @param {string} message.type - The type of message (from MESSAGE_TYPES)
 * @param {Object} [message.data] - Any data associated with the message
 * @param {Function} sendResponse - Function to send response back to the caller
 * @returns {boolean} - True if message was handled, false otherwise
 */
export function handleMessage(message, sendResponse) {
  if (!message || !message.type) {
    // Log actual error, not just string
    handleError(new Error('Invalid message format received'), 'api.controller.handleMessage'); 
    return false;
  }
  
  switch (message.type) {
    case MESSAGE_TYPES.API_REQUEST:
      // Pass sendResponse correctly
      handleApiRequest(message.data, sendResponse);
      return true;
      
    default:
      return false; // Message not handled by this controller
  }
}

/**
 * Handles API request message
 * Makes an API call to the specified endpoint
 * 
 * @param {Object} data - The request data
 * @param {string} data.endpoint - The API endpoint to call
 * @param {string} data.method - The HTTP method to use
 * @param {Object} [data.params] - The parameters to include in the request
 * @param {Object} [data.body] - The request body (for POST, PUT methods)
 * @param {boolean} [data.requiresAuth=true] - Whether the request requires authentication
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleApiRequest(data, sendResponse) {
  const context = 'api.controller.handleApiRequest';
  try {
    logger.info(`API request received: ${data.method} ${data.endpoint}`, context);
    
    if (!data || !data.endpoint || !data.method) {
      throw createError('BaseError', 'Invalid API request: missing required parameters', context);
    }
    
    // Check if request requires authentication (default: true)
    const requiresAuth = data.requiresAuth !== false;
    let accessToken = undefined; // Use undefined instead of null for optional string
    
    if (requiresAuth) {
      const authData = await storageService.getAuthData();
      accessToken = authData?.accessToken; // Optional chaining handles null/undefined authData
      
      if (!accessToken) {
        throw createError('AuthError', 'Authentication required but user is not logged in', context);
      }
    }
    
    // Make the API request (pass undefined if no token)
    const response = await makeApiRequest(data.endpoint, data.method, data.params, data.body, accessToken);
    
    // Send the success response back
    sendResponse({ 
      success: true, 
      data: response 
    });
    
  } catch (error) {
    handleError(error, context); // Log the handled error
    // Ensure error is serialized correctly for sendResponse
    sendResponse({ 
      success: false, 
      error: serializeError(error) // Use serializeError here
    });
  }
}

/**
 * Makes an API request to the specified endpoint
 * 
 * @param {string} endpoint - The API endpoint to call
 * @param {string} method - The HTTP method to use
 * @param {Object} [params] - The query parameters
 * @param {Object} [body] - The request body (for POST, PUT methods)
 * @param {string} [accessToken] - The access token for authentication (optional)
 * @returns {Promise<any>} The API response data
 */
async function makeApiRequest(endpoint, method, params, body, accessToken) {
  const context = 'api.controller.makeApiRequest';
  logger.info(`[API] Making API request: ${method} ${endpoint}`, context);
  
  // ALWAYS get current server URL dynamically
  const serverUrls = await appConfig.getServerUrls();
  logger.info(`[API] Backend server (DYNAMIC): ${serverUrls.apiUrl}`, context);
  
  try {
    // Build URL with query parameters if provided
    let url = `${serverUrls.apiUrl}${endpoint}`;
    
    if (params && Object.keys(params).length > 0 && (method === 'GET' || method === 'DELETE')) {
      const queryParams = new URLSearchParams();
      
      for (const [key, value] of Object.entries(params)) {
        // Ensure value is stringifiable
        if (value !== undefined && value !== null) {
          queryParams.append(key, String(value));
        }
      }
      
      const queryString = queryParams.toString();
      if (queryString) {
        url += `?${queryString}`;
      }
    }
    
    // Build request options
    const options = {
      method: method,
      headers: { ...apiConfig.HEADERS }, // Use default headers from config
    };
    
    // Add authentication header if token provided
    if (accessToken) {
      // @ts-ignore Headers might be missing Authorization, TS complains
      options.headers['Authorization'] = `Bearer ${accessToken}`;
    }
    
    // Add body for request types that support it
    if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
      options.body = JSON.stringify(body);
    } else {
      // Ensure Content-Type is not set for methods without body (like GET)
      // @ts-ignore Headers might be missing Content-Type, TS complains
      delete options.headers['Content-Type']; 
    }
    
    // Make the request using fetch
    logger.info(`[API] Fetching: ${url}`, context);
    const response = await fetch(url, options);
    
    // Handle non-2xx responses
    if (!response.ok) {
      const errorText = await response.text();
      // Use createError for specific error type
      throw createError('ApiError', `API Error: ${response.status} ${response.statusText} - ${errorText}`, response.status, context);
    }
    
    // Parse JSON response if content type indicates it
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return await response.json();
    } else {
      // Return text for non-JSON responses (or handle empty response)
      return await response.text();
    }
    
  } catch (error) {
    // Log error here if not already logged by createError/handleError
    if (!(error instanceof Error && error.name === 'ApiError') && !(error instanceof Error && error.name === 'AuthError')) {
       handleError(error, context); // Log if it's not one of our handled custom errors from this flow
    }
    // Re-throw the original or custom error
    throw error; 
  }
}

// This file exports functions directly, no class instantiation needed.