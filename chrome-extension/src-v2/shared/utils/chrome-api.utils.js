//@ts-check
/// <reference types="chrome" />

/**
 * @fileoverview Chrome API utilities - Helper functions for Chrome APIs
 * 
 * This file provides typed wrapper functions for common Chrome API operations,
 * ensuring consistent error handling and type safety across the codebase.
 */

import { logger } from './logger.js';

/**
 * Opens a new tab with the specified URL
 * @param {string} url - URL to open
 * @returns {Promise<chrome.tabs.Tab>} - Promise resolving to the created tab
 */
export function createTab(url) {
  return new Promise((resolve, reject) => {
    try {
      chrome.tabs.create({ url }, (tab) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(tab);
        }
      });
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Sets the badge text for the extension icon
 * @param {string} text - Text to display on the badge
 */
export function setBadgeText(text) {
  try {
    chrome.action.setBadgeText({ text });
  } catch (error) {
    logger.error(`Error setting badge text: ${error instanceof Error ? error.message : String(error)}`, 'chrome-api.utils');
  }
}

/**
 * Sets the badge background color for the extension icon
 * @param {string} color - Color in CSS format (e.g., '#FF0000')
 */
export function setBadgeBackgroundColor(color) {
  try {
    chrome.action.setBadgeBackgroundColor({ color });
  } catch (error) {
    logger.error(`Error setting badge color: ${error instanceof Error ? error.message : String(error)}`, 'chrome-api.utils');
  }
}

/**
 * Sends a message to a specific tab
 * @param {number} tabId - ID of the tab to send the message to
 * @param {any} message - Message to send
 * @returns {Promise<any>} - Promise resolving with the response
 */
export function sendMessageToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    try {
      chrome.tabs.sendMessage(tabId, message, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Sends a message to the background script
 * @param {any} message - Message to send
 * @returns {Promise<any>} - Promise resolving with the response
 */
export function sendMessageToBackground(message) {
  return new Promise((resolve, reject) => {
    try {
      chrome.runtime.sendMessage(message, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Adds a listener for extension icon clicks
 * @param {function(): void} callback - Function to call when the icon is clicked
 */
export function addActionClickListener(callback) {
  try {
    chrome.action.onClicked.addListener(callback);
  } catch (error) {
    logger.error(`Error adding action click listener: ${error instanceof Error ? error.message : String(error)}`, 'chrome-api.utils');
  }
}

/**
 * Gets the extension's URL for a resource
 * @param {string} path - Path to the resource
 * @returns {string} - Full URL to the resource
 */
export function getExtensionUrl(path) {
  return chrome.runtime.getURL(path);
} 