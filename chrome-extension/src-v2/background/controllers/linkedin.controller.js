//@ts-check
/// <reference types="chrome"/>

/**
 * LinkedIn Controller for handling LinkedIn-related operations
 * 
 * This controller interfaces between the messaging layer and LinkedIn functionality,
 * providing a clean API for LinkedIn operations like status checks and login.
 * 
 * @fileoverview LinkedIn controller for background service
 */

import { MESSAGE_TYPES } from '../../shared/constants/message-types.js';
import { logger } from '../../shared/utils/logger.js';
import { createError } from '../../shared/utils/error-handler.js'; // Import createError
import * as feedUtils from '../../content/linkedin/feed.js';
import * as commentsUtils from '../../content/linkedin/comments.js';
import * as postsUtils from '../../content/linkedin/posts.js';
import * as authService from '../services/auth.service.js';

// Use globalThis.chrome in service worker context
const chrome = globalThis.chrome;

// Map of local utility functions that can be executed directly in background
const localFunctions = {
  fetchPostsFromFeed: feedUtils.fetchPostsFromFeed,
  fetchCommentersForPost: commentsUtils.fetchCommentersForPost,
  fetchPostsForProfile: postsUtils.fetchPostsForProfile,
  parseLinkedInPostUrl: feedUtils.parseLinkedInPostUrl
  // Add other utility functions as needed
};

/**
 * Initializes the LinkedIn controller
 * Performs any necessary setup for LinkedIn handling
 */
export function init() {
  logger.info('Initializing LinkedIn Controller', 'linkedin.controller');
}

