//@ts-nocheck // Disabled due to multiple unrelated type errors
/// <reference types="chrome"/>

/**
 * WebSocket Service for handling WebSocket connections and operations
 * 
 * This service manages the WebSocket connection, reconnection, and message handling.
 * It provides a clean API for the WebSocket controller to interact with the WebSocket
 * and handle domain-specific requests.
 * 
 * @fileoverview WebSocket service implementation
 */

import appConfig from '../../shared/config/app.config.js';
import websocketConfig, { getWebSocketConfig } from '../../shared/config/websocket.config.js';
import { STORAGE_KEYS } from '../../shared/constants/storage-keys.js';
import { WS_MESSAGE_TYPES, MESSAGE_TYPES } from '../../shared/constants/message-types.js';
import { logger } from '../../shared/utils/logger.js';
import { handleError, createError } from '../../shared/utils/error-handler.js';
import * as messagingService from './messaging.service.js';
import { getAuthData } from './storage.service.js';
import { getInstanceId } from '../../shared/utils/instance-id.js';

// Import helper functions
import {
  addWebSocketListener,
  removeWebSocketListener,
  notifyWebSocketListeners,
  calculateReconnectionDelay,
  parseWebSocketMessage,
  createWebSocketMessage,
  handleWebSocketError
} from './websocket.helpers.js';
import { getLinkedInCookiesAndCsrf } from '../utils/linkedin-cookies.util.js';

// WebSocket instance
/** @type {WebSocket|null} */
let ws = null;

// Connection status
let isWsConnected = false;

// Track current server URL to detect switches
let currentServerUrl = null;

// Track current user ID to detect user switches
let currentUserId = null;

// Reconnection timer
/** @type {number|null} */
let reconnectTimer = null;

// Current reconnect delay (will be increased on each failed attempt)
let currentReconnectDelay = getWebSocketConfig('reconnection.INITIAL_DELAY', 1000);

// Reconnection attempt counter
let reconnectAttempt = 0;

// Maximum reconnection attempts
const MAX_RECONNECT_ATTEMPTS = 10;

// Keep-alive timers
/** @type {number|null} */
let pingInterval = null;

/** @type {number|null} */
let pongTimeout = null;

// Request tracking - maps request IDs to their callbacks
/** @type {Map<string, Function>} */
const pendingRequests = new Map();

/**
 * Initialize the WebSocket service
 * Starts the WebSocket connection
 */
export function init() {
  logger.info('Initializing WebSocket service', 'websocket.service');
  initWebSocket();
}

/**
 * Initialize WebSocket connection
 * @returns {Promise<void>}
 */
