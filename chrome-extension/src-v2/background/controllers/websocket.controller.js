//@ts-check
/// <reference types="chrome"/>

/**
 * WebSocket Controller for handling WebSocket-related operations
 * 
 * This controller interfaces between the messaging layer and the WebSocket service,
 * providing a clean API for WebSocket operations like status checks, reconnection,
 * and request/response handling.
 * 
 * @fileoverview WebSocket controller for background service
 */

import { MESSAGE_TYPES } from '../../shared/constants/message-types.js';
import { logger } from '../../shared/utils/logger.js';
import * as websocketService from '../services/websocket.service.js';

/**
 * Initializes the WebSocket controller
 * Performs any necessary setup for WebSocket handling
 */
export function init() {
  logger.info('Initializing WebSocket Controller', 'websocket.controller');
  // Initialize WebSocket service
  websocketService.init();
}

/**
 * Handles messages related to WebSocket operations
 * Routes messages to appropriate handler functions based on message type
 * 
 * @param {Object} message - The received message
 * @param {string} message.type - The type of message (from MESSAGE_TYPES)
 * @param {Object} [message.data] - Any data associated with the message
 * @param {Function} sendResponse - Function to send response back to the caller
 * @returns {boolean} - True if response will be sent asynchronously
 */
export function handleMessage(message, sendResponse) {
  if (!message || !message.type) {
    logger.error('Invalid message format received', 'websocket.controller');
    return false;
  }
  
  switch (message.type) {
    case MESSAGE_TYPES.GET_WEBSOCKET_STATUS:
      handleGetWebSocketStatus(sendResponse);
      return true;
      
    case MESSAGE_TYPES.RECONNECT_WEBSOCKET:
      handleReconnectWebSocket(sendResponse);
      return true;
      
    case 'close_websocket':
      handleCloseWebSocket(message, sendResponse);
      return true;
      
    case MESSAGE_TYPES.SEND_WEBSOCKET_REQUEST:
      handleSendWebSocketRequest(message, sendResponse);
      return true;
      
    case MESSAGE_TYPES.REQUEST_PROFILE_DATA:
      handleRequestProfileData(message, sendResponse);
      return true;
      
    default:
      return false; // Message not handled by this controller
  }
}

/**
 * Handle WebSocket status request
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
function handleGetWebSocketStatus(sendResponse) {
  try {
    logger.info('Handling GET_WEBSOCKET_STATUS request', 'websocket.controller');
    const status = websocketService.getConnectionStatus();
    logger.info(`WebSocket status from service: ${status} (${typeof status})`, 'websocket.controller');
    
    const response = { success: true, status };
    logger.info(`Sending WebSocket status response: ${JSON.stringify(response)}`, 'websocket.controller');
    
    sendResponse(response);
  } catch (error) {
    logger.error(`Error getting WebSocket status: ${error.message}`, 'websocket.controller');
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Handle WebSocket reconnection request
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleReconnectWebSocket(sendResponse) {
  try {
    await websocketService.reconnect();
    const status = websocketService.getConnectionStatus();
    sendResponse({ success: true, status });
  } catch (error) {
    logger.error(`Error reconnecting WebSocket: ${error.message}`, 'websocket.controller');
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Handle WebSocket close request (for server switching)
 * 
 * @param {Object} message - The message with clearServerUrl flag
 * @param {Function} sendResponse - Function to send response back to the caller
 */
function handleCloseWebSocket(message, sendResponse) {
  try {
    const clearServerUrl = message.clearServerUrl || false;
    logger.info(`[WS_CONTROLLER] Closing WebSocket connection (clearServerUrl: ${clearServerUrl})`, 'websocket.controller');
    websocketService.closeWebSocket(clearServerUrl);
    sendResponse({ success: true, cleared: clearServerUrl });
  } catch (error) {
    logger.error(`Error closing WebSocket: ${error.message}`, 'websocket.controller');
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Handle sending WebSocket request
 * 
 * @param {Object} message - The message containing request details
 * @param {string} message.requestType - The type of WebSocket request
 * @param {string} message.requestId - Unique ID for the request
 * @param {Object} message.data - The request data
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleSendWebSocketRequest(message, sendResponse) {
  try {
    const { requestType, requestId, data } = message;
    
    if (!requestType || !requestId) {
      throw new Error('Invalid WebSocket request format');
    }
    
    const response = await websocketService.sendRequest(requestType, requestId, data);
    
    sendResponse({
      success: true,
      status: 'SUCCESS',
      requestId,
      data: response
    });
  } catch (error) {
    logger.error(`Error sending WebSocket request: ${error.message}`, 'websocket.controller');
    sendResponse({
      success: false,
      status: 'ERROR',
      requestId: message.requestId,
      error: error.message
    });
  }
}

/**
 * Handle request to get LinkedIn profile data
 * 
 * @param {Object} message - The message containing request details
 * @param {string} message.requestId - Unique ID for the request
 * @param {string} message.request_type - Type of profile data request
 * @param {Object} message.data - Additional request data
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleRequestProfileData(message, sendResponse) {
  try {
    // TODO: Implement profile data request handling
    logger.warn('handleProfileDataRequest not implemented in websocket.service', 'websocket.controller');
    sendResponse({
      success: false,
      requestId: message.requestId,
      error: 'Profile data request not implemented'
    });
  } catch (error) {
    logger.error(`Error handling profile data request: ${error.message}`, 'websocket.controller');
    sendResponse({
      success: false,
      requestId: message.requestId,
      error: error.message
    });
  }
}

/**
 * Broadcast WebSocket status to all UI components
 * 
 * @param {Object} status - The current WebSocket status
 */
export function broadcastStatus(status) {
  chrome.runtime.sendMessage({
    type: MESSAGE_TYPES.WEBSOCKET_STATUS_UPDATE,
    status
  }).catch(error => {
    logger.error(`Error broadcasting WebSocket status: ${error.message}`, 'websocket.controller');
  });
}

/**
 * Check if WebSocket is connected
 * 
 * @returns {boolean} True if WebSocket is connected
 */
export function isConnected() {
  return websocketService.isConnected();
} 