/**
 * Handles messages related to LinkedIn
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
    logger.error(createError('InvalidMessageFormat', 'Invalid message format received', 'linkedin.controller'));
    return false;
  }
  
  switch (message.type) {
    case MESSAGE_TYPES.CHECK_LINKEDIN_LOGGED_IN:
      handleCheckLinkedInStatus(sendResponse);
      return true;
      
    case MESSAGE_TYPES.OPEN_LINKEDIN:
      handleOpenLinkedIn(sendResponse);
      return true;
      
    case MESSAGE_TYPES.GET_CSRF_TOKEN:
      handleGetCsrfToken(sendResponse);
      return true;
      
    case MESSAGE_TYPES.GET_LINKEDIN_STATUS:
      handleGetLinkedInStatus(sendResponse);
      return true;
      
    case MESSAGE_TYPES.EXECUTE_FUNCTION:
      handleExecuteFunction(message.data, sendResponse);
      return true;
      
    default:
      return false; // Message not handled by this controller
  }
}

/**
 * Handles request to execute a LinkedIn function directly in background
 * 
 * @param {Object} data - Data for the function execution
 * @param {string} data.functionName - Name of the function to execute
 * @param {Object} data.params - Parameters for the function
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleExecuteFunction(data, sendResponse) {
  try {
    logger.info(`Handling execute function request: ${data?.functionName}`, 'linkedin.controller');
    
    if (!data || !data.functionName) {
      throw createError('MissingParameters', 'Missing required parameters: functionName', 'linkedin.controller.handleExecuteFunction');
    }
    
    const { functionName, params } = data;
    
    if (!localFunctions[functionName] || typeof localFunctions[functionName] !== 'function') {
      throw createError('FunctionNotFound', `Function '${functionName}' not found or not executable`, 'linkedin.controller.handleExecuteFunction');
    }
    
    // For functions that need CSRF token but don't have it in params
    if ((functionName === 'fetchPostsFromFeed' || functionName === 'fetchCommentersForPost' || functionName === 'fetchPostsForProfile') && 
        (!params || !params.csrfToken)) {
      logger.info('Getting CSRF token for function execution', 'linkedin.controller');
      try {
        const csrfToken = await getCsrfToken();
        
        // Add CSRF token to params if it's not already there
        const paramsWithToken = { ...params, csrfToken };
        
        // Execute the function with unpacked parameters based on function signature
        let result;
        if (functionName === 'fetchPostsFromFeed') {
          // fetchPostsFromFeed(startIndex, count, csrfToken)
          // Handle both snake_case (from API) and camelCase (from direct calls)
          result = await localFunctions[functionName](
            paramsWithToken.startIndex || paramsWithToken.start_index,
            paramsWithToken.count,
            paramsWithToken.csrfToken
          );
        } else if (functionName === 'fetchCommentersForPost') {
          // fetchCommentersForPost(postUrl, csrfToken, start, count, numReplies)
          // Handle both snake_case (from API) and camelCase (from direct calls)
          result = await localFunctions[functionName](
            paramsWithToken.postUrl || paramsWithToken.post_url,
            paramsWithToken.csrfToken,
            paramsWithToken.start || 0,
            paramsWithToken.count || 10,
            paramsWithToken.numReplies || paramsWithToken.num_replies || 1
          );
        } else if (functionName === 'fetchPostsForProfile') {
          // fetchPostsForProfile(profileId, start, count, csrfToken)
          result = await localFunctions[functionName](
            paramsWithToken.profileID || paramsWithToken.profile_id,
            paramsWithToken.start || 0,
            paramsWithToken.count || 10,
            paramsWithToken.csrfToken
          );
        }
        sendResponse({ success: true, data: result });
      } catch (tokenError) {
        const err = tokenError instanceof Error ? tokenError : createError('CsrfTokenError', String(tokenError), 'linkedin.controller.handleExecuteFunction');
        logger.error(err, 'linkedin.controller');
        sendResponse({ success: false, error: `Failed to get CSRF token: ${err.message}` });
      }
    } else {
      // Execute the function directly with provided params
      // Unpack parameters for LinkedIn functions
      let result;
      if (functionName === 'fetchPostsFromFeed') {
        // Handle both snake_case (from API) and camelCase (from direct calls)
        result = await localFunctions[functionName](
          params.startIndex || params.start_index,
          params.count,
          params.csrfToken
        );
      } else if (functionName === 'fetchCommentersForPost') {
        // Handle both snake_case (from API) and camelCase (from direct calls)
        result = await localFunctions[functionName](
          params.postUrl || params.post_url,
          params.csrfToken,
          params.start || 0,
          params.count || 10,
          params.numReplies || params.num_replies || 1
        );
      } else if (functionName === 'fetchPostsForProfile') {
        // fetchPostsForProfile(profileId, start, count, csrfToken)
        result = await localFunctions[functionName](
          params.profileID || params.profile_id,
          params.start || 0,
          params.count || 10,
          params.csrfToken
        );
      } else {
        // For other functions, pass params object as-is
        result = await localFunctions[functionName](params);
      }
      sendResponse({ success: true, data: result });
    }
  } catch (error) {
    const err = error instanceof Error ? error : createError('ExecutionError', String(error), 'linkedin.controller.handleExecuteFunction');
    logger.error(err, 'linkedin.controller');
    sendResponse({ success: false, error: err.message });
  }
}

/**
 * Handles LinkedIn status check request
 * Checks if user is logged into LinkedIn
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleCheckLinkedInStatus(sendResponse) {
  try {
    const result = await checkLinkedInStatus();
    sendResponse(result);
  } catch (error) {
    const err = error instanceof Error ? error : createError('StatusCheckError', String(error), 'linkedin.controller.handleCheckLinkedInStatus');
    logger.error(err, 'linkedin.controller');
    sendResponse({ connected: false, error: err.message });
  }
}

/**
 * Handles request to open LinkedIn in a new tab
 * Useful for prompting users to log in
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleOpenLinkedIn(sendResponse) {
  try {
    const result = await openLinkedInTab();
    sendResponse(result);
  } catch (error) {
    const err = error instanceof Error ? error : createError('OpenTabError', String(error), 'linkedin.controller.handleOpenLinkedIn');
    logger.error(err, 'linkedin.controller');
    sendResponse({ success: false, error: err.message });
  }
}

/**
 * Handles request to get LinkedIn CSRF token
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleGetCsrfToken(sendResponse) {
  try {
    const token = await getCsrfToken();
    sendResponse({ success: true, token });
  } catch (error) {
    const err = error instanceof Error ? error : createError('CsrfTokenError', String(error), 'linkedin.controller.handleGetCsrfToken');
    logger.error(err, 'linkedin.controller');
    sendResponse({ success: false, error: err.message });
  }
}

/**
 * Get All LinkedIn Cookies
 * Retrieves ALL cookies from LinkedIn domain for server-side authentication.
 * 
 * @returns {Promise<Object>} Object containing all LinkedIn cookies {name: value}
 */