export async function initWebSocket() {
  logger.info('Attempting to initialize WebSocket connection', 'websocket.service');
  
  // --- Get User ID and Instance ID before connecting --- 
  let userId = null;
  let instanceId = null;
  try {
    // Get auth data from per-server storage
    const authData = await getAuthData();
    userId = authData.userId;
    
    if (!userId) {
      logger.info('WebSocket connection skipped: No user ID found in per-server storage', 'websocket.service');
      logger.info('[WEBSOCKET] User must be logged in first. Check server selection and login.', 'websocket.service');
      // Don't schedule reconnect if user is simply not logged in
      isWsConnected = false;
      broadcastStatusUpdate(false);
      stopKeepAlive(); // Ensure timers are stopped
      ws = null; // Ensure ws is null
      currentUserId = null; // Clear tracked user ID
      return; 
    }
    logger.info(`[WEBSOCKET] Found user ID from per-server storage: ${userId}`, 'websocket.service');

    // IMPORTANT: User changing should NOT disconnect WebSocket!
    // WebSocket is tied to browser instance (instance_id), not user
    // Users can login/logout/switch without affecting the connection
    if (currentUserId && currentUserId !== userId) {
      logger.info(`[WEBSOCKET] User changed from ${currentUserId} to ${userId} - WebSocket stays connected`, 'websocket.service');
      // Just update currentUserId for logging purposes
      currentUserId = userId;
    }

    // Don't open a new connection if one is already open or connecting
    if (ws !== null && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      logger.info('WebSocket connection attempt skipped: Already open or connecting', 'websocket.service');
      return;
    }
    
    // Get extension's own instance_id (unique per installation, persists across restarts)
    // This is the correct instance_id to use for WebSocket routing
    // Note: instance_id should exist from extension initialization, but handle gracefully if missing
    try {
      instanceId = await getInstanceId();
      if (instanceId) {
        logger.info(`[WEBSOCKET] Found extension instance_id: ${instanceId}`, 'websocket.service');
      } else {
        logger.warn('[WEBSOCKET] No instance_id found - extension may need initialization. Will connect as "default"', 'websocket.service');
        // Note: ensureInstanceId() should have been called on install, but handle gracefully
        // Connection will work, just registered as "default" instance
      }
    } catch (instanceError) {
      logger.warn(`[WEBSOCKET] Could not retrieve instance_id: ${instanceError.message}`, 'websocket.service');
      // Continue without instance_id - backward compatibility
      // Connection will work, just registered as "default" instance
    }
  } catch (error) {
    handleError(error, 'websocket.service.initWebSocket');
    logger.error(`Error retrieving user ID for WebSocket: ${error.message}`, 'websocket.service');
    // Schedule reconnect on storage error, as it might be temporary
    scheduleReconnect(); 
    return;
  }
  
  // Get dynamic WebSocket URL from appConfig
  const serverUrls = await appConfig.getServerUrls();
  const baseWssUrl = serverUrls.wssUrl;

  // IMPORTANT: WebSocket URL is based on instance_id ONLY, not user_id
  // This allows users to switch without affecting the WebSocket connection
  if (!instanceId) {
    logger.error('[WEBSOCKET] Cannot connect without instance_id', 'websocket.service');
    return;
  }

  // Construct WebSocket URL with instance_id query parameter
  const wsUrl = `${baseWssUrl}?instance_id=${encodeURIComponent(instanceId)}`;

  // Check if server changed - if so, force disconnect and reconnect
  if (currentServerUrl && currentServerUrl !== baseWssUrl) {
    logger.info(`[WEBSOCKET] Server changed from ${currentServerUrl} to ${baseWssUrl} - forcing reconnect`, 'websocket.service');
    if (ws) {
      ws.close();
      ws = null;
    }
  }

  // Store current server URL and user ID for future comparison
  // Note: User ID can change (login/logout) but WebSocket stays connected
  currentServerUrl = baseWssUrl;
  currentUserId = userId; // Tracked for logging only

  logger.info(`[WEBSOCKET] Preparing to connect for instance: ${instanceId}`, 'websocket.service');
  logger.info(`[WEBSOCKET] Current user (for logging): ${userId || 'none'}`, 'websocket.service');
  logger.info(`[WEBSOCKET] Base WSS URL (DYNAMIC): ${baseWssUrl}`, 'websocket.service');
  logger.info(`[WEBSOCKET] Full WebSocket URL: ${wsUrl}`, 'websocket.service');

  // Create a new WebSocket connection
  try {
    logger.info(`[WEBSOCKET] Connecting to WebSocket server at: ${wsUrl}`, 'websocket.service');
    ws = new WebSocket(wsUrl);
    
    // Set up event handlers
    ws.onopen = handleWsOpen;
    ws.onmessage = handleWsMessage;
    ws.onerror = handleWsError;
    // Pass user ID to onclose for potential specific cleanup
    ws.onclose = (event) => handleWsClose(event, userId); 
  } catch (error) {
    handleError(error, 'websocket.service.initWebSocket.connect');
    logger.error(`WebSocket connection error: ${error.message}`, 'websocket.service');
    scheduleReconnect();
  }
}

/**
 * Handle WebSocket connection opened
 */
async function handleWsOpen() {
  const serverUrls = await appConfig.getServerUrls();
  logger.info(`[WEBSOCKET] Connection ESTABLISHED to server: ${serverUrls.wssUrl}`, 'websocket.service');
  isWsConnected = true;

  // Reset reconnect delay and attempt counter
  currentReconnectDelay = getWebSocketConfig('reconnection.INITIAL_DELAY', 1000);
  reconnectAttempt = 0;

  // Clear any reconnect timer
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  // Refresh cookies and CSRF in the backend after reconnection
  // This ensures the backend has the latest credentials for proxy requests
  try {
    const authService = await import('./auth.service.js');
    logger.info('[WEBSOCKET] Refreshing LinkedIn credentials in backend after reconnection', 'websocket.service');
    await authService.updateBackendCredentials();
  } catch (error) {
    logger.warn(`[WEBSOCKET] Could not refresh backend credentials: ${error.message}`, 'websocket.service');
    // Non-critical error - connection is still usable
  }

  // Start keep-alive mechanism
  startKeepAlive();

  // Broadcast status update
  broadcastStatusUpdate(true);

  // Notify listeners
  notifyWebSocketListeners('connected', { connected: true });
}

