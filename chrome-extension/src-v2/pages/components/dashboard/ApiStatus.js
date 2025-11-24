//@ts-check
/// <reference types="chrome"/>

import { MESSAGE_TYPES } from '../../../shared/constants/message-types.js';
import { logger } from '../../../shared/utils/logger.js';
import { handleError, createError } from '../../../shared/utils/error-handler.js';
import { sendMessageToBackground } from '../../../background/services/messaging.service.js';
import appConfig from '../../../shared/config/app.config.js';

// Extract constants from app config 
const MIN_CHECK_INTERVAL = appConfig.MIN_CHECK_INTERVAL || 5000; // Default 5 seconds for minimum interval
const ACTIVE_CHECK_INTERVAL = appConfig.ACTIVE_CHECK_INTERVAL || 15000; // Default 15 seconds for active checking

/**
 * ApiStatus Component for displaying the WebSocket connection status
 */
export class ApiStatus {
    /** 
     * @type {HTMLElement|null} 
     */
    statusElement = null;
    
    /** 
     * @type {number|null} 
     */
    statusCheckInterval = null;
    
    /**
     * @type {number}
     */
    lastCheckTime = 0;
    
    /**
     * Create a new ApiStatus component
     */
    constructor() {
        // Status element
        this.statusElement = /** @type {HTMLElement|null} */ (document.getElementById('api-availability-status'));
        
        // Status check interval
        this.statusCheckInterval = null;
        
        // Last check timestamp
        this.lastCheckTime = 0;
        
        // Bind methods to maintain proper 'this' context
        this.handleStatusUpdate = this.handleStatusUpdate.bind(this);
        this.checkStatus = this.checkStatus.bind(this);
        this.handleVisibilityChange = this.handleVisibilityChange.bind(this);
        
        // Initialize the component
        this.init();
    }
    
    /**
     * Initialize the component - set up listeners and start status checking
     */
    init() {
        try {
            logger.info('Initializing API Status component', 'ApiStatus');
        
            // Set up message listener for status updates from background
            this.setupMessageListener();
            
            // Set up visibility change listener
            document.addEventListener('visibilitychange', this.handleVisibilityChange);
            
            // Check status immediately
            this.checkStatus(true);
            
            // Set up periodic status checking if tab is visible
            if (document.visibilityState === 'visible') {
                this.startStatusChecking();
            }
            
            logger.info('API Status component initialized', 'ApiStatus');
        } catch (error) {
            handleError(error, 'ApiStatus.init');
        }
    }
    
    /**
     * Handle visibility change event
     */
    handleVisibilityChange() {
        try {
            logger.info(`Visibility changed: ${document.visibilityState}`, 'ApiStatus');
            
            if (document.visibilityState === 'visible') {
                // Check status immediately when tab becomes visible
                logger.info('Tab became visible - checking API status', 'ApiStatus');
                this.checkStatus(true); // Force check (bypass throttling)
                
                // Start the active polling
                this.startStatusChecking();
            } else {
                // Stop polling when tab is hidden
                this.stopStatusChecking();
            }
        } catch (error) {
            handleError(error, 'ApiStatus.handleVisibilityChange');
        }
    }
    
    /**
     * Set up listener for WebSocket status messages from background
     */
    setupMessageListener() {
        chrome.runtime.onMessage.addListener((message) => {
            try {
                if (message && message.type === MESSAGE_TYPES.WEBSOCKET_STATUS_UPDATE) {
                this.updateStatusDisplay(message.status);
            }
            } catch (error) {
                handleError(error, 'ApiStatus.setupMessageListener');
            }
        });
        
        logger.info('WebSocket status message listener established', 'ApiStatus');
    }
    