export async function getAllLinkedInCookies() {
  logger.info('Getting all LinkedIn cookies...', 'linkedin.controller');
  return new Promise((resolve) => {
    if (!chrome || !chrome.cookies) {
      logger.warn('chrome.cookies API not available', 'linkedin.controller.getAllLinkedInCookies');
      resolve({});
      return;
    }
    chrome.cookies.getAll({ domain: '.linkedin.com' }, (cookies) => {
      const cookieObj = {};
      if (cookies && Array.isArray(cookies)) {
        cookies.forEach(cookie => {
          // Strip quotes from cookie values like we do for CSRF token
          let value = cookie.value;
          if (value.startsWith('"') && value.endsWith('"')) {
            value = value.slice(1, -1);
          }
          cookieObj[cookie.name] = value;
        });
        logger.info(`Retrieved ${Object.keys(cookieObj).length} LinkedIn cookies`, 'linkedin.controller.getAllLinkedInCookies');
      }
      resolve(cookieObj);
    });
  });
}

/**
 * Retrieves LinkedIn CSRF token from JSESSIONID cookie
 * Required for authenticated API requests to LinkedIn
 * 
 * @returns {Promise<string>} The CSRF token
 * @throws {Error} Error message if CSRF token cannot be retrieved
 */
export async function getCsrfToken() {
  logger.info('Getting LinkedIn CSRF token...', 'linkedin.controller');
  return new Promise((resolve, reject) => {
    if (!chrome || !chrome.cookies) {
        return reject(createError('ChromeApiError', 'chrome.cookies API not available', 'linkedin.controller.getCsrfToken'));
    }
    chrome.cookies.get({ url: 'https://www.linkedin.com', name: 'JSESSIONID' }, cookie => {
      if (chrome.runtime.lastError) {
        return reject(createError('ChromeApiError', `Error getting cookie: ${chrome.runtime.lastError.message}`, 'linkedin.controller.getCsrfToken'));
      }
      if (cookie && cookie.value) {
        // The CSRF token is the value within the quotes
        const csrfToken = cookie.value.replace(/^"|"$/g, '');
        logger.info('CSRF token retrieved successfully', 'linkedin.controller');
        resolve(csrfToken);
      } else {
        logger.error(createError('CsrfTokenNotFound', 'CSRF token (JSESSIONID cookie) not found - user likely not logged in to LinkedIn', 'linkedin.controller.getCsrfToken'));
        reject(createError('CsrfTokenNotFound', 'CSRF token not found', 'linkedin.controller.getCsrfToken'));
      }
    });
  });
}

/**
 * Creates a random delay between operations
 * Helps prevent rate limiting and simulates natural user behavior
 * 
 * @param {number} min - Minimum delay in milliseconds
 * @param {number} max - Maximum delay in milliseconds
 * @returns {Promise<void>} Promise that resolves after the delay
 */
function randomDelay(min, max) {
  const delay = Math.random() * (max - min) + min;
  return new Promise(resolve => setTimeout(resolve, delay));
}

/**
 * Checks if the user is logged into LinkedIn using Voyager API
 * More reliable than cookie-only checks
 * Also updates the CSRF token in the backend if user has an API key
 * 
 * @returns {Promise<Object>} Object containing connection status and any error details
 */