/**
 * Handle WebSocket messages
 * @param {MessageEvent} event - The message event
 */
function handleWsMessage(event) {
  try {
    const message = parseWebSocketMessage(event.data);
    if (!message) {
      logger.error(`Invalid WebSocket message received: ${event.data}`, 'websocket.service');
      return;
    }
    
    logger.info(`WebSocket message received - type: ${message.type}, requestId: ${message.requestId || 'N/A'}`, 'websocket.service');
    
    // Ensure pong timeout is cleared on ANY valid message from server
    if (pongTimeout) {
      clearTimeout(pongTimeout);
      pongTimeout = null;
      logger.info('Cleared pong timeout due to received message', 'websocket.service');
    }
    
    // Check if this is a response to a pending request
    if (message.requestId && pendingRequests.has(message.requestId)) {
      const callback = pendingRequests.get(message.requestId);
      pendingRequests.delete(message.requestId);
      
      if (callback) {
        callback(message);
      }
      return;
    }
    
    // Handle different message types
    switch (message.type) {
      case WS_MESSAGE_TYPES.PONG:
        // Server acknowledged our ping
        handlePong();
        break;
      
      case WS_MESSAGE_TYPES.REQUEST_PROXY_HTTP:
        logger.info(`Processing REQUEST_PROXY_HTTP - request_id: ${message.request_id}, url: ${message.url?.substring(0, 100)}...`, 'websocket.service');
        handleProxyHttpRequest(message);
        break;

    case WS_MESSAGE_TYPES.REQUEST_REFRESH_LINKEDIN_SESSION:
      logger.info(`Processing REQUEST_REFRESH_LINKEDIN_SESSION`, 'websocket.service');
      handleRefreshLinkedInSession(message);
      break;
        
      case WS_MESSAGE_TYPES.NOTIFICATION:
        // Handle notifications from server
        handleServerNotification(message);
        break;
        
      default:
        logger.info(`Unhandled WebSocket message type: ${message.type}`, 'websocket.service');
    }
  } catch (error) {
    handleError(error, 'websocket.service.handleWsMessage');
    logger.error(`Error processing WebSocket message: ${error.message}`, 'websocket.service');
  }
}
/**
 * Handle refresh of LinkedIn session (cookies + CSRF)
 * @param {{ requestId: string }} message
 */
async function handleRefreshLinkedInSession(message) {
  const context = 'websocket.service.handleRefreshLinkedInSession';
  try {
    const { cookies, csrfToken } = await getLinkedInCookiesAndCsrf();
    if (!csrfToken || Object.keys(cookies).length === 0) {
      return sendWebSocketResponse({
        type: WS_MESSAGE_TYPES.RESPONSE_REFRESH_LINKEDIN_SESSION,
        request_id: message.requestId || message.request_id,
        status: 'error',
        error_message: 'Failed to retrieve LinkedIn cookies/CSRF'
      }, context);
    }

    // Respond with refreshed data
    await sendWebSocketResponse({
      type: WS_MESSAGE_TYPES.RESPONSE_REFRESH_LINKEDIN_SESSION,
      request_id: message.requestId || message.request_id,
      status: 'success',
      csrf_token: csrfToken,
      cookies
    }, context);
  } catch (error) {
    handleError(error, context);
    await sendWebSocketResponse({
      type: WS_MESSAGE_TYPES.RESPONSE_REFRESH_LINKEDIN_SESSION,
      request_id: message.requestId || message.request_id,
      status: 'error',
      error_message: error?.message || String(error)
    }, context);
  }
}

/**
 * Handle WebSocket errors
 * @param {Event} event - The error event
 */
function handleWsError(event) {
  logger.error('WebSocket error occurred', 'websocket.service');
  handleWebSocketError(new Error('WebSocket error'), 'websocket.service.handleWsError');
  // The onclose event will usually fire immediately after an error
}