    /**
     * Check WebSocket status by sending a message to the background script
     * @param {boolean} [force=false] - Whether to force a check regardless of throttling
     */
    async checkStatus(force = false) {
        try {
            const now = Date.now();
            
            // Skip check if too recent, unless forced
            if (!force && (now - this.lastCheckTime) < MIN_CHECK_INTERVAL) {
                logger.info(`Skipping API status check - last check was ${Math.round((now - this.lastCheckTime)/1000)}s ago`, 'ApiStatus');
                return;
            }
            
            // Update last check time
            this.lastCheckTime = now;
            
            if (!this.statusElement) {
                throw createError('DomError', 'Status element not found', 'ApiStatus.checkStatus');
            }
            
            // Show checking status
            this.statusElement.textContent = 'Checking...';
            this.statusElement.className = 'status-checking';
            
            // Use a timeout to prevent indefinite hanging if backend is down
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('Status check timeout')), 3000);
            });
            
            // Request status from background using messaging service
            const response = await Promise.race([
                sendMessageToBackground({ type: MESSAGE_TYPES.GET_WEBSOCKET_STATUS }),
                timeoutPromise
            ]);
            
            this.handleStatusUpdate(response);
            
            logger.info('API status check completed', 'ApiStatus');
        } catch (error) {
            handleError(error, 'ApiStatus.checkStatus');
            // Update display to disconnected state on error or timeout
            this.updateStatusDisplay(false);
        }
    }
    
    /**
     * Handle status check response from the background script or broadcast updates
     * @param {any} responseOrStatus - The response object ({success, status}) or a direct boolean status
     */
    handleStatusUpdate(responseOrStatus) {
        try {
            logger.info(`ApiStatus received update: ${JSON.stringify(responseOrStatus)}`, 'ApiStatus');
            
            let isConnected = false;
            
            // Check if it's the response object from GET_WEBSOCKET_STATUS with new format {success:true, status:boolean}
            if (responseOrStatus && typeof responseOrStatus === 'object' && responseOrStatus.hasOwnProperty('success') && responseOrStatus.hasOwnProperty('status')) {
                if (responseOrStatus.success && typeof responseOrStatus.status === 'boolean') {
                    isConnected = responseOrStatus.status;
                    logger.info(`ApiStatus parsed response object with success/status: ${isConnected}`, 'ApiStatus');
                } else {
                    // Handle error case within the response object if needed, otherwise defaults to false
                    logger.warn('Received status response object, but success was false or status invalid', 'ApiStatus');
                }
            } 
            // Check if it's a direct boolean status (e.g., from broadcast)
            else if (typeof responseOrStatus === 'boolean') {
                isConnected = responseOrStatus;
                logger.info(`ApiStatus received direct boolean status: ${isConnected}`, 'ApiStatus');
            } 
            // Check if it's the old format object with 'connected' property
            else if (responseOrStatus && typeof responseOrStatus === 'object' && responseOrStatus.hasOwnProperty('connected')) {
                isConnected = !!responseOrStatus.connected;
                logger.info(`ApiStatus parsed legacy response with 'connected' property: ${isConnected}`, 'ApiStatus');
            }
            // Otherwise, it's an invalid format
            else {
                logger.warn(`Invalid API status response/update received: ${JSON.stringify(responseOrStatus)}`, 'ApiStatus');
            }
            
            // Update the display with the determined status
            this.updateStatusDisplay(isConnected);

        } catch (error) {
            handleError(error, 'ApiStatus.handleStatusUpdate');
            this.updateStatusDisplay(false); // Default to false on error
        }
    }
    
    /**
     * Update the status display in the UI
     * @param {boolean} isConnected - Whether the WebSocket is connected
     */
    updateStatusDisplay(isConnected) {
        try {
            if (!this.statusElement) {
                throw createError('DomError', 'Status element not found', 'ApiStatus.updateStatusDisplay');
            }
            
            logger.info(`Updating API status display: ${isConnected ? 'Connected' : 'Disconnected'}`, 'ApiStatus');
            
            // Update text and styling
            if (isConnected) {
                this.statusElement.innerHTML = 'Connected';
                this.statusElement.className = 'status-connected';
                this.statusElement.style.color = '#10b981';
                this.statusElement.style.fontWeight = '600';
            } else {
                // Add retry button when disconnected
                this.statusElement.innerHTML = `
                    <span style="color: #ef4444; font-weight: 600;">Disconnected</span>
                    <button id="api-retry-btn" style="
                        background: none;
                        border: none;
                        cursor: pointer;
                        padding: 4px 8px;
                        margin-left: 8px;
                        font-size: 16px;
                        color: #0077b5;
                        transition: transform 0.2s ease;
                        display: inline-flex;
                        align-items: center;
                        vertical-align: middle;
                    " title="Retry connection">🔄</button>
                `;
                this.statusElement.className = 'status-disconnected';
                
                // Add click handler for retry button
                const retryBtn = document.getElementById('api-retry-btn');
                if (retryBtn) {
                    retryBtn.addEventListener('click', () => this.retryConnection());
                    
                    // Add hover effect
                    retryBtn.addEventListener('mouseover', () => {
                        retryBtn.style.transform = 'scale(1.2) rotate(180deg)';
                    });
                    retryBtn.addEventListener('mouseout', () => {
                        retryBtn.style.transform = 'scale(1) rotate(0deg)';
                    });
                }
            }
        } catch (error) {
            handleError(error, 'ApiStatus.updateStatusDisplay');
        }
    }
    
    /**
     * Retry the WebSocket connection
     */
    async retryConnection() {
        try {
            logger.info('Manual retry connection requested from UI', 'ApiStatus');
            
            // Update status to show retrying
            if (this.statusElement) {
                this.statusElement.innerHTML = '<span style="color: #f59e0b; font-weight: 600;">Reconnecting...</span>';
            }
            
            // Send reconnect request to background
            const response = await sendMessageToBackground({ 
                type: MESSAGE_TYPES.RECONNECT_WEBSOCKET 
            });
            
            if (response && response.success) {
                logger.info('Reconnection initiated successfully', 'ApiStatus');
            } else {
                logger.warn('Reconnection request failed', 'ApiStatus');
                // Will update to disconnected state via broadcast
            }
        } catch (error) {
            handleError(error, 'ApiStatus.retryConnection');
            // Restore disconnected state on error
            this.updateStatusDisplay(false);
        }
    }
    
    /**
     * Start periodic status checking
     */
    startStatusChecking() {
        try {
        // Clear any existing interval
        this.stopStatusChecking();
        
            // Only start if tab is visible
            if (document.visibilityState === 'visible') {
                logger.info(`Started periodic API status checking (${ACTIVE_CHECK_INTERVAL/1000}s interval)`, 'ApiStatus');
                
                // Check every ACTIVE_CHECK_INTERVAL seconds
                this.statusCheckInterval = window.setInterval(() => {
                    logger.info('Periodic API status check while tab active', 'ApiStatus');
            this.checkStatus();
                }, ACTIVE_CHECK_INTERVAL);
            }
        } catch (error) {
            handleError(error, 'ApiStatus.startStatusChecking');
        }
    }
    
    /**
     * Stop periodic status checking
     */
    stopStatusChecking() {
        try {
        if (this.statusCheckInterval) {
                window.clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
                logger.info('Stopped periodic API status checking', 'ApiStatus');
            }
        } catch (error) {
            handleError(error, 'ApiStatus.stopStatusChecking');
        }
    }
} 