//@ts-check
/// <reference types="chrome"/>

/**
 * Messaging Service
 * 
 * Centralizes the handling of extension messages, providing a clean interface for
 * registering message handlers and routing messages to the appropriate controllers.
 * 
 * @fileoverview Extension messaging service
 */

import { logger } from '../../shared/utils/logger.js';
import { handleError } from '../../shared/utils/error-handler.js';

/**
 * @typedef {Object} MessageHandler
 * @property {Function} handleMessage - Function that handles a message
 * @property {Function} [handleAuthSession] - Function that handles auth session message
 */

/** @type {MessageHandler[]} */
const messageHandlers = [];

/**
 * Initializes the messaging service
 * Sets up the message listener
 */
export function init() {
  logger.info('Initializing messaging service', 'messaging.service');
  
  // Set up message listener
  chrome.runtime.onMessage.addListener(handleMessage);
  
  logger.info('Messaging service initialized', 'messaging.service');
}

/**
 * Registers a controller as a message handler
 * 
 * @param {MessageHandler} handler - The controller that will handle messages
 */
export function registerMessageHandler(handler) {
  if (!handler || typeof handler.handleMessage !== 'function') {
    logger.error('Invalid message handler: missing handleMessage function', 'messaging.service');
    return;
  }
  
  messageHandlers.push(handler);
  logger.info('Message handler registered', 'messaging.service');
}

/**
 * Handles all incoming messages and routes them to the appropriate handlers
 * 
 * @param {Object} message - The message received
 * @param {string} [message.type] - The type of message
 * @param {string} [message.action] - The action for special messages
 * @param {Object} [message.data] - Any data associated with the message
 * @param {chrome.runtime.MessageSender} sender - Information about the sender
 * @param {Function} sendResponse - Function to send response back to the caller
 * @returns {boolean} - True if response will be sent asynchronously
 */
function handleMessage(message, sender, sendResponse) {
  try {
    logger.info(`Received message: ${JSON.stringify(message)}`, 'messaging.service');
    
    // Special handling for auth_session message from login page
    if (message.action === 'auth_session') {
      for (const handler of messageHandlers) {
        if (handler.handleAuthSession) {
          handler.handleAuthSession(message.data, (result) => {
            sendResponse(result);
          });
          return true; // Keep the message channel open for sendResponse
        }
      }
    }
    
    // Handle page navigation events or other messages with data but no type
    if (message && message.data && message.data.url && !message.type) {
      logger.info(`Received page navigation event to: ${message.data.url}`, 'messaging.service');
      // We could potentially do something with this data if needed
      sendResponse({ received: true });
      return false;
    }
    
    // Make sure regular messages have a type
    if (!message || !message.type) {
      logger.error('Message received with no type', 'messaging.service');
      sendResponse({ error: 'Invalid message format' });
      return false;
    }
    
    // Try each registered handler
    for (const handler of messageHandlers) {
      if (handler.handleMessage(message, sendResponse)) {
        return true; // This handler is managing the response
      }
    }
    
    // No handler claimed this message
    logger.error(`Unhandled message type: ${message.type}`, 'messaging.service');
    sendResponse({ error: `Unknown message type: ${message.type}` });
    return false;
    
  } catch (error) {
    handleError(error, 'messaging.service.handleMessage');
    sendResponse({ error: `Error processing message: ${error.message}` });
    return false;
  }
}

/**
 * Sends a message to a specific tab
 * 
 * @param {number} tabId - The ID of the tab to send the message to
 * @param {Object} message - The message to send
 * @returns {Promise<any>} - The response from the recipient
 */
export function sendMessageToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    try {
      chrome.tabs.sendMessage(tabId, message, response => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
        } else {
          resolve(response);
        }
      });
    } catch (error) {
      handleError(error, 'messaging.service.sendMessageToTab');
      reject(error);
    }
  });
}

/**
 * Sends a message to all tabs that match the specified URL pattern
 * 
 * @param {string|RegExp} urlPattern - URL pattern to match tabs against
 * @param {Object} message - The message to send
 * @returns {Promise<Array<any>>} - Array of responses from the recipients
 */
export function sendMessageToMatchingTabs(urlPattern, message) {
  return new Promise((resolve, reject) => {
    try {
      chrome.tabs.query({}, tabs => {
        const matchingTabs = tabs.filter(tab => {
          if (!tab.url) return false;
          return typeof urlPattern === 'string' 
            ? tab.url.includes(urlPattern) 
            : urlPattern.test(tab.url);
        });
        
        const promises = matchingTabs.map(tab => {
          return sendMessageToTab(tab.id, message);
        });
        
        Promise.all(promises)
          .then(resolve)
          .catch(reject);
      });
    } catch (error) {
      handleError(error, 'messaging.service.sendMessageToMatchingTabs');
      reject(error);
    }
  });
}

/**
 * Broadcasts a message to all tabs
 * 
 * @param {Object} message - The message to broadcast
 * @returns {Promise<Array<any>>} - Array of responses from the recipients
 */
export function broadcastMessage(message) {
  return new Promise((resolve, reject) => {
    try {
      chrome.tabs.query({}, tabs => {
        const promises = tabs.map(tab => {
          return sendMessageToTab(tab.id, message);
        });
        
        Promise.all(promises)
          .then(resolve)
          .catch(reject);
      });
    } catch (error) {
      handleError(error, 'messaging.service.broadcastMessage');
      reject(error);
    }
  });
}

/**
 * Sends a message to the extension's background script
 * 
 * @param {Object} message - The message to send
 * @returns {Promise<any>} - The response from the background script
 */
export function sendMessageToBackground(message) {
  return new Promise((resolve, reject) => {
    try {
      chrome.runtime.sendMessage(message, response => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
        } else {
          resolve(response);
        }
      });
    } catch (error) {
      handleError(error, 'messaging.service.sendMessageToBackground');
      reject(error);
    }
  });
} 