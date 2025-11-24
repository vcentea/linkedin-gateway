//@ts-check
/// <reference types="chrome"/>

import { MESSAGE_TYPES } from '../../../shared/constants/message-types.js';
import { logger } from '../../../shared/utils/logger.js';
import { handleError, createError } from '../../../shared/utils/error-handler.js';
import { sendMessageToBackground } from '../../../background/services/messaging.service.js';
import appConfig from '../../../shared/config/app.config.js';

// Extract constants from app config
const MIN_CHECK_INTERVAL = appConfig.MIN_CHECK_INTERVAL || 60000; // Default 1 minute
const ACTIVE_CHECK_INTERVAL = appConfig.ACTIVE_CHECK_INTERVAL || 120000; // Default 2 minutes

/**
 * LinkedInStatus Component for displaying and controlling LinkedIn integration status
 */
export class LinkedInStatus {
    /**
     * @type {HTMLElement|null}
     */
    container = null;
    
    /**
     * @type {HTMLElement|null}
     */
    statusDisplay = null;
    
    /**
     * @type {HTMLButtonElement|null}
     */
    toggleButton = null;
    
    /**
     * @type {boolean}
     */
    isLinkedInEnabled = false;
    
    /**
     * @type {number}
     */
    lastCheckTime = 0;
    
    /**
     * @type {number|null}
     */
    statusCheckInterval = null;
    
    /**
     * Create a new LinkedInStatus component
     */
    constructor() {
        this.container = document.getElementById('linkedin-status-container');
        this.lastCheckTime = 0;
        this.statusCheckInterval = null;
        
        if (!this.container) {
            // If the container doesn't exist in the static HTML, log an error or handle appropriately.
            // Assuming the container is always present in dashboard/index.html based on the current structure.
            logger.error('LinkedIn status container not found in HTML', 'LinkedInStatus.constructor');
            return; // Stop initialization if the container is missing
        }
        
        // Get the specific elements within the container
        this.statusDisplay = document.getElementById('linkedin-status-message'); 
        this.toggleButton = /** @type {HTMLButtonElement|null} */ (document.getElementById('linkedin-connect-btn'));
        
        // Bind methods to maintain proper 'this' context
        this.checkLinkedInStatus = this.checkLinkedInStatus.bind(this);
        this.handleVisibilityChange = this.handleVisibilityChange.bind(this);
        
        // Initialize the component
        this.init();
    }
    
    /**
     * Initialize the component
     */
    async init() {
        try {
            logger.info('Initializing LinkedIn Status component', 'LinkedInStatus');

            // Check if required elements were found in the constructor
            if (!this.statusDisplay) {
                 throw createError('DomError', 'LinkedIn status display element not found', 'LinkedInStatus.init');
            }
            if (!this.toggleButton) {
                 throw createError('DomError', 'LinkedIn connect button not found', 'LinkedInStatus.init');
            }
            
            // Set up visibility change detection
            document.addEventListener('visibilitychange', this.handleVisibilityChange);
            
            // Check current status (force=true to bypass throttling)
            await this.checkLinkedInStatus(true);
            
            // Set up event listeners for button
            this.toggleButton.addEventListener('click', () => this.toggleLinkedInStatus());
            
            // Listen for status updates from background
            this.setupMessageListener();
            
            // Start periodic status checking if tab is visible
            if (document.visibilityState === 'visible') {
                this.startStatusChecking();
            }
            
            logger.info('LinkedIn Status component initialized', 'LinkedInStatus');
        } catch (error) {
            handleError(error, 'LinkedInStatus.init');
            this.showError('Failed to initialize LinkedIn status component');
        }
    }
    
    /**
     * Handle visibility change event
     */
    handleVisibilityChange() {
        logger.info(`Visibility changed: ${document.visibilityState}`, 'LinkedInStatus');
        
        if (document.visibilityState === 'visible') {
            // Always check when tab becomes visible (force refresh)
            logger.info('Tab became visible - checking LinkedIn status', 'LinkedInStatus');
            this.checkLinkedInStatus(true); // Force check (bypass throttling)
            
            // Also start the active polling
            this.startStatusChecking();
        } else {
            // Stop polling when tab is hidden
            this.stopStatusChecking();
        }
    }
    
