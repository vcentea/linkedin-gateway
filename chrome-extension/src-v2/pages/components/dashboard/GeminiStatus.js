//@ts-check
/// <reference types="chrome"/>

import { MESSAGE_TYPES } from '../../../shared/constants/message-types.js';
import { GEMINI_STATUS } from '../../../shared/constants/gemini-constants.js';
import { logger } from '../../../shared/utils/logger.js';
import { handleError, createError } from '../../../shared/utils/error-handler.js';
import { sendMessageToBackground } from '../../../background/services/messaging.service.js';
import appConfig from '../../../shared/config/app.config.js';

// Extract constants from app config
const MIN_CHECK_INTERVAL = appConfig.MIN_CHECK_INTERVAL || 60000; // Default 1 minute
const ACTIVE_CHECK_INTERVAL = appConfig.ACTIVE_CHECK_INTERVAL || 120000; // Default 2 minutes

/**
 * GeminiStatus Component for displaying and controlling Gemini AI integration status
 * 
 * Uses script-based OAuth flow since Gemini CLI credentials only work with localhost redirects.
 */
export class GeminiStatus {
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
    connectButton = null;
    
    /**
     * @type {HTMLElement|null}
     */
    emailDisplay = null;

    /**
     * @type {HTMLElement|null}
     */
    emailContainer = null;
    
    /**
     * @type {HTMLButtonElement|null}
     */
    reconnectButton = null;
    
    /**
     * @type {boolean}
     */
    isGeminiEnabled = false;
    
    /**
     * @type {number}
     */
    lastCheckTime = 0;
    
    /**
     * @type {number|null}
     */
    statusCheckInterval = null;
    
    /**
     * Create a new GeminiStatus component
     */
    constructor() {
        this.container = document.getElementById('gemini-status-container');
        this.lastCheckTime = 0;
        this.statusCheckInterval = null;
        
        if (!this.container) {
            logger.error('Gemini status container not found in HTML', 'GeminiStatus.constructor');
            return;
        }
        
        // Get the specific elements within the container
        this.statusDisplay = document.getElementById('gemini-status-message');
        this.connectButton = /** @type {HTMLButtonElement|null} */ (document.getElementById('gemini-connect-btn'));
        this.emailDisplay = document.getElementById('gemini-email-display');
        this.emailContainer = document.getElementById('gemini-email-container');
        
        // Bind methods to maintain proper 'this' context
        this.checkGeminiStatus = this.checkGeminiStatus.bind(this);
        this.handleVisibilityChange = this.handleVisibilityChange.bind(this);
        
        // Initialize the component
        this.init();
    }
    
    /**
     * Initialize the component
     */
    async init() {
        try {
            logger.info('Initializing Gemini Status component', 'GeminiStatus');

            if (!this.statusDisplay) {
                throw createError('DomError', 'Gemini status display element not found', 'GeminiStatus.init');
            }
            if (!this.connectButton) {
                throw createError('DomError', 'Gemini connect button not found', 'GeminiStatus.init');
            }
            
            // Set up visibility change detection
            document.addEventListener('visibilitychange', this.handleVisibilityChange);
            
            // Check current status (force=true to bypass throttling)
            await this.checkGeminiStatus(true);
            
            // Set up event listeners for button
            this.connectButton.addEventListener('click', () => this.handleConnectClick());
            
            // Listen for status updates from background
            this.setupMessageListener();
            
            // Start periodic status checking if tab is visible
            if (document.visibilityState === 'visible') {
                this.startStatusChecking();
            }
            
            logger.info('Gemini Status component initialized', 'GeminiStatus');
        } catch (error) {
            handleError(error, 'GeminiStatus.init');
            this.showError('Failed to initialize Gemini status component');
        }
    }
    
    /**
     * Handle visibility change event
     */
    handleVisibilityChange() {
        logger.info(`Visibility changed: ${document.visibilityState}`, 'GeminiStatus');
        
        if (document.visibilityState === 'visible') {
            logger.info('Tab became visible - checking Gemini status', 'GeminiStatus');
            this.checkGeminiStatus(true);
            this.startStatusChecking();
        } else {
            this.stopStatusChecking();
        }
    }
    
