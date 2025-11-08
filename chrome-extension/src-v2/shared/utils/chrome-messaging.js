//@ts-nocheck
/**
 * Chrome Messaging Utilities for UI Pages
 * 
 * Provides utilities for communicating with the extension's background script
 * from UI pages (popup, dashboard, etc.).
 */

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
          console.error('Chrome runtime error:', chrome.runtime.lastError.message);
          reject(chrome.runtime.lastError);
        } else {
          resolve(response);
        }
      });
    } catch (error) {
      console.error('Error sending message to background:', error);
      reject(error);
    }
  });
} 