    /**
     * Create the container for the LinkedIn status component
     */
    createContainer() {
        try {
            logger.info('Creating LinkedIn status container', 'LinkedInStatus');
            
            // Find a suitable location to inject the container
            const dashboard = document.getElementById('dashboard');
            
            if (!dashboard) {
                throw createError('DomError', 'Dashboard element not found', 'LinkedInStatus.createContainer');
            }
            
            // Create container element
            this.container = document.createElement('div');
            this.container.id = 'linkedin-status-container';
            this.container.className = 'dashboard-card';
            
            // Set container content
            this.container.innerHTML = `
                <h3>LinkedIn Integration</h3>
                <div class="card-content">
                    <p>Status: <span id="linkedin-status">Checking...</span></p>
                    <button id="linkedin-toggle" class="button primary">Enable LinkedIn Integration</button>
                    <p class="info-text">
                        LinkedIn integration allows this extension to access and analyze your LinkedIn feed.
                    </p>
                </div>
            `;
            
            // Add container to the dashboard
            dashboard.appendChild(this.container);
            
            logger.info('LinkedIn status container created and added to dashboard', 'LinkedInStatus');
        } catch (error) {
            handleError(error, 'LinkedInStatus.createContainer');
        }
    }
    
    /**
     * Set up message listener for LinkedIn status updates
     */
    setupMessageListener() {
        chrome.runtime.onMessage.addListener((message) => {
            try {
                if (message && message.type === MESSAGE_TYPES.LINKEDIN_STATUS_UPDATE) {
                    this.updateStatusDisplay(message.enabled);
                }
            } catch (error) {
                handleError(error, 'LinkedInStatus.setupMessageListener');
            }
        });
        
        logger.info('LinkedIn status message listener established', 'LinkedInStatus');
    }
    
    /**
     * Check the current LinkedIn integration status
     * @param {boolean} [force=false] - Whether to force a check regardless of throttling
     */
    async checkLinkedInStatus(force = false) {
        try {
            logger.info('Checking LinkedIn integration status', 'LinkedInStatus');
            
            const now = Date.now();
            
            // Skip check if too recent, unless forced
            if (!force && (now - this.lastCheckTime) < MIN_CHECK_INTERVAL) {
                logger.info(`Skipping LinkedIn check - last check was ${Math.round((now - this.lastCheckTime)/1000)}s ago`, 'LinkedInStatus');
                return;
            }
            
            // Update last check time
            this.lastCheckTime = now;
            
            if (!this.statusDisplay) {
                // This check might be redundant if init() already threw an error, but good for safety
                throw createError('DomError', 'LinkedIn status display element not found', 'LinkedInStatus.checkLinkedInStatus');
            }
            
            // Show checking status
            this.statusDisplay.textContent = 'Checking...';
            this.statusDisplay.className = 'status-checking'; // Consider adding styles for this class
            
            // Request status from background using messaging service
            const response = await sendMessageToBackground({ 
                type: MESSAGE_TYPES.GET_LINKEDIN_STATUS 
            });
            
            if (!response) {
                throw createError('ApiError', 'No response received from background service', 'LinkedInStatus.checkLinkedInStatus');
            }
            
            // Update status display based on response
            this.updateStatusDisplay(response.enabled);
            
            logger.info(`LinkedIn status checked: ${response.enabled ? 'Enabled' : 'Disabled'}`, 'LinkedInStatus');
        } catch (error) {
            handleError(error, 'LinkedInStatus.checkLinkedInStatus');
            // Update to disabled state on error
            this.updateStatusDisplay(false);
        }
    }
    
    /**
     * Start periodic status checking
     */
    startStatusChecking() {
        try {
            // Clear any existing interval first
            this.stopStatusChecking();
            
            // Only start if tab is visible
            if (document.visibilityState === 'visible') {
                logger.info('Starting periodic LinkedIn status checking', 'LinkedInStatus');
                
                // Create new interval
                this.statusCheckInterval = window.setInterval(() => {
                    logger.info('Periodic LinkedIn status check while tab active', 'LinkedInStatus');
                    this.checkLinkedInStatus();
                }, ACTIVE_CHECK_INTERVAL);
            }
        } catch (error) {
            handleError(error, 'LinkedInStatus.startStatusChecking');
        }
    }
    
    /**
     * Stop periodic status checking
     */
    stopStatusChecking() {
        try {
            if (this.statusCheckInterval) {
                logger.info('Stopping periodic LinkedIn status checking', 'LinkedInStatus');
                window.clearInterval(this.statusCheckInterval);
                this.statusCheckInterval = null;
            }
        } catch (error) {
            handleError(error, 'LinkedInStatus.stopStatusChecking');
        }
    }
    