    /**
     * Set up message listener for Gemini status updates
     */
    setupMessageListener() {
        chrome.runtime.onMessage.addListener((message) => {
            try {
                if (message && message.type === MESSAGE_TYPES.GEMINI_STATUS_UPDATE) {
                    this.updateStatusDisplay(
                        message.data?.status === GEMINI_STATUS.CONNECTED,
                        message.data?.email
                    );
                }
            } catch (error) {
                handleError(error, 'GeminiStatus.setupMessageListener');
            }
        });
        
        logger.info('Gemini status message listener established', 'GeminiStatus');
    }
    
    /**
     * Check the current Gemini integration status
     * @param {boolean} [force=false] - Whether to force a check regardless of throttling
     */
    async checkGeminiStatus(force = false) {
        try {
            logger.info('Checking Gemini integration status', 'GeminiStatus');
            
            const now = Date.now();
            
            // Skip check if too recent, unless forced
            if (!force && (now - this.lastCheckTime) < MIN_CHECK_INTERVAL) {
                logger.info(`Skipping Gemini check - last check was ${Math.round((now - this.lastCheckTime)/1000)}s ago`, 'GeminiStatus');
                return;
            }
            
            this.lastCheckTime = now;
            
            if (!this.statusDisplay) {
                throw createError('DomError', 'Gemini status display element not found', 'GeminiStatus.checkGeminiStatus');
            }
            
            // Show checking status
            this.statusDisplay.textContent = 'Checking...';
            this.statusDisplay.className = 'status-checking';
            
            // Request status from background
            const response = await sendMessageToBackground({ 
                type: MESSAGE_TYPES.GET_GEMINI_STATUS 
            });
            
            if (!response) {
                throw createError('ApiError', 'No response received from background service', 'GeminiStatus.checkGeminiStatus');
            }
            
            // Update status display based on response
            this.updateStatusDisplay(response.enabled, response.email);
            
            logger.info(`Gemini status checked: ${response.enabled ? 'Enabled' : 'Disabled'}`, 'GeminiStatus');
        } catch (error) {
            handleError(error, 'GeminiStatus.checkGeminiStatus');
            this.updateStatusDisplay(false);
        }
    }
    
    /**
     * Start periodic status checking
     */
    startStatusChecking() {
        try {
            this.stopStatusChecking();
            
            if (document.visibilityState === 'visible') {
                logger.info('Starting periodic Gemini status checking', 'GeminiStatus');
                
                this.statusCheckInterval = window.setInterval(() => {
                    logger.info('Periodic Gemini status check while tab active', 'GeminiStatus');
                    this.checkGeminiStatus();
                }, ACTIVE_CHECK_INTERVAL);
            }
        } catch (error) {
            handleError(error, 'GeminiStatus.startStatusChecking');
        }
    }
    
    /**
     * Stop periodic status checking
     */
    stopStatusChecking() {
        try {
            if (this.statusCheckInterval) {
                logger.info('Stopping periodic Gemini status checking', 'GeminiStatus');
                window.clearInterval(this.statusCheckInterval);
                this.statusCheckInterval = null;
            }
        } catch (error) {
            handleError(error, 'GeminiStatus.stopStatusChecking');
        }
    }
    
    /**
     * Handle connect button click
     * Shows platform selection dialog for script download
     */
    async handleConnectClick() {
        logger.info('Connect Gemini button clicked', 'GeminiStatus');
        this.showScriptDownloadDialog();
    }
    