/**
 * Handle WebSocket connection closed
 * @param {CloseEvent} event - The close event
 * @param {string} userId - The user ID associated with this connection attempt
 */
function handleWsClose(event, userId) {
  logger.info(`WebSocket connection closed: code=${event.code}, reason='${event.reason}', wasClean=${event.wasClean}, user=${userId}`, 'websocket.service');
  
  // Update connection state
  isWsConnected = false;
  
  // Stop keep-alive
  stopKeepAlive();
  
  // Clear WebSocket instance
  ws = null;
  
  // Broadcast status update
  broadcastStatusUpdate(false);
  
  // Notify listeners
  notifyWebSocketListeners('disconnected', { 
    code: event.code,
    reason: event.reason,
    wasClean: event.wasClean
  });
  
  // Schedule reconnect on ANY disconnect (clean or unclean)
  // Only skip reconnect if it was a manual close (code 1000) initiated by user
  const isManualClose = event.code === 1000 && event.reason === 'Manual reconnection';
  if (!isManualClose) {
    logger.info(`Scheduling reconnection (code: ${event.code}, clean: ${event.wasClean})`, 'websocket.service');
    scheduleReconnect();
  } else {
    logger.info('Skipping reconnection: manual close for reconnection', 'websocket.service');
  }
}

/**
 * Schedule WebSocket reconnection with exponential backoff
 */
function scheduleReconnect() {
  // Don't schedule multiple reconnection attempts
  if (reconnectTimer !== null) {
    logger.info('Reconnection already scheduled', 'websocket.service');
    return;
  }
  
  reconnectAttempt++;
  if (reconnectAttempt > MAX_RECONNECT_ATTEMPTS) {
    logger.error(`Maximum reconnection attempts (${MAX_RECONNECT_ATTEMPTS}) reached`, 'websocket.service');
    notifyWebSocketListeners('max_reconnect_attempts', { attempts: reconnectAttempt });
    return;
  }
  
  // Calculate delay with exponential backoff
  const delay = Math.min(
    currentReconnectDelay * Math.pow(getWebSocketConfig('reconnection.MULTIPLIER', 1.5), reconnectAttempt - 1),
    getWebSocketConfig('reconnection.MAX_DELAY', 30000)
  );
  
  logger.info(`Scheduling reconnection in ${delay}ms (attempt ${reconnectAttempt}/${MAX_RECONNECT_ATTEMPTS})`, 'websocket.service');
  
  // Schedule reconnection
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    initWebSocket();
  }, delay);
}

/**
 * Start keep-alive mechanism
 */
function startKeepAlive() {
  // Clear any existing timers
  stopKeepAlive();
  
  // Set up ping interval
  if (getWebSocketConfig('keepAlive.AUTO_PING', true)) {
    pingInterval = setInterval(sendPing, getWebSocketConfig('keepAlive.PING_INTERVAL', 30000));
    logger.info(`Started keep-alive ping interval (${getWebSocketConfig('keepAlive.PING_INTERVAL', 30000)}ms)`, 'websocket.service');
  }
}

/**
 * Stop keep-alive mechanism
 */
function stopKeepAlive() {
  // Clear ping interval
  if (pingInterval) {
    clearInterval(pingInterval);
    pingInterval = null;
  }
  
  // Clear pong timeout
  if (pongTimeout) {
    clearTimeout(pongTimeout);
    pongTimeout = null;
  }
  
  logger.info('Stopped keep-alive mechanism', 'websocket.service');
}

/**
 * Send ping message to server
 */
function sendPing() {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    logger.info('Cannot send ping: WebSocket not open', 'websocket.service');
    return;
  }
  
  // Send ping
  try {
    const pingMessage = createWebSocketMessage(WS_MESSAGE_TYPES.PING);
    ws.send(pingMessage);
    logger.info('Sent ping to server', 'websocket.service');
    
    // Set up pong timeout
    pongTimeout = setTimeout(handlePongTimeout, getWebSocketConfig('keepAlive.PONG_TIMEOUT', 10000));
  } catch (error) {
    handleError(error, 'websocket.service.sendPing');
    logger.error(`Error sending ping: ${error.message}`, 'websocket.service');
  }
}

