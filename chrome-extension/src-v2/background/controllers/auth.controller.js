//@ts-check
/// <reference types="chrome"/>

/**
 * Auth Controller for handling authentication-related operations
 * 
 * This controller interfaces between the messaging layer and the auth service,
 * providing a clean API for auth operations like profile checks, logout, and API key management.
 * 
 * @fileoverview Authentication controller for background service
 */

import { MESSAGE_TYPES } from '../../shared/constants/message-types.js';
import { logger } from '../../shared/utils/logger.js';
import * as authService from '../services/auth.service.js';

/**
 * Initializes the auth controller
 * Performs any necessary setup for authentication handling
 */
export function init() {
  logger.info('Initializing Auth Controller', 'auth.controller');
}

/**
 * Handles messages related to authentication
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
    logger.error('Invalid message format received', 'auth.controller');
    return false;
  }
  
  switch (message.type) {
    case MESSAGE_TYPES.GET_USER_PROFILE:
      handleGetUserProfile(sendResponse);
      return true;
      
    case MESSAGE_TYPES.LOGOUT_USER:
      handleLogout(sendResponse);
      return true;
      
    case MESSAGE_TYPES.GET_API_KEY:
      handleGetApiKey(sendResponse);
      return true;
      
    case MESSAGE_TYPES.GENERATE_API_KEY:
      handleGenerateApiKey(sendResponse);
      return true;
      
    case MESSAGE_TYPES.DELETE_API_KEY:
      handleDeleteApiKey(sendResponse);
      return true;
      
    default:
      return false; // Message not handled by this controller
  }
}

/**
 * Handles special auth_session message from login page
 * This is a special case outside the normal message types
 * 
 * @param {Object} userData - The user data from login
 * @param {Function} sendResponse - Function to send response back to the caller
 */
export async function handleAuthSession(userData, sendResponse) {
  try {
    const result = await authService.saveAuthSession(userData);
    sendResponse(result);
  } catch (error) {
    logger.error(`Error handling auth session: ${error.message}`, 'auth.controller');
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Handle user profile request
 * Checks if user is authenticated and returns profile data
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleGetUserProfile(sendResponse) {
  try {
    const result = await authService.checkAuthAndGetProfile();
    sendResponse(result);
  } catch (error) {
    logger.error(`Error getting user profile: ${error.message}`, 'auth.controller');
    sendResponse({ authenticated: false, error: error.message });
  }
}

/**
 * Handle logout request
 * Logs user out from the backend and clears local data
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleLogout(sendResponse) {
  try {
    const result = await authService.performLogout();
    sendResponse(result);
  } catch (error) {
    logger.error(`Error during logout: ${error.message}`, 'auth.controller');
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Handle get API key request
 * Retrieves user's API key from the backend
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleGetApiKey(sendResponse) {
  try {
    const result = await authService.getApiKey();
    sendResponse(result);
  } catch (error) {
    logger.error(`Error getting API key: ${error.message}`, 'auth.controller');
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Handle generate API key request
 * Creates a new API key for the user
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleGenerateApiKey(sendResponse) {
  try {
    const result = await authService.generateApiKey();
    sendResponse(result);
  } catch (error) {
    logger.error(`Error generating API key: ${error.message}`, 'auth.controller');
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Handle delete API key request
 * Deletes the user's API key
 * 
 * @param {Function} sendResponse - Function to send response back to the caller
 */
async function handleDeleteApiKey(sendResponse) {
  try {
    const result = await authService.deleteApiKey();
    sendResponse(result);
  } catch (error) {
    logger.error(`Error deleting API key: ${error.message}`, 'auth.controller');
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Check if user is authenticated (cached check)
 * Useful for quick checks without fetching profile
 * 
 * @returns {Promise<boolean>} True if authenticated with valid token
 */
export async function isAuthenticated() {
  return await authService.hasValidToken();
} 