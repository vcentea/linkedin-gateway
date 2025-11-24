//@ts-check
/// <reference types="chrome"/>

import { logger } from '../../shared/utils/logger.js';
import { handleError } from '../../shared/utils/error-handler.js';

/**
 * Auth helper functions for token management and validation
 * This file consolidates authentication utilities from the original utils/auth.js
 * 
 * @fileoverview Helpers for authenticating with the backend API
 * @typedef {Object} Chrome
 * @property {Object} storage - The Chrome storage API
 * @property {Object} storage.local - The local storage area
 * @property {Function} storage.local.get - Gets items from local storage
 */

/**
 * Retrieves the access token from chrome.storage.local
 * Returns the token if it exists (backend validates expiration)
 *
 * @returns {Promise<string|null>} The access token if it exists, null otherwise
 */
export async function getAccessToken() {
  try {
    // Get the token from chrome.storage.local
    const storage = await new Promise((resolve) => {
      chrome.storage.local.get(['access_token'], (result) => {
        console.log('Retrieved from storage:', result);
        resolve(result);
      });
    });

    if (!storage || !storage.access_token) {
      logger.error('No access token found in storage', undefined, 'auth.helpers');
      return null;
    }

    const tokenPreview = storage.access_token.substring(0, 20) + '...';
    console.log('Access token found:', tokenPreview);

    // Display token for debugging
    console.log('Full token for debugging:', storage.access_token);

    return storage.access_token;
  } catch (error) {
    console.error('Error getting access token:', error);
    return null;
  }
}

/**
 * Checks if a token is expired based on its expiration timestamp
 * 
 * @param {string|number|Date} expiresAt - Token expiration date/time
 * @returns {boolean} True if token is expired, false otherwise
 */
export function isTokenExpired(expiresAt) {
  if (!expiresAt) return true;
  return new Date(expiresAt) <= new Date();
}

/**
 * Creates a preview of a token (first few characters with ellipsis)
 * Useful for logging without exposing the full token
 * 
 * @param {string} token - The token to preview
 * @param {number} [previewLength=20] - Number of characters to show in preview 
 * @returns {string} The token preview
 */
export function createTokenPreview(token, previewLength = 20) {
  if (!token) return 'no-token';
  return token.substring(0, previewLength) + '...';
} 