/**
 * Handle pong timeout
 */
function handlePongTimeout() {
  logger.warn('Pong message not received within timeout. Closing WebSocket connection.', 'websocket.service');
  ws?.close();
}

/**
 * Broadcast WebSocket status update to UI
 * @param {boolean} status - WebSocket connection status
 */
function broadcastStatusUpdate(status) {
  try {
    messagingService.broadcastMessage({
      type: MESSAGE_TYPES.WEBSOCKET_STATUS_UPDATE,
      status: status,  // Direct status field for ApiStatus component
      timestamp: Date.now()
    }).catch(error => {
      if (error && error.message && error.message.includes('Could not establish connection')) {
        logger.info('WebSocket status broadcast skipped: No receiving end exists.', 'websocket.service');
      } else {
        handleError(createError('MessagingError', 'Failed to broadcast WebSocket status', 'websocket.service.broadcastStatusUpdate', error));
      }
    });
    logger.info(`Broadcast WebSocket status update to UI: ${status}`, 'websocket.service');
  } catch (error) {
    handleError(createError('MessagingError', 'Error during broadcastStatus setup', 'websocket.service.broadcastStatusUpdate', error));
  }
}

/**
 * Handle pong message from server
 */
function handlePong() {
  logger.info('Received pong from server', 'websocket.service');
  
  // Clear pong timeout
  if (pongTimeout) {
    clearTimeout(pongTimeout);
    pongTimeout = null;
  }
}

/**
 * Executes a LinkedIn function in a modular way
 * This is the same logic used by local tests via EXECUTE_FUNCTION
 * 
 * @param {string} functionName - Name of the function to execute
 * @param {Object} params - Parameters for the function
 * @returns {Promise<{success: boolean, data?: any, error?: string}>}
 */

/**
 * Handle server notification
 * @param {Object} message - The notification message
 */
function handleServerNotification(message) {
  logger.info(`Received server notification: ${JSON.stringify(message)}`, 'websocket.service');
  
  // Forward notification to UI or handle specific notification types
  notifyWebSocketListeners('notification', message);
}


/**
 * Send message to tab
 * @param {number} tabId - Chrome tab ID
 * @param {Object} message - Message to send
 * @returns {Promise<any>} Response from the tab
 */
async function sendMessageToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    try {
      chrome.tabs.sendMessage(tabId, message, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        resolve(response);
      });
    } catch (error) {
      reject(error);
    }
  });
}


/**
 * Get WebSocket connection status
 * @returns {boolean} True if WebSocket is connected
 */
export function getConnectionStatus() {
  const connected = isConnected();
  logger.info(`getConnectionStatus called, returning: ${connected} (type: ${typeof connected})`, 'websocket.service');
  return connected;
}

/**
 * Check if WebSocket is connected
 * @returns {boolean} True if WebSocket is connected
 */
export function isConnected() {
  const wsExists = !!ws;
  const wsReadyState = ws ? ws.readyState : 'null';
  const isOpen = wsExists && ws.readyState === WebSocket.OPEN;
  
  logger.info(`isConnected check: ws exists=${wsExists}, readyState=${wsReadyState}, isOpen=${isOpen}`, 'websocket.service');
  
  return isOpen;
}

/**
 * Forcefully reconnect the WebSocket
 * @returns {Promise<void>}
 */
export async function reconnect() {
  logger.info('Manual WebSocket reconnection requested', 'websocket.service');

  // Close existing connection if open and wait for it to complete
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    try {
      // Create a promise that resolves when the connection is fully closed
      const closePromise = new Promise((resolve) => {
        const originalOnClose = ws.onclose;
        ws.onclose = (event) => {
          logger.info('WebSocket closed for reconnection', 'websocket.service');
          // Call original handler if it exists (but don't trigger reconnect)
          if (originalOnClose && event.code !== 1000) {
            // Only call original if not manual close
          }
          resolve();
        };

        // Set a timeout in case close doesn't complete
        setTimeout(resolve, 2000); // 2 second timeout
      });

      ws.close(1000, 'Manual reconnection');

      // Wait for the close to complete
      await closePromise;
      logger.info('WebSocket close completed, proceeding with reconnection', 'websocket.service');
    } catch (error) {
      handleError(error, 'websocket.service.reconnect');
      logger.error(`Error closing WebSocket for reconnection: ${error.message}`, 'websocket.service');
    }
  }

  // Reset reconnection state
  ws = null;
  isWsConnected = false;

  // Clear any existing timers
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  stopKeepAlive();

  // Reset reconnect delay and attempt counter
  currentReconnectDelay = getWebSocketConfig('reconnection.INITIAL_DELAY', 1000);
  reconnectAttempt = 0;

  // Small delay to ensure clean state before reconnecting
  await new Promise(resolve => setTimeout(resolve, 100));

  // Attempt to reconnect immediately
  await initWebSocket();
}

