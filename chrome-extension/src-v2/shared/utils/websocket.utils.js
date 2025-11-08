// @ts-check

/**
 * Utility functions for WebSocket operations, connection management, and message handling.
 * These functions are UI-agnostic and focused on the WebSocket protocol.
 */

import { logger } from './logger.js';

/**
 * Constructs a WebSocket URL with the given user ID
 * @param {string} userId - The user ID to include in the URL
 * @param {string} baseWsUrl - The base WebSocket URL (without user ID)
 * @returns {string} - The complete WebSocket URL
 */
export function constructWebSocketUrl(userId, baseWsUrl) {
  if (!userId) {
    logger.error('Missing userId for WebSocket connection.', undefined, 'constructWebSocketUrl');
    throw new Error('Cannot construct WebSocket URL: Missing userId.');
  }
  
  // Ensure baseWsUrl doesn't end with a slash
  const normalizedBaseUrl = baseWsUrl.endsWith('/') 
    ? baseWsUrl.slice(0, -1) 
    : baseWsUrl;
  
  const wsUrl = `${normalizedBaseUrl}/${userId}`;
  logger.info(`Constructed WebSocket URL: ${wsUrl}`, 'constructWebSocketUrl');
  return wsUrl;
}

/**
 * Calculates the reconnection delay with exponential backoff
 * @param {number} currentDelay - The current delay in milliseconds
 * @param {number} multiplier - The multiplier for exponential backoff
 * @param {number} maxDelay - The maximum delay in milliseconds
 * @returns {number} - The next delay in milliseconds
 */
export function calculateReconnectDelay(currentDelay, multiplier, maxDelay) {
  const nextDelay = currentDelay * multiplier;
  const jitter = nextDelay * 0.1 * (Math.random() * 2 - 1);
  const finalDelay = Math.round(Math.min(nextDelay + jitter, maxDelay));
  logger.info(`Calculated reconnect delay: ${finalDelay}ms`, 'calculateReconnectDelay');
  return finalDelay;
}

/**
 * Safely parses a WebSocket message
 * @param {string} data - The raw message data
 * @returns {Object|null} - The parsed message or null if parsing failed
 */
export function parseWebSocketMessage(data) {
  if (typeof data !== 'string') {
    logger.warn('Received non-string WebSocket message. Cannot parse.', 'parseWebSocketMessage');
    return null;
  }
  
  try {
    const parsed = JSON.parse(data);
    logger.info('Successfully parsed WebSocket message.', 'parseWebSocketMessage');
    return parsed;
  } catch (error) {
    logger.error('Failed to parse WebSocket message JSON.', error, 'parseWebSocketMessage');
    return null;
  }
}

/**
 * Creates a properly formatted message for sending over WebSocket
 * @param {string} type - The message type
 * @param {Object} [payload={}] - The message payload
 * @returns {string} - Stringified JSON message
 */
export function createWebSocketMessage(type, payload = {}) {
  const message = {
    type,
    ...payload,
    timestamp: Date.now()
  };
  
  logger.info(`Creating WebSocket message of type: ${type}`, 'createWebSocketMessage');
  return JSON.stringify(message);
}

/**
 * Creates a ping message for WebSocket keep-alive
 * @returns {string} - Stringified ping message
 */
export function createPingMessage() {
  return createWebSocketMessage('ping', { id: generateMessageId() });
}

/**
 * Generates a unique message ID for request-response correlation
 * @returns {string} - A unique message ID
 */
export function generateMessageId() {
  return `ws-msg-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
}

/**
 * Handles a WebSocket error with proper logging
 * @param {any} error - The error event or object (typed as any to allow instanceof checks)
 * @param {string} context - The context where the error occurred
 * @param {Function} [callback] - Optional callback for additional error handling
 */
export function handleWebSocketError(error, context, callback) {
  let errorMessage = 'Unknown WebSocket error';

  if (error instanceof CloseEvent) {
    errorMessage = `WebSocket closed unexpectedly. Code: ${error.code}, Reason: ${error.reason || 'No reason specified'}`;
    logger.warn(errorMessage, context);
  } else if (error instanceof Error) {
    errorMessage = `WebSocket error: ${error.message}`;
    logger.error(errorMessage, error, context);
  } else if (error instanceof Event) { // Generic event, likely 'error' event
    errorMessage = 'WebSocket connection error event.';
    logger.error(errorMessage, undefined, context);
  } else {
    let unknownErrorDetails = 'Unknown error type';
    try {
      unknownErrorDetails = JSON.stringify(error);
    } catch (e) {
      unknownErrorDetails = 'Could not stringify error object';
    }
    logger.error(`Unknown WebSocket error object type: ${typeof error}. Details: ${unknownErrorDetails}`, undefined, context);
  }

  if (callback && typeof callback === 'function') {
    try {
      callback(errorMessage);
    } catch (callbackError) {
      logger.error('Error in WebSocket error callback.', callbackError, 'handleWebSocketError');
    }
  }
}

/**
 * Normalizes WebSocket readyState to a string representation
 * @param {number} readyState - The WebSocket readyState value (0-3)
 * @returns {string} - Human-readable connection state
 */
export function getConnectionStateName(readyState) {
  switch (readyState) {
    case WebSocket.CONNECTING:
      return 'CONNECTING';
    case WebSocket.OPEN:
      return 'OPEN';
    case WebSocket.CLOSING:
      return 'CLOSING';
    case WebSocket.CLOSED:
      return 'CLOSED';
    default:
      return 'UNKNOWN';
  }
}

/**
 * Creates a standard WebSocket status object
 * @param {WebSocket|null} ws - The WebSocket instance
 * @returns {Object} - Status object with connected flag and state name
 */
export function createWebSocketStatusObject(ws) {
  if (!ws) {
    return { connected: false, state: 'DISCONNECTED' };
  }
  
  return {
    connected: ws.readyState === WebSocket.OPEN,
    state: getConnectionStateName(ws.readyState)
  };
}

/**
 * Checks if a WebSocket connection is currently active
 * @param {WebSocket|null} ws - The WebSocket instance
 * @returns {boolean} - True if WebSocket is connected
 */
export function isWebSocketConnected(ws) {
  return !!ws && ws.readyState === WebSocket.OPEN;
}

/**
 * Safely closes a WebSocket connection with code and reason
 * @param {WebSocket|null} ws - The WebSocket instance to close
 * @param {number} [code=1000] - The close code (default: normal closure)
 * @param {string} [reason='Client initiated close'] - Close reason
 * @returns {boolean} - True if WebSocket was closed, false if already closed or null
 */
export function safelyCloseWebSocket(ws, code = 1000, reason = 'Client initiated close') {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    try {
      ws.close(code, reason);
      logger.info(`WebSocket closed with code ${code}: ${reason}`, 'safelyCloseWebSocket');
      return true;
    } catch (error) {
      logger.error('Error closing WebSocket.', error, 'safelyCloseWebSocket');
      return false;
    }
  }
  return false;
} 