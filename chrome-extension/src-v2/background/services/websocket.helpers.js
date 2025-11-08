// @ts-check
import { logger } from '../../shared/utils/logger.js';
import { handleError } from '../../shared/utils/error-handler.js';

/**
 * Helper functions extracted from the WebSocketClient implementation
 * These functions provide utilities for WebSocket connection management,
 * message handling, and reconnection logic.
 */

/**
 * Tracks WebSocket event listeners for status updates and other events
 * @type {Object<string, Function[]>}
 */
let listeners = {};

/**
 * Adds an event listener for WebSocket events
 * @param {string} event - The event type to listen for (connected, disconnected, error, etc.)
 * @param {Function} callback - The callback function to invoke when the event occurs
 */
export function addWebSocketListener(event, callback) {
  if (!listeners[event]) {
    listeners[event] = [];
  }
  
  listeners[event].push(callback);
}

/**
 * Removes an event listener for WebSocket events
 * @param {string} event - The event type
 * @param {Function} callback - The callback function to remove
 * @returns {boolean} - Whether the listener was removed successfully
 */
export function removeWebSocketListener(event, callback) {
  if (!listeners[event]) {
    return false;
  }
  
  const index = listeners[event].indexOf(callback);
  if (index !== -1) {
    listeners[event].splice(index, 1);
    return true;
  }
  
  return false;
}

/**
 * Notifies all registered listeners of a WebSocket event
 * @param {string} event - The event type
 * @param {Object} data - The data associated with the event
 */
export function notifyWebSocketListeners(event, data) {
  if (!listeners[event]) {
    return;
  }
  
  for (const callback of listeners[event]) {
    try {
      callback(data);
    } catch (error) {
      logger.error(`Error in WebSocket ${event} listener`, error, 'websocket.helpers');
    }
  }
}

/**
 * Calculates the reconnection delay using exponential backoff
 * @param {number} attempt - The current reconnection attempt number
 * @param {number} baseInterval - The base interval in milliseconds
 * @param {number} maxAttempts - The maximum number of reconnection attempts
 * @param {number} multiplier - The exponential backoff multiplier (default: 1.5)
 * @returns {number|null} - The calculated delay in ms, or null if max attempts reached
 */
export function calculateReconnectionDelay(attempt, baseInterval, maxAttempts, multiplier = 1.5) {
  if (attempt > maxAttempts) {
    return null; // Max attempts reached
  }
  
  return baseInterval * Math.pow(multiplier, attempt - 1);
}

/**
 * Safely parses a WebSocket message
 * @param {string} data - The raw message data
 * @returns {Object|null} - The parsed message or null if parsing failed
 */
export function parseWebSocketMessage(data) {
  try {
    return JSON.parse(data);
  } catch (error) {
    logger.error('Failed to parse WebSocket message', error, 'websocket.helpers');
    return null;
  }
}

/**
 * Creates a properly formatted WebSocket message
 * @param {string} type - The message type
 * @param {Object} [payload={}] - The message payload
 * @returns {string} - JSON string representation of the message
 */
export function createWebSocketMessage(type, payload = {}) {
  const message = {
    type,
    ...payload
  };
  
  return JSON.stringify(message);
}

/**
 * Checks if a WebSocket connection has timed out based on last activity
 * @param {number} lastActivityTime - Timestamp of last received message
 * @param {number} timeoutMs - Timeout duration in milliseconds
 * @returns {boolean} - Whether the connection has timed out
 */
export function hasConnectionTimedOut(lastActivityTime, timeoutMs) {
  return Date.now() - lastActivityTime > timeoutMs;
}

/**
 * Constructs a WebSocket URL from a base URL
 * This implementation handles different URL formats and ensures proper protocol
 * @param {string} baseUrl - The base URL (can be HTTP or WebSocket protocol)
 * @param {string} [endpoint='/ws'] - The WebSocket endpoint
 * @returns {string} - The complete WebSocket URL
 */
export function constructWebSocketUrl(baseUrl, endpoint = '/ws') {
  // Convert http/https to ws/wss if needed
  const wsUrl = baseUrl.replace(/^http/, 'ws');
  
  // Ensure we don't duplicate slashes between base URL and endpoint
  if (wsUrl.endsWith('/') && endpoint.startsWith('/')) {
    return wsUrl + endpoint.substring(1);
  } else if (!wsUrl.endsWith('/') && !endpoint.startsWith('/')) {
    return wsUrl + '/' + endpoint;
  }
  
  return wsUrl + endpoint;
}

/**
 * Manages reconnection attempts with tracking
 * @param {Function} connectCallback - Function to call to attempt reconnection
 * @param {number} currentAttempt - The current reconnection attempt number
 * @param {number} maxAttempts - Maximum number of reconnection attempts
 * @param {number} baseInterval - Base interval between attempts in milliseconds
 * @param {number} [multiplier=1.5] - Backoff multiplier
 * @returns {Promise<{timeout: number|null, newAttempt: number}>} - The timeout ID and new attempt count
 */
export async function manageReconnectionAttempt(
  connectCallback, 
  currentAttempt, 
  maxAttempts, 
  baseInterval,
  multiplier = 1.5
) {
  // Clear any existing timeout
  let timeout = null;
  let newAttempt = currentAttempt;
  
  if (currentAttempt < maxAttempts) {
    newAttempt++;
    const delay = calculateReconnectionDelay(newAttempt, baseInterval, maxAttempts, multiplier);
    
    if (delay !== null) {
      logger.info(`Attempting to reconnect in ${delay}ms (attempt ${newAttempt}/${maxAttempts})`);
      
      /** @type {Promise<void>} */
      const reconnectPromise = new Promise((resolve) => {
        timeout = setTimeout(() => {
          connectCallback();
          resolve();
        }, delay);
      });
      
      await reconnectPromise;
    } else {
      logger.error('Maximum reconnection attempts reached');
      notifyWebSocketListeners('max_reconnect_attempts', {});
    }
  } else {
    logger.error('Maximum reconnection attempts reached');
    notifyWebSocketListeners('max_reconnect_attempts', {});
  }
  
  return { timeout, newAttempt };
}

/**
 * Handle WebSocket connection errors with appropriate logging and notifications
 * @param {Error} error - The error object
 * @param {string} context - The context where the error occurred
 */
export function handleWebSocketError(error, context) {
  logger.error(`WebSocket error in ${context}:`, error);
  notifyWebSocketListeners('error', { 
    message: error.message,
    context, 
    timestamp: Date.now() 
  });
} 