/**
 * Close WebSocket connection (for server switching)
 * @param {boolean} [clearServerUrl=false] - Whether to clear the stored server URL
 */
export function closeWebSocket(clearServerUrl = false) {
  logger.info(`[WEBSOCKET] Closing WebSocket connection (clearServerUrl: ${clearServerUrl})`, 'websocket.service');
  
  if (ws) {
    // Remove event handlers to prevent reconnection
    ws.onclose = null;
    ws.onerror = null;
    ws.onmessage = null;
    ws.onopen = null;
    
    try {
      ws.close(1000, clearServerUrl ? 'Server switch' : 'User logout');
    } catch (error) {
      logger.error(`Error closing WebSocket: ${error.message}`, 'websocket.service');
    }
    ws = null;
  }
  
  isWsConnected = false;
  stopKeepAlive();
  
  // Clear any pending reconnect timers
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  
  // Reset reconnection attempt counter
  reconnectAttempt = 0;
  currentReconnectDelay = getWebSocketConfig('reconnection.INITIAL_DELAY', 1000);
  
  // Clear server URL if switching servers
  if (clearServerUrl) {
    logger.info('[WEBSOCKET] Clearing stored server URL (server switch)', 'websocket.service');
    currentServerUrl = null;
  }
  
  // Clear tracked user ID
  currentUserId = null;
  
  // Clear pending requests
  pendingRequests.clear();
  
  // Broadcast status update
  broadcastStatusUpdate(false);
  
  logger.info(`[WEBSOCKET] WebSocket fully closed and cleaned up`, 'websocket.service');
}

/**
 * Send a request through the WebSocket
 * @param {string} type - The request type
 * @param {string} requestId - Unique ID for the request
 * @param {Object} data - The request data
 * @returns {Promise<Object>} The response data
 */
export function sendRequest(type, requestId, data) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    return Promise.reject(new Error('WebSocket is not connected'));
  }
  
  return new Promise((resolve, reject) => {
    try {
      // Create the message
      const message = {
        type,
        requestId,
        ...data
      };
      
      // Register callback for the response
      pendingRequests.set(requestId, (response) => {
        if (response.error) {
          reject(new Error(response.error));
        } else {
          resolve(response);
        }
      });
      
      // Send the message
      ws.send(JSON.stringify(message));
      logger.info(`Sent WebSocket request - type: ${message.type}, requestId: ${requestId}`, 'websocket.service');
      
      // Set up timeout to prevent hanging promises
      setTimeout(() => {
        if (pendingRequests.has(requestId)) {
          pendingRequests.delete(requestId);
          reject(new Error('WebSocket request timed out'));
        }
      }, 30000); // 30 seconds timeout
    } catch (error) {
      pendingRequests.delete(requestId);
      reject(error);
    }
  });
}

function resetReconnectAttempt() {
  reconnectAttempt = 0;
  currentReconnectDelay = getWebSocketConfig('reconnection.INITIAL_DELAY', 1000);
  logger.info('WebSocket reconnection counter reset', 'websocket.service');
}

/**
 * Handle generic HTTP proxy request from backend
 * Executes the HTTP request in browser context with credentials and returns raw response
 * @param {Object} message - The proxy request message
 * @returns {Promise<void>}
 */