    /**
     * Show dialog for downloading the connection script
     */
    showScriptDownloadDialog() {
        // Create modal dialog
        const modal = document.createElement('div');
        modal.id = 'gemini-script-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
        `;
        
        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: white;
            border-radius: 16px;
            padding: 28px;
            max-width: 480px;
            width: 90%;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        `;
        
        dialog.innerHTML = `
            <div style="text-align: center; margin-bottom: 20px;">
                <div style="font-size: 48px; margin-bottom: 12px;">🔐</div>
                <h3 style="margin: 0 0 8px 0; color: #1f2937; font-size: 20px; font-weight: 600;">
                    Connect Gemini AI
                </h3>
                <p style="color: #6b7280; font-size: 14px; margin: 0;">
                    Download and run a script to securely connect your Google account.
                </p>
            </div>
            
            <div style="background: #f3f4f6; border-radius: 12px; padding: 16px; margin-bottom: 20px;">
                <p style="color: #374151; font-size: 13px; margin: 0 0 12px 0; font-weight: 500;">
                    How it works:
                </p>
                <ol style="color: #6b7280; font-size: 13px; margin: 0; padding-left: 20px; line-height: 1.8;">
                    <li>Download the script for your system</li>
                    <li>Run it (it will open Google sign-in)</li>
                    <li>Sign in with your Google account</li>
                    <li>Done! Your account is connected</li>
                </ol>
            </div>
            
            <div style="display: flex; gap: 12px; margin-bottom: 16px;">
                <button id="download-windows-script" style="
                    flex: 1;
                    padding: 14px 20px;
                    border: 2px solid #0078d4;
                    border-radius: 10px;
                    background: white;
                    color: #0078d4;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 600;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 6px;
                    transition: all 0.2s ease;
                ">
                    <span style="font-size: 24px;">🪟</span>
                    Windows
                    <span style="font-size: 11px; font-weight: 400; opacity: 0.8;">Double-click to run</span>
                </button>
                <button id="download-mac-script" style="
                    flex: 1;
                    padding: 14px 20px;
                    border: 2px solid #333;
                    border-radius: 10px;
                    background: white;
                    color: #333;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 600;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 6px;
                    transition: all 0.2s ease;
                ">
                    <span style="font-size: 24px;">🍎</span>
                    macOS
                    <span style="font-size: 11px; font-weight: 400; opacity: 0.8;">Terminal</span>
                </button>
            </div>
            
            <button id="gemini-script-cancel" style="
                width: 100%;
                padding: 12px;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                background: white;
                color: #6b7280;
                cursor: pointer;
                font-size: 14px;
            ">Cancel</button>
        `;
        
        modal.appendChild(dialog);
        document.body.appendChild(modal);
        
        // Add hover effects
        const winBtn = document.getElementById('download-windows-script');
        const macBtn = document.getElementById('download-mac-script');
        
        if (winBtn) {
            winBtn.onmouseover = () => { winBtn.style.background = '#0078d4'; winBtn.style.color = 'white'; };
            winBtn.onmouseout = () => { winBtn.style.background = 'white'; winBtn.style.color = '#0078d4'; };
            winBtn.addEventListener('click', () => {
                modal.remove();
                this.downloadScript('windows');
            });
        }
        
        if (macBtn) {
            macBtn.onmouseover = () => { macBtn.style.background = '#333'; macBtn.style.color = 'white'; };
            macBtn.onmouseout = () => { macBtn.style.background = 'white'; macBtn.style.color = '#333'; };
            macBtn.addEventListener('click', () => {
                modal.remove();
                this.downloadScript('mac');
            });
        }
        
        // Handle cancel
        const cancelBtn = document.getElementById('gemini-script-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => modal.remove());
        }
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    }
    
    /**
     * Download the connection script
     * @param {string} platform - 'windows' or 'mac'
     */
    async downloadScript(platform) {
        logger.info(`Downloading ${platform} script`, 'GeminiStatus');
        
        if (this.statusDisplay) {
            this.statusDisplay.textContent = 'Generating script...';
            this.statusDisplay.style.color = '#f59e0b';
        }

        try {
            // Get server URL and access token
            const { apiUrl } = await appConfig.getServerUrls();
            const authService = await import('../../../background/services/auth.service.js');
            const accessToken = await authService.getAccessToken();
            
            if (!accessToken) {
                throw createError('AuthError', 'Not logged in', 'GeminiStatus.downloadScript');
            }
            
            // Request script from backend
            const response = await fetch(`${apiUrl}/api/v1/gemini/auth/script/${platform}`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                }
            });
            
            if (!response.ok) {
                throw createError('ApiError', `Failed to generate script: ${response.statusText}`, 'GeminiStatus.downloadScript');
            }
            
            // Get script content
            const scriptContent = await response.text();
            
