/**
 * @fileoverview Template for Chrome API type references
 * This file provides a template for adding Chrome API type references to JavaScript files.
 * Copy and adapt the relevant sections at the top of files using Chrome APIs.
 */

// Add this to the top of your file for Chrome API type checking
// =============================================================

/**
 * @fileoverview [Your file description here]
 * 
 * @typedef {import('../../shared/types/chrome.types').ChromeRuntime} ChromeRuntime
 * @typedef {import('../../shared/types/chrome.types').ChromeStorage} ChromeStorage
 * @typedef {import('../../shared/types/chrome.types').ChromeAction} ChromeAction
 * @typedef {import('../../shared/types/chrome.types').ChromeTabs} ChromeTabs
 * @typedef {import('../../shared/types/chrome.types').ChromeCookies} ChromeCookies
 * @typedef {import('../../shared/types/chrome.types').Tab} Tab
 * @typedef {import('../../shared/types/chrome.types').MessageSender} MessageSender
 */

// Note: You don't need to import all of these - just the ones you're using
// Adjust the import path based on your file's location
// For example, from background files: '../shared/types/chrome.types'
// From components: '../../shared/types/chrome.types'

// Then add this JSDoc annotation to use Chrome APIs with type checking:

/**
 * Chrome API namespace
 * @type {{
 *   runtime: ChromeRuntime,
 *   storage: ChromeStorage,
 *   action: ChromeAction,
 *   tabs: ChromeTabs,
 *   cookies: ChromeCookies
 * }}
 */
const chrome = window.chrome;

// In real code, you don't need to create the chrome const as it's global 
// This is just for type checking. Just add the JSDoc annotation before
// your first chrome API use.

// Example of use:
// =============================================================

/**
 * Sets the extension badge text and color.
 * @param {string} text - Text to display on the badge
 * @param {string} color - Badge color (e.g., '#FF0000')
 */
function setBadge(text, color) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
}

/**
 * Creates a new tab with the specified URL.
 * @param {string} url - URL to open
 * @returns {Promise<Tab>} - Promise resolving to the created tab
 */
async function createTab(url) {
  return chrome.tabs.create({ url });
}

/**
 * Gets the value of a storage item.
 * @param {string} key - Storage key to retrieve
 * @returns {Promise<any>} - Promise resolving to the storage value
 */
async function getStorageItem(key) {
  const result = await chrome.storage.local.get([key]);
  return result[key];
}

/**
 * Sends a message to the background script.
 * @param {Object} message - Message to send
 * @returns {Promise<any>} - Promise resolving to the response
 */
async function sendMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
} 