async function handleProxyHttpRequest(message) {
  const context = 'websocket.service.handleProxyHttpRequest';
  const { request_id, url, method = 'GET', headers = {}, body = null, response_type = 'json', include_credentials = true } = message;
  
  if (!request_id || !url) {
    logger.error('[PROXY_HTTP] Missing required fields: request_id or url', context);
    return;
  }
  
  try {
    logger.info(`[PROXY_HTTP] Executing ${method} request to ${url.substring(0, 100)}...`, context);
    
    // Normalize URL - if it starts with /, prefix with LinkedIn base URL
    let targetUrl = url;
    if (url.startsWith('/')) {
      targetUrl = `https://www.linkedin.com${url}`;
      logger.info(`[PROXY_HTTP] Normalized relative URL to: ${targetUrl}`, context);
    }
    
    // Filter forbidden headers that browsers don't allow setting
    const forbiddenHeaders = [
      'cookie', 'host', 'content-length', 'connection', 
      'accept-encoding', 'origin', 'referer', 'user-agent',
      'upgrade-insecure-requests', 'pragma', 'cache-control'
    ];
    
    const filteredHeaders = {};
    for (const [key, value] of Object.entries(headers)) {
      const lowerKey = key.toLowerCase();
      // Filter forbidden headers and sec-* headers
      if (!forbiddenHeaders.includes(lowerKey) && !lowerKey.startsWith('sec-')) {
        filteredHeaders[key] = value;
      }
    }
    
    logger.info(`[PROXY_HTTP] Filtered headers from ${Object.keys(headers).length} to ${Object.keys(filteredHeaders).length}`, context);
    
    // Build fetch options
    const fetchOptions = {
      method: method,
      headers: filteredHeaders,
      credentials: include_credentials ? 'include' : 'omit',
      redirect: 'follow',
      cache: 'no-store'
    };
    
    // Add body if present (for POST, PUT, etc.)
    if (body !== null && method !== 'GET' && method !== 'HEAD') {
      fetchOptions.body = body;
    }
    
    // Execute the fetch request
    logger.info(`[PROXY_HTTP] Executing fetch with credentials: ${include_credentials}`, context);
    const response = await fetch(targetUrl, fetchOptions);
    
    logger.info(`[PROXY_HTTP] Received response: status=${response.status}`, context);
    
    // Extract response headers (only allowed ones)
    const responseHeaders = {};
    const allowedResponseHeaders = ['content-type', 'x-restli-protocol-version', 'content-length'];
    for (const header of allowedResponseHeaders) {
      const value = response.headers.get(header);
      if (value) {
        responseHeaders[header] = value;
      }
    }
    
    // Read response body based on response_type
    let responseBody;
    if (response_type === 'json' || response_type === 'text') {
      responseBody = await response.text();
      logger.info(`[PROXY_HTTP] Read response as text, length: ${responseBody.length}`, context);
    } else if (response_type === 'bytes') {
      const arrayBuffer = await response.arrayBuffer();
      // Convert to base64
      const bytes = new Uint8Array(arrayBuffer);
      responseBody = btoa(String.fromCharCode.apply(null, bytes));
      logger.info(`[PROXY_HTTP] Read response as bytes (base64), length: ${responseBody.length}`, context);
    } else {
      // Default to text
      responseBody = await response.text();
      logger.info(`[PROXY_HTTP] Read response as text (default), length: ${responseBody.length}`, context);
    }
    
    // Send success response
    const responsePayload = {
      type: WS_MESSAGE_TYPES.RESPONSE_PROXY_HTTP,
      request_id: request_id,
      status: 'success',
      status_code: response.status,
      headers: responseHeaders,
      body: responseBody
    };
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      logger.info(`[PROXY_HTTP] Sending success response for request_id ${request_id}`, context);
      ws.send(JSON.stringify(responsePayload));
    } else {
      logger.error(`[PROXY_HTTP] WebSocket not open when trying to send response for request_id ${request_id}`, context);
    }
    
  } catch (error) {
    logger.error(`[PROXY_HTTP] Error executing HTTP request: ${error.message}`, context);
    
    // Send error response
    const errorPayload = {
      type: WS_MESSAGE_TYPES.RESPONSE_PROXY_HTTP,
      request_id: request_id,
      status: 'error',
      error_message: `Failed to execute HTTP request: ${error.message}`
    };
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      logger.info(`[PROXY_HTTP] Sending error response for request_id ${request_id}`, context);
      ws.send(JSON.stringify(errorPayload));
    } else {
      logger.error(`[PROXY_HTTP] WebSocket not open when trying to send error response for request_id ${request_id}`, context);
    }
  }
} 