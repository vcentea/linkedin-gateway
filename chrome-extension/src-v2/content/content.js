//@ts-check
/// <reference types="chrome"/>

/**
 * Main content script entry point
 * 
 * This script is injected into web pages and coordinates between domain-specific
 * modules and the background script via the messaging system.
 * 
 * @fileoverview Main content script
 */

import { logger } from '../shared/utils/logger.js';
import { MESSAGE_TYPES } from '../shared/constants/message-types.js';
import { handleError, createError } from '../shared/utils/error-handler.js';
import * as feedUtils from './linkedin/feed.js';
import * as commentsUtils from './linkedin/comments.js';

// Map function names to actual functions for local execution
const localFunctions = {
    fetchPostsFromFeed: feedUtils.fetchPostsFromFeed,
    fetchCommentersForPost: commentsUtils.fetchCommentersForPost,
    parseLinkedInPostUrl: feedUtils.parseLinkedInPostUrl
    // Add other locally testable functions here
};

/**
 * Initialize the content script
 */
function init() {
  const isLinkedIn = window.location.hostname.includes('linkedin.com');
  const logContext = 'content:init';

  if (isLinkedIn) {
    logger.info('LinkedIn content script initializing', logContext);
    initializeLinkedIn();
  } else {
    logger.info('Content script initialized on non-LinkedIn page', logContext);
  }

  if (chrome.runtime?.onMessage) {
      chrome.runtime.onMessage.addListener(handleMessage);
       logger.info('Message listener added.', logContext);
  } else {
       logger.error(createError('SetupError', 'chrome.runtime.onMessage is not available.', logContext));
  }
}

/**
 * Initialize LinkedIn-specific functionality and report readiness
 */
function initializeLinkedIn() {
  const logContext = 'content:initializeLinkedIn';
  logger.info('Setting up LinkedIn-specific functionality', logContext);
  
  // Report readiness to the background script
  if (chrome.runtime?.sendMessage) {
    chrome.runtime.sendMessage({ type: MESSAGE_TYPES.CONTENT_SCRIPT_READY }, (response) => {
      if (chrome.runtime.lastError) {
        logger.error(createError('MessagingError', `Error sending CONTENT_SCRIPT_READY: ${chrome.runtime.lastError.message}`, logContext));
      } else {
        logger.info(`Background acknowledged CONTENT_SCRIPT_READY: ${JSON.stringify(response)}`, logContext);
      }
    });
  } else {
    logger.error(createError('SetupError', 'chrome.runtime.sendMessage is not available.', logContext));
  }
  
  // Add other LinkedIn-specific initializations here (e.g., MutationObservers)
}

/**
 * Handle messages from the background script or other parts of the extension
 *
 * @param {any} message - The message object (type any for flexibility from runtime)
 * @param {chrome.runtime.MessageSender} sender - Information about the sender
 * @param {Function} sendResponse - Function to send a response
 * @returns {boolean|undefined} - Return true to indicate asynchronous response, otherwise undefined/false.
 */
function handleMessage(message, sender, sendResponse) {
  const logContext = 'content:handleMessage';
  logger.info(`Received message: Type=${message?.type}, Sender=${sender?.id}`, logContext);

  if (!message || !message.type) {
    const errorMsg = 'Invalid message format received.';
    logger.error(createError('MessageError', errorMsg, logContext));
    sendResponse({ success: false, error: errorMsg });
    return false; // Synchronous response
  }

  // Centralized handling using a map
  const handlers = {
      [MESSAGE_TYPES.GET_CSRF_TOKEN]: handleGetCsrfToken,
      [MESSAGE_TYPES.REQUEST_GET_POSTS]: handleGetPosts,
      [MESSAGE_TYPES.REQUEST_GET_COMMENTERS]: handleGetCommenters,
      [MESSAGE_TYPES.EXECUTE_FUNCTION]: handleExecuteFunction,
  };

  const handler = handlers[message.type];

  if (handler) {
      try {
          const isAsync = handler(message.data || {}, sendResponse); 
          return isAsync; 
      } catch (error) {
          const err = (error instanceof Error) ? error : createError('HandlerError', String(error), logContext);
          logger.error(`Error executing handler for ${message.type}: ${err.message}`, logContext, err);
          sendResponse({ success: false, error: `Handler error: ${err.message}` });
          return false; 
      }
  } else {
      logger.warn(`No handler found for message type: ${message.type}`, logContext);
      sendResponse({ success: false, error: `Unknown message type: ${message.type}` });
      return false; 
  }
}

/**
 * Handle request to get CSRF token from LinkedIn cookies
 *
 * @param {any} data - Message data (expected to be empty)
 * @param {Function} sendResponse - Function to send a response
 */
