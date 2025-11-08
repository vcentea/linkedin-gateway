// @ts-check

/**
 * Interface layer for UI components to interact with the WebSocket service.
 * This interface provides a clean API for UI components to get connection status,
 * subscribe to status updates, send requests, and manage the WebSocket connection.
 * 
 * @fileoverview WebSocket interface for UI components
 */

import { log } from '../../shared/utils/general.utils.js';
import { MESSAGE_TYPES } from '../../shared/constants/message-types.js';
import { createWebSocketMessage, generateMessageId } from '../../shared/utils/websocket.utils.js';

// Import types
/**
 * @typedef {import('../../shared/types/websocket.types.js').WebSocketStatus} WebSocketStatus
 * @typedef {import('../../shared/types/websocket.types.js').WebSocketStatusListener} WebSocketStatusListener
 * @typedef {import('../../shared/types/websocket.types.js').WebSocketResponseStatus} WebSocketResponseStatus
 */

/**
 * @typedef {Object} Chrome
 * @property {Object} runtime
 * @property {Object} runtime.onMessage
 * @property {function(function(Object, Object, function(*): boolean): boolean): void} runtime.onMessage.addListener
 * @property {function(function(Object, Object, function(*): boolean): boolean): void} runtime.onMessage.removeListener
 * @property {function(Object, function(*): void): void} runtime.sendMessage
 */

/**
 * Chrome API global
 * @type {Chrome}
 */
// @ts-ignore
const chrome = window.chrome;

// Private array to store status listeners
/** @type {WebSocketStatusListener[]} */
const statusListeners = [];

// Reference to the last known status (cached)
/** @type {WebSocketStatus|null} */
let cachedStatus = null;

/**
 * Get the current WebSocket connection status
 * @returns {Promise<WebSocketStatus>} Current connection status
 */
export async function getConnectionStatus() {
  // If we have a cached status, return it immediately
  if (cachedStatus) {
    return Promise.resolve(cachedStatus);
  }
  
  // Otherwise, request the status from the background WebSocket service
  /** @type {Promise<WebSocketStatus>} */
  const statusPromise = new Promise((resolve) => {
    chrome.runtime.sendMessage({
      type: MESSAGE_TYPES.GET_WEBSOCKET_STATUS
    }, (response) => {
      cachedStatus = response.status;
      resolve(response.status);
    });
  });
  
  return statusPromise;
}

/**
 * Subscribe to WebSocket status updates
 * @param {WebSocketStatusListener} callback - Function to call when status changes
 * @returns {boolean} Whether the subscription was successful
 */
export function subscribeToStatusUpdates(callback) {
  if (typeof callback !== 'function') {
    log('Invalid callback provided to subscribeToStatusUpdates');
    return false;
  }
  
  // Avoid duplicate subscriptions
  if (statusListeners.includes(callback)) {
    return true;
  }
  
  statusListeners.push(callback);
  
  // Register a listener for WebSocket status updates if this is the first subscription
  if (statusListeners.length === 1) {
    chrome.runtime.onMessage.addListener(handleStatusMessage);
  }
  
  // Get initial status and call the callback with it
  getConnectionStatus().then(status => {
    try {
      callback(status);
    } catch (error) {
      log(`Error in WebSocket status listener: ${error.message}`);
    }
  });
  
  return true;
}

/**
 * Unsubscribe from WebSocket status updates
 * @param {WebSocketStatusListener} callback - The callback to remove
 * @returns {boolean} Whether the unsubscription was successful
 */
export function unsubscribeFromStatusUpdates(callback) {
  const index = statusListeners.indexOf(callback);
  if (index === -1) {
    return false;
  }
  
  statusListeners.splice(index, 1);
  
  // Remove the message listener if there are no more subscribers
  if (statusListeners.length === 0) {
    chrome.runtime.onMessage.removeListener(handleStatusMessage);
  }
  
  return true;
}

/**
 * Handle incoming status messages from the background script
 * @param {Object} message - The message received
 * @param {Object} sender - The message sender
 * @param {function(*): void} [sendResponse] - Function to send response
 * @returns {boolean} Whether the message was handled
 * @private
 */
function handleStatusMessage(message, sender, sendResponse) {
  if (message.type === MESSAGE_TYPES.WEBSOCKET_STATUS_UPDATE) {
    cachedStatus = message.status;
    
    // Notify all listeners
    for (const listener of statusListeners) {
      try {
        listener(message.status);
      } catch (error) {
        log(`Error in WebSocket status listener: ${error.message}`);
      }
    }
    
    return true;
  }
  
  return false;
}

/**
 * Send a WebSocket request and get the response
 * @param {string} type - The request type
 * @param {Object} data - The request data
 * @param {number} [timeout=30000] - Timeout in milliseconds
 * @returns {Promise<Object>} The response data
 */
export function sendWebSocketRequest(type, data, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const requestId = generateMessageId();
    const request = {
      type: MESSAGE_TYPES.SEND_WEBSOCKET_REQUEST,
      requestType: type,
      requestId,
      data
    };
    
    // Set up timeout
    const timeoutId = setTimeout(() => {
      chrome.runtime.onMessage.removeListener(responseHandler);
      reject(new Error(`WebSocket request timed out after ${timeout}ms`));
    }, timeout);
    
    /**
     * Handle response from WebSocket request
     * @param {Object} message - The response message
     * @param {Object} sender - The message sender
     * @param {function(*): void} [sendResponse] - Function to send response
     * @returns {boolean} Whether the message was handled
     */
    function responseHandler(message, sender, sendResponse) {
      if (message.type === MESSAGE_TYPES.WEBSOCKET_RESPONSE && 
          message.requestId === requestId) {
        clearTimeout(timeoutId);
        chrome.runtime.onMessage.removeListener(responseHandler);
        
        if (message.status === 'ERROR') {
          reject(new Error(message.error || 'Unknown WebSocket error'));
        } else {
          resolve(message.data);
        }
        
        return true;
      }
      
      return false;
    }
    
    // Register response handler
    chrome.runtime.onMessage.addListener(responseHandler);
    
    // Send request
    chrome.runtime.sendMessage(request);
  });
}

/**
 * Request a reconnection of the WebSocket
 * @returns {Promise<boolean>} Whether the reconnection was initiated
 */
export async function reconnectWebSocket() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({
      type: MESSAGE_TYPES.RECONNECT_WEBSOCKET
    }, (response) => {
      resolve(response.success || false);
    });
  });
}

/**
 * Check if the WebSocket is connected
 * @returns {Promise<boolean>} Whether the WebSocket is connected
 */
export async function isWebSocketConnected() {
  const status = await getConnectionStatus();
  return status.connected;
}

/**
 * Get the WebSocket connection state name
 * @returns {Promise<string>} The connection state name
 */
export async function getConnectionStateName() {
  const status = await getConnectionStatus();
  return status.state;
} 