export async function checkLinkedInStatus() {
  logger.info('Checking LinkedIn connection status using Voyager API...', 'linkedin.controller');
  const url = 'https://www.linkedin.com/voyager/api/voyagerNotificationsDashPill?decorationId=com.linkedin.voyager.dash.deco.notifications.FullNotificationPillsCollection-4&q=filterVanityName';
  let csrfToken = '';

  try {
    csrfToken = await getCsrfToken();
  } catch (error) {
    logger.error(`Error getting CSRF token: ${error}`, 'linkedin.controller');
    // If we can't get CSRF, they are likely not logged in
    return { connected: false, error: error };
  }

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'csrf-token': csrfToken,
        "accept": "application/vnd.linkedin.normalized+json+2.1",
        'X-RestLi-Protocol-Version': '2.0.0',
        // We don't explicitly set the cookie header, `credentials: 'include'` handles it
      },
      credentials: 'include' // Important: Send cookies with the request
    });

    if (!response.ok) {
      logger.info(`LinkedIn connection check response: NOT LOGGED IN (Status: ${response.status})`, 'linkedin.controller');
      // Consider specific statuses like 401 Unauthorized as definitive not logged in
      return { connected: false, status: response.status };
    }

    // We don't need to parse the data, a 200 OK is enough
    logger.info('LinkedIn connection check response: OK (Status: 200)', 'linkedin.controller');
    
    // Update CSRF token and all cookies in backend if user has an API key
    // Use static import to avoid dynamic import issues in Service Worker
    authService.getApiKey().then(apiKeyResult => {
      if (apiKeyResult.success && apiKeyResult.keyExists) {
        logger.info('API key exists, updating CSRF token and LinkedIn cookies in backend', 'linkedin.controller');
        
        // Update CSRF token
        authService.updateCsrfToken(csrfToken).then(updateResult => {
          if (updateResult.success) {
            logger.info('CSRF token updated successfully in backend', 'linkedin.controller');
          } else {
            logger.warn(`Failed to update CSRF token in backend: ${updateResult.error}`, 'linkedin.controller');
          }
        }).catch(err => {
          logger.error(`Error updating CSRF token: ${err.message}`, 'linkedin.controller');
        });
        
        // Update all LinkedIn cookies
        getAllLinkedInCookies().then(cookies => {
          authService.updateLinkedInCookies(cookies).then(updateResult => {
            if (updateResult.success) {
              logger.info(`LinkedIn cookies updated successfully in backend (${Object.keys(cookies).length} cookies)`, 'linkedin.controller');
            } else {
              logger.warn(`Failed to update LinkedIn cookies in backend: ${updateResult.error}`, 'linkedin.controller');
            }
          }).catch(err => {
            logger.error(`Error updating LinkedIn cookies: ${err.message}`, 'linkedin.controller');
          });
        }).catch(err => {
          logger.error(`Error retrieving LinkedIn cookies: ${err.message}`, 'linkedin.controller');
        });
      } else {
        logger.info('No API key found, skipping CSRF token and cookies update', 'linkedin.controller');
      }
    }).catch(err => {
      logger.error(`Error checking for API key: ${err.message}`, 'linkedin.controller');
    });
    
    return { connected: true };
    
  } catch (error) {
    logger.error(`LinkedIn connection check using API failed: ${error.message}`, 'linkedin.controller');
    // Optional: Implement a simpler fallback check here if needed
    // await randomDelay(1000, 3000); // Optional delay on error
    return { connected: false, error: error.message };
  }
}

/**
 * Opens LinkedIn in a new browser tab
 * Useful for prompting users to log in
 * 
 * @returns {Promise<Object>} Object containing success status, tab ID, and any error details
 */
export async function openLinkedInTab() {
  logger.info('Opening LinkedIn login page', 'linkedin.controller');
  
  try {
    const linkedInUrl = "https://www.linkedin.com/";
    const tab = await chrome.tabs.create({ url: linkedInUrl });
    return { success: true, tabId: tab.id };
  } catch (error) {
    logger.error(`Error opening LinkedIn tab: ${error.message}`, 'linkedin.controller');
    return { success: false, error: error.message };
  }
}

/**
 * Handles LinkedIn status request for the dashboard
 * Checks LinkedIn integration status and returns enabled/disabled state
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleGetLinkedInStatus(sendResponse) {
  try {
    logger.info('Handling GET_LINKEDIN_STATUS request', 'linkedin.controller');
    const result = await checkLinkedInStatus();
    
    // For dashboard display, we just need a simple enabled/disabled status
    sendResponse({ 
      enabled: result.connected,
      timestamp: Date.now()
    });
  } catch (error) {
    logger.error(`Error getting LinkedIn status: ${error.message}`, 'linkedin.controller');
    sendResponse({ 
      enabled: false, 
      error: error.message,
      timestamp: Date.now()
    });
  }
} 