function handleGetCsrfToken(data, sendResponse) {
  logger.info('Handling CSRF token request', 'content');
  
  try {
    // Get JSESSIONID from cookies
    const cookies = document.cookie.split(';');
    let csrfToken = null;
    
    for (const cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === 'JSESSIONID') {
        // Remove quotes if present
        csrfToken = value.replace(/^"(.*)"$/, '$1');
        break;
      }
    }
    
    if (csrfToken) {
      logger.info('CSRF token retrieved successfully', 'content');
      sendResponse({
        success: true,
        data: { csrfToken }
      });
    } else {
      logger.error('CSRF token not found in cookies', 'content');
      sendResponse({
        success: false,
        error: 'CSRF token not found'
      });
    }
  } catch (error) {
    logger.error(`Error retrieving CSRF token: ${error.message}`, 'content');
    sendResponse({
      success: false,
      error: `Error retrieving CSRF token: ${error.message}`
    });
  }
}

/**
 * Handle request to get LinkedIn posts
 *
 * @param {Object} data - Post request data
 * @param {number} data.startIndex - Starting index for posts
 * @param {number} data.count - Number of posts to fetch
 * @param {string} data.csrfToken - CSRF token for LinkedIn API
 * @param {Function} sendResponse - Function to send a response
 */
async function handleGetPosts(data, sendResponse) {
  logger.info(`Handling get posts request - startIndex: ${data.startIndex}, count: ${data.count}`, 'content');
  
  try {
    const { startIndex, count, csrfToken } = data;
    
    if (!csrfToken) {
      throw new Error('CSRF token is required');
    }
    
    const posts = await feedUtils.fetchPostsFromFeed(startIndex, count, csrfToken);
    
    logger.info(`Successfully fetched ${posts.length} posts`, 'content');
    sendResponse({
      success: true,
      data: { posts }
    });
  } catch (error) {
    logger.error(`Error fetching posts: ${error.message}`, 'content');
    sendResponse({
      success: false,
      error: `Error fetching posts: ${error.message}`
    });
  }
}

/**
 * Handle request to get commenters on a LinkedIn post
 *
 * @param {Object} data - Commenter request data
 * @param {string} data.postUrl - URL of the post
 * @param {string} data.csrfToken - CSRF token for LinkedIn API
 * @param {number} [data.start] - Starting index for commenters
 * @param {number} [data.count] - Number of commenters to fetch
 * @param {Function} sendResponse - Function to send a response
 */
async function handleGetCommenters(data, sendResponse) {
  logger.info(`Handling get commenters request - postUrl length: ${data.postUrl?.length || 0}, start: ${data.start || 0}, count: ${data.count || 10}`, 'content');
  
  try {
    const { postUrl, csrfToken, start = 0, count = 10 } = data;
    
    if (!postUrl) {
      throw new Error('Post URL is required');
    }
    
    if (!csrfToken) {
      throw new Error('CSRF token is required');
    }
    
    const commenters = await commentsUtils.fetchCommentersForPost(postUrl, csrfToken, start, count);
    
    logger.info(`Successfully fetched ${commenters.length} commenters`, 'content');
    sendResponse({
      success: true,
      data: { commenters }
    });
  } catch (error) {
    logger.error(`Error fetching commenters: ${error.message}`, 'content');
    sendResponse({
      success: false,
      error: `Error fetching commenters: ${error.message}`
    });
  }
}

/**
 * Handles requests to execute a specific function locally
 * @param {Object} data - Execution request data
 * @param {string} data.functionName - The name of the function to execute
 * @param {Object} data.params - Parameters to pass to the function
 * @param {Function} sendResponse - Callback to send the response
 */
async function handleExecuteFunction(data, sendResponse) {
    const logContext = 'content:handleExecuteFunction';
    const { functionName, params } = data;
    logger.info(`Attempting to execute local function: ${functionName}`, logContext);
    
    if (typeof localFunctions[functionName] === 'function') {
        try {
            // Execute the function with provided parameters
            // Assumes functions handle their own parameters appropriately
            const result = await localFunctions[functionName](params);
            logger.info(`Local function ${functionName} executed successfully.`, logContext);
            sendResponse({ success: true, data: result });
        } catch (error) {
             if (error instanceof Error) {
                logger.error(`Error executing local function ${functionName}: ${error.message}`, logContext, error);
                sendResponse({ success: false, error: error.message });
            } else {
                logger.error(`Unknown error executing local function ${functionName}: ${String(error)}`, logContext);
                sendResponse({ success: false, error: String(error) });
            }
        }
    } else {
        logger.warn(`Local function not found or not executable: ${functionName}`, logContext);
        sendResponse({ success: false, error: `Function ${functionName} not found or is not executable locally.` });
    }
}

// Initialize the content script
init(); 