            // Create download
            const blob = new Blob([scriptContent], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const filename = platform === 'windows' ? 'connect_gemini.bat' : 'connect_gemini.sh';
            
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            logger.info(`Script downloaded: ${filename}`, 'GeminiStatus');
            
            // Show instructions
            this.showPostDownloadInstructions(platform);
            
            // Start polling for completion
            this.startPollingForConnection();
            
        } catch (error) {
            handleError(error, 'GeminiStatus.downloadScript');
            this.showError(error.message || 'Failed to download script');
            this.updateStatusDisplay(false);
        }
    }
    
    /**
     * Show instructions after script download
     * @param {string} platform
     */
    showPostDownloadInstructions(platform) {
        if (this.statusDisplay) {
            this.statusDisplay.textContent = 'Run the downloaded script...';
            this.statusDisplay.style.color = '#f59e0b';
        }
        
        const instructions = platform === 'windows' 
            ? 'Double-click connect_gemini.bat to run it'
            : 'Open Terminal and run: chmod +x ~/Downloads/connect_gemini.sh && ~/Downloads/connect_gemini.sh';
        
        // Create a subtle notification
        const notification = document.createElement('div');
        notification.id = 'gemini-download-notification';
        notification.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #1f2937;
            color: white;
            padding: 16px 20px;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
            z-index: 10001;
            max-width: 360px;
            font-size: 13px;
            line-height: 1.5;
        `;
        notification.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 12px;">
                <span style="font-size: 20px;">📥</span>
                <div>
                    <strong style="display: block; margin-bottom: 4px;">Script Downloaded!</strong>
                    <span style="opacity: 0.9;">${instructions}</span>
                </div>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 15 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 15000);
    }
    
    /**
     * Start polling for connection completion
     * After user runs the script, check periodically if credentials arrived
     */
    startPollingForConnection() {
        let pollCount = 0;
        const maxPolls = 60; // 2 minutes (2s intervals)
        
        const poll = async () => {
            pollCount++;
            
            if (pollCount > maxPolls) {
                // Stop polling
                if (this.statusDisplay && !this.isGeminiEnabled) {
                    this.statusDisplay.textContent = 'Connection timed out';
                    this.statusDisplay.style.color = '#ef4444';
                }
                return;
            }
            
            // Check status
            await this.checkGeminiStatus(true);
            
            // If connected, stop polling
            if (this.isGeminiEnabled) {
                logger.info('Gemini connected via script!', 'GeminiStatus');
                // Remove notification if present
                const notification = document.getElementById('gemini-download-notification');
                if (notification) notification.remove();
                return;
            }
            
            // Continue polling
            setTimeout(poll, 2000);
        };
        
        // Start after a delay to give user time to run script
        setTimeout(poll, 3000);
    }
    
    /**
     * Handle reconnect button click (change account)
     */
    async handleReconnectClick() {
        logger.info('Reconnect Gemini clicked (change account)', 'GeminiStatus');
        this.showScriptDownloadDialog();
    }
    
    /**
     * Update the status display based on Gemini integration status
     * @param {boolean} isEnabled - Whether Gemini integration is enabled
     * @param {string} [email] - User's Google email if connected
     */
    updateStatusDisplay(isEnabled, email = null) {
        this.isGeminiEnabled = isEnabled;
        
        if (!this.statusDisplay || !this.connectButton) {
            handleError(createError('DomError', 'Required UI elements not found', 'GeminiStatus.updateStatusDisplay'));
            return;
        }
        
        if (isEnabled) {
            this.statusDisplay.textContent = 'Connected';
            this.statusDisplay.className = 'status-enabled';
            this.statusDisplay.style.color = '#10b981';
            this.statusDisplay.style.fontWeight = '600';
            
            // Show email if available
            if (this.emailDisplay && email) {
                this.emailDisplay.textContent = email;
                if (this.emailContainer) {
                    this.emailContainer.style.display = 'block';
                } else {
                    this.emailDisplay.style.display = 'inline';
                }
            }
            
            // Hide main connect button, show small reconnect
            this.connectButton.style.display = 'none';
            this.showReconnectButton();
        } else {
            this.statusDisplay.textContent = 'Not Connected';
            this.statusDisplay.className = 'status-disabled';
            this.statusDisplay.style.color = '#ef4444';
            this.statusDisplay.style.fontWeight = '600';
            
            // Hide email display
            if (this.emailContainer) {
                this.emailContainer.style.display = 'none';
            } else if (this.emailDisplay) {
                this.emailDisplay.style.display = 'none';
            }
            
            // Show connect button, hide reconnect
            this.connectButton.textContent = 'Connect Gemini';
            this.connectButton.style.display = 'inline-block';
            this.applyConnectButtonStyles();
            this.hideReconnectButton();
        }
    }
    
    /**
     * Show the small reconnect button
     */
    showReconnectButton() {
        if (!this.reconnectButton) {
            this.reconnectButton = document.createElement('button');
            this.reconnectButton.id = 'gemini-reconnect-btn';
            this.reconnectButton.title = 'Change Google account';
            this.reconnectButton.innerHTML = '🔄';
            this.reconnectButton.style.cssText = `
                background: transparent;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px 8px;
                cursor: pointer;
                font-size: 12px;
                margin-left: 8px;
                transition: all 0.2s ease;
            `;
            
            this.reconnectButton.onmouseover = () => {
                this.reconnectButton.style.background = '#f3f4f6';
                this.reconnectButton.style.borderColor = '#9ca3af';
            };
            this.reconnectButton.onmouseout = () => {
                this.reconnectButton.style.background = 'transparent';
                this.reconnectButton.style.borderColor = '#d1d5db';
            };
            
            this.reconnectButton.addEventListener('click', () => this.handleReconnectClick());
            
            // Insert after status display
            // We want it before the "Connected" text, so actually insert before status display if possible, 
            // or use flex order.
            // The container is:
            // <div id="gemini-status-container" style="display: flex; justify-content: flex-end; align-items: center; gap: 8px;">
            //     <span id="gemini-status-message">Checking...</span>
            // </div>
            
            // So we want to insert BEFORE statusDisplay
            if (this.statusDisplay && this.statusDisplay.parentNode) {
                this.statusDisplay.parentNode.insertBefore(this.reconnectButton, this.statusDisplay);
            }
        }
        
        this.reconnectButton.style.display = 'inline-block';
    }
    
    /**
     * Hide the reconnect button
     */
    hideReconnectButton() {
        if (this.reconnectButton) {
            this.reconnectButton.style.display = 'none';
        }
    }
    
    /**
     * Apply styles for the connect button
     */
    applyConnectButtonStyles() {
        if (!this.connectButton) return;
        
        // Google/Gemini blue color scheme
        this.connectButton.style.backgroundColor = '#4285f4';
        this.connectButton.style.color = 'white';
        this.connectButton.style.border = 'none';
        this.connectButton.style.padding = '10px 20px';
        this.connectButton.style.borderRadius = '8px';
        this.connectButton.style.cursor = 'pointer';
        this.connectButton.style.fontWeight = '600';
        this.connectButton.style.fontSize = '14px';
        this.connectButton.style.transition = 'all 0.2s ease';
        
        // Add hover effects
        this.connectButton.onmouseover = () => {
            this.connectButton.style.backgroundColor = '#3367d6';
            this.connectButton.style.transform = 'translateY(-1px)';
            this.connectButton.style.boxShadow = '0 4px 8px rgba(66,133,244,0.3)';
        };
        
        this.connectButton.onmouseout = () => {
            this.connectButton.style.backgroundColor = '#4285f4';
            this.connectButton.style.transform = 'translateY(0)';
            this.connectButton.style.boxShadow = 'none';
        };
    }
    
    /**
     * Show an error message
     * @param {string} message - Error message to display
     */
    showError(message) {
        logger.error(new Error(message), 'GeminiStatus');
        
        try {
            let errorElement = document.getElementById('gemini-status-error');
            
            if (!errorElement && this.container) {
                errorElement = document.createElement('div');
                errorElement.id = 'gemini-status-error';
                errorElement.className = 'error-message';
                errorElement.style.color = '#dc2626';
                errorElement.style.fontSize = '12px';
                errorElement.style.marginTop = '8px';
                this.container.appendChild(errorElement);
            }
            
            if (errorElement) {
                errorElement.textContent = `Error: ${message}`;
                errorElement.style.display = 'block';
                
                // Auto-hide after 5 seconds
                setTimeout(() => {
                    if (errorElement) {
                        errorElement.style.display = 'none';
                    }
                }, 5000);
            }
        } catch (error) {
            handleError(error, 'GeminiStatus.showError');
        }
    }
}
