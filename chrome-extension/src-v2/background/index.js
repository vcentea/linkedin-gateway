// VERY TOP LEVEL LOG
console.log('LinkedIn Gateway: background/index.js script started loading.');

// @ts-nocheck
/// <reference types="chrome"/>

/**
 * Background Service Worker Entry Point
 * 
 * This is the main entry point for the extension's background service worker.
 * It initializes controllers, sets up message listeners, and handles the extension icon click.
 * 
 * @fileoverview Background service worker initialization and message routing
 */

// Import Chrome API types from type-only import
/// <reference path="../shared/types/chrome.types.js" />

// Restore all imports
import { logger } from '../shared/utils/logger.js';
import * as authController from './controllers/auth.controller.js';
import * as websocketController from './controllers/websocket.controller.js';
import * as linkedinController from './controllers/linkedin.controller.js';
import * as apiController from './controllers/api.controller.js';
import * as messagingService from './services/messaging.service.js';
import { initializeInstance } from './services/instance.service.js'; // Multi-key support (v1.1.0)


// Restore code AND logger.* calls
// Use globalThis.chrome in service worker context instead of window.chrome
const chrome = globalThis.chrome;

// Debug: verify chrome.action availability
if (!chrome || !chrome.action) {
  logger.error('[background] chrome.action API is not available in background script', undefined, 'background');
}

// Initialize the background service worker
function init() {
  logger.info('[background] Background service worker initializing', 'background');
  logger.info(`[background] chrome.action available: ${!!(chrome && chrome.action)}`, 'background');
  
  // Initialize messaging service first
  messagingService.init();
  
  // Initialize controllers
  authController.init();
  websocketController.init();
  linkedinController.init();
  apiController.init();
  
  // Register controllers with messaging service
  messagingService.registerMessageHandler(authController);
  messagingService.registerMessageHandler(websocketController);
  messagingService.registerMessageHandler(linkedinController);
  messagingService.registerMessageHandler(apiController);
  
  // Debug: registering extension icon click listener
  logger.info('[background] Registering extension icon click listener', 'background');
  chrome.action.onClicked.addListener(handleExtensionClick);
  
  // Set badge color - DIRECT CHROME API USAGE
  chrome.action.setBadgeBackgroundColor({ color: '#0077b5' }); // LinkedIn blue
  
  // Check authentication initially and set badge
  checkInitialAuthAndSetBadge();
  
  logger.info('[background] Background service worker initialized', 'background');
}

/**
 * Handle click on extension icon
 * Opens the dashboard page in a new tab
 * @param {chrome.tabs.Tab} tab - The active tab when the icon is clicked
 * @returns {void}
 */
function handleExtensionClick(tab) {
  logger.info('[background] handleExtensionClick invoked - opening dashboard', 'background');
  logger.info(`[background] handleExtensionClick tab argument: ${JSON.stringify(tab)}`, 'background');
  // DIRECT CHROME API USAGE
  try {
    const dashboardUrl = chrome.runtime.getURL('dashboard/index.html');
    chrome.tabs.create({ url: dashboardUrl });
  } catch (error) {
    // Pass error object to logger
    logger.error(`[background] Error opening dashboard`, error, 'background');
  }
}

/**
 * Check initial authentication and set badge accordingly
 * @returns {Promise<void>} */
async function checkInitialAuthAndSetBadge() {
  try {
    const isAuthenticated = await authController.isAuthenticated();
    // DIRECT CHROME API USAGE
    chrome.action.setBadgeText({ text: isAuthenticated ? '✓' : '' });
    logger.info(`[background] Initial auth check: ${isAuthenticated ? 'Authenticated' : 'Not authenticated'}`, 'background');
  } catch (error) {
    // Pass error object to logger
    logger.error(`[background] Error in initial auth check`, error, 'background');
    // DIRECT CHROME API USAGE
    chrome.action.setBadgeText({ text: '' });
  }
}

// =============================================================================
// Extension Lifecycle Hooks (v1.1.0 - Multi-key Support)
// =============================================================================

/**
 * Handle extension install or update
 * Initializes instance tracking for multi-key support
 */
chrome.runtime.onInstalled.addListener(async (details) => {
  logger.info(`[background] Extension ${details.reason}`, 'background');
  
  try {
    if (details.reason === 'install') {
      logger.info('[background] First install - initializing instance tracking', 'background');
      await initializeInstance();
      logger.info('[background] Instance tracking initialized successfully', 'background');
    } else if (details.reason === 'update') {
      logger.info(`[background] Updated from ${details.previousVersion} - verifying instance tracking`, 'background');
      await initializeInstance(); // Ensures instance exists and updates browser info
      logger.info('[background] Instance tracking verified successfully', 'background');
    }
  } catch (error) {
    logger.error('[background] Failed to initialize instance tracking', error, 'background');
    // Don't block extension initialization on instance tracking failure
  }
});

/**
 * Handle browser startup
 * Verifies instance data integrity on each browser start
 */
chrome.runtime.onStartup.addListener(async () => {
  logger.info('[background] Browser started - verifying instance tracking', 'background');
  
  try {
    await initializeInstance();
    logger.info('[background] Instance tracking verified on startup', 'background');
  } catch (error) {
    logger.error('[background] Failed to verify instance tracking on startup', error, 'background');
    // Don't block extension initialization on instance tracking failure
  }
});

// =============================================================================
// Initialize the background service worker
// =============================================================================
init();