    /**
     * Toggle LinkedIn integration status
     * Opens LinkedIn feed page in a new tab to allow user to connect
     */
    async toggleLinkedInStatus() {
        logger.info('LinkedIn connect button clicked - opening LinkedIn feed', 'LinkedInStatus');
        
        if (!this.toggleButton) {
            handleError(createError('DomError', 'LinkedIn connect button not found', 'LinkedInStatus.toggleLinkedInStatus'));
            return;
        }

        // Open LinkedIn feed page in a new tab
        chrome.tabs.create({ url: 'https://www.linkedin.com/feed/' });

        // Example of sending a message to background if needed
        // try {
        //     this.toggleButton.disabled = true;
        //     this.toggleButton.textContent = this.isLinkedInEnabled ? 'Disabling...' : 'Enabling...';
        //     const response = await sendMessageToBackground({
        //         type: this.isLinkedInEnabled ? MESSAGE_TYPES.DISABLE_LINKEDIN : MESSAGE_TYPES.ENABLE_LINKEDIN
        //     });
        //     this.updateStatusDisplay(response.enabled);
        // } catch (error) {
        //     handleError(error, 'LinkedInStatus.toggleLinkedInStatus');
        //     this.showError('Failed to toggle LinkedIn status');
        // } finally {
        //      if(this.toggleButton) this.toggleButton.disabled = false;
        // }
    }
    
    /**
     * Update the status display and button text based on LinkedIn integration status
     * @param {boolean} isEnabled - Whether LinkedIn integration is enabled
     */
    updateStatusDisplay(isEnabled) {
        this.isLinkedInEnabled = isEnabled;
        
        if (!this.statusDisplay || !this.toggleButton) {
            handleError(createError('DomError', 'Required UI elements not found', 'LinkedInStatus.updateStatusDisplay'));
            return;
        }
        
        if (isEnabled) {
            this.statusDisplay.textContent = 'Connected';
            this.statusDisplay.className = 'status-enabled';
            this.statusDisplay.style.color = '#10b981';
            this.statusDisplay.style.fontWeight = '600';
            this.toggleButton.style.display = 'none'; // Hide button when connected
        } else {
            this.statusDisplay.textContent = 'Not Connected';
            this.statusDisplay.className = 'status-disabled';
            this.statusDisplay.style.color = '#ef4444';
            this.statusDisplay.style.fontWeight = '600';
            this.toggleButton.textContent = 'Connect LinkedIn';
            this.toggleButton.style.display = 'inline-block';
            
            // Apply modern button styles
            this.toggleButton.style.backgroundColor = '#0077b5';
            this.toggleButton.style.color = 'white';
            this.toggleButton.style.border = 'none';
            this.toggleButton.style.padding = '10px 20px';
            this.toggleButton.style.borderRadius = '8px';
            this.toggleButton.style.cursor = 'pointer';
            this.toggleButton.style.fontWeight = '600';
            this.toggleButton.style.fontSize = '14px';
            this.toggleButton.style.transition = 'all 0.2s ease';
            
            // Add hover effects
            this.toggleButton.addEventListener('mouseover', () => {
                this.toggleButton.style.backgroundColor = '#006097';
                this.toggleButton.style.transform = 'translateY(-1px)';
                this.toggleButton.style.boxShadow = '0 4px 8px rgba(0,119,181,0.2)';
            });
            
            this.toggleButton.addEventListener('mouseout', () => {
                this.toggleButton.style.backgroundColor = '#0077b5';
                this.toggleButton.style.transform = 'translateY(0)';
                this.toggleButton.style.boxShadow = 'none';
            });
        }
    }
    
    /**
     * Show an error message
     * @param {string} message - Error message to display
     */
    showError(message) {
        logger.error(new Error(message), 'LinkedInStatus');
        
        try {
            // Create error element if it doesn't exist
            let errorElement = document.getElementById('linkedin-status-error');
            
            if (!errorElement && this.container) {
                errorElement = document.createElement('div');
                errorElement.id = 'linkedin-status-error';
                errorElement.className = 'error-message';
                this.container.appendChild(errorElement);
            }
            
            if (errorElement) {
                errorElement.textContent = `Error: ${message}`;
                errorElement.style.display = 'block';
            }
        } catch (error) {
            handleError(error, 'LinkedInStatus.showError');
        }
    }
} 