//@ts-check

/**
 * WebSocket-specific configuration
 * 
 * @fileoverview Comprehensive configuration settings for WebSocket connections.
 * This file consolidates all WebSocket-related configuration and extends the
 * basic settings from app.config.js with additional detailed options.
 */

import appConfig from './app.config.js';

/**
 * WebSocket connection configuration
 * @typedef {Object} WSConnectionConfig
 * @property {string} WSS_URL - WebSocket server URL
 * @property {number} CONNECTION_TIMEOUT - Maximum time to wait for connection establishment in ms
 * @property {boolean} AUTO_RECONNECT - Whether to automatically attempt to reconnect on disconnection
 * @property {number} HANDSHAKE_TIMEOUT - Maximum time to wait for protocol handshake in ms
 */

/**
 * WebSocket reconnection configuration
 * @typedef {Object} WSReconnectionConfig
 * @property {number} INITIAL_DELAY - Initial delay before reconnection attempt in ms
 * @property {number} MAX_DELAY - Maximum delay between reconnection attempts in ms
 * @property {number} MULTIPLIER - Factor for exponential backoff
 * @property {number} MAX_RETRIES - Maximum number of reconnection attempts
 * @property {boolean} RESET_RETRY_COUNT_ON_SUCCESS - Whether to reset retry counter after successful connection
 * @property {number} STABLE_CONNECTION_TIME - Time connected needed to consider connection stable (resets retry count) in ms
 */

/**
 * WebSocket keep-alive configuration
 * @typedef {Object} WSKeepAliveConfig
 * @property {number} PING_INTERVAL - Interval for sending ping messages in ms
 * @property {number} PONG_TIMEOUT - Time to wait for pong response in ms
 * @property {boolean} AUTO_PING - Whether to automatically send ping messages
 * @property {number} NO_DATA_TIMEOUT - Maximum time to wait for any message before considering connection dead in ms
 */

/**
 * WebSocket message configuration
 * @typedef {Object} WSMessageConfig
 * @property {number} MAX_MESSAGE_SIZE - Maximum allowed message size in bytes
 * @property {boolean} VALIDATE_JSON - Whether to validate all messages as JSON
 * @property {number} MESSAGE_QUEUE_SIZE - Maximum size of unsent message queue
 * @property {number} DEFAULT_REQUEST_TIMEOUT - Default timeout for request-response pattern in ms
 */

/**
 * Complete WebSocket configuration
 * Consider environment-specific overrides here for properties like WSS_URL.
 * @typedef {Object} WebSocketConfig
 * @property {WSConnectionConfig} connection - Connection settings
 * @property {WSReconnectionConfig} reconnection - Reconnection and retry settings
 * @property {WSKeepAliveConfig} keepAlive - Keep-alive and heartbeat settings
 * @property {WSMessageConfig} message - Message handling settings
 */

/**
 * WebSocket configuration
 * @type {WebSocketConfig}
 */
const websocketConfig = {
  // Connection settings
  connection: {
    WSS_URL: appConfig.WSS_URL, // Consider environment override
    CONNECTION_TIMEOUT: 10000, // 10 seconds
    AUTO_RECONNECT: true,
    HANDSHAKE_TIMEOUT: 5000, // 5 seconds
  },
  
  // Reconnection settings
  reconnection: {
    INITIAL_DELAY: appConfig.WS_INITIAL_RECONNECT_DELAY,
    MAX_DELAY: appConfig.WS_MAX_RECONNECT_DELAY,
    MULTIPLIER: appConfig.WS_RECONNECT_MULTIPLIER,
    MAX_RETRIES: 10,
    RESET_RETRY_COUNT_ON_SUCCESS: true,
    STABLE_CONNECTION_TIME: 60000, // 1 minute
  },
  
  // Keep-alive settings
  keepAlive: {
    PING_INTERVAL: appConfig.WS_PING_INTERVAL,
    PONG_TIMEOUT: appConfig.WS_PONG_TIMEOUT,
    AUTO_PING: true,
    NO_DATA_TIMEOUT: 45000, // 45 seconds
  },
  
  // Message settings
  message: {
    MAX_MESSAGE_SIZE: 1048576, // 1MB
    VALIDATE_JSON: true,
    MESSAGE_QUEUE_SIZE: 100,
    DEFAULT_REQUEST_TIMEOUT: 30000, // 30 seconds
  }
};

export default websocketConfig;

/**
 * Helper function to access nested configuration with fallbacks
 * @param {string} path - Dot-notation path to configuration value
 * @param {*} defaultValue - Default value if path is not found
 * @returns {*} Configuration value or default
 */
export function getWebSocketConfig(path, defaultValue) {
  const parts = path.split('.');
  let current = websocketConfig;
  
  for (const part of parts) {
    if (current === undefined || current === null || typeof current !== 'object') {
      return defaultValue;
    }
    current = current[part];
  }
  
  return current !== undefined ? current : defaultValue;
}

// Removing backward compatibility exports - use websocketConfig directly or getWebSocketConfig helper.
/*
export const CONNECTION_TIMEOUT = websocketConfig.connection.CONNECTION_TIMEOUT;
export const AUTO_RECONNECT = websocketConfig.connection.AUTO_RECONNECT;
export const MAX_RETRIES = websocketConfig.reconnection.MAX_RETRIES;
export const AUTO_PING = websocketConfig.keepAlive.AUTO_PING; 
*/ 