//@ts-check
/// <reference types="chrome"/>

import { logger } from '../../../shared/utils/logger.js';
import { handleError, createError } from '../../../shared/utils/error-handler.js';
import appConfig from '../../../shared/config/app.config.js';
import { checkBackendCompatibility } from '../../../shared/utils/version-check.js';

/**
 * Server configuration options
 */
const SERVER_CONFIGS = {
    MAIN: {
        name: 'Main Server (Cloud)',
        apiUrl: 'https://lg.ainnovate.tech'
    },
    CUSTOM: {
        name: 'Your Private Server',
        apiUrl: ''
    }
};

/**
 * ServerSettings Component for managing server configuration
 */
export class ServerSettings {
    /**
     * @type {HTMLElement|null}
     */
    container = null;
    
    /**
     * @type {HTMLSelectElement|null}
     */
    serverSelect = null;
    
    /**
     * @type {HTMLInputElement|null}
     */
    customApiInput = null;
    
    /**
     * @type {HTMLButtonElement|null}
     */
    saveButton = null;
    
    /**
     * @type {HTMLDivElement|null}
     */
    customFieldsContainer = null;
    
    /**
     * @type {Object|null}
     */
    serverInfo = null;
    
    /**
     * Create a new ServerSettings component
     * @param {HTMLElement} containerElement - The container element to render into
     */
    constructor(containerElement) {
        this.container = containerElement;
        this.init();
    }
    
    /**
     * @type {Object|null}
     */
    versionCompatibility = null;
    
    /**
     * Initialize the component
     */
    async init() {
        try {
            logger.info('Initializing ServerSettings component', 'ServerSettings');
            
            if (!this.container) {
                throw createError('DomError', 'Container element not provided', 'ServerSettings.init');
            }
            
            // Fetch server info first
            await this.fetchServerInfo();
            
            // Check version compatibility
            await this.checkVersionCompatibility();
            
            // Render the component
            this.render();
            
            // Load current settings
            await this.loadCurrentSettings();
            
            // Set up event listeners
            this.setupEventListeners();
            
            logger.info('ServerSettings component initialized', 'ServerSettings');
        } catch (error) {
            handleError(error, 'ServerSettings.init');
        }
    }
    
    /**
     * Check version compatibility between extension and backend
     */
    async checkVersionCompatibility() {
        try {
            this.versionCompatibility = await checkBackendCompatibility();
            logger.info(`Version check result: ${JSON.stringify(this.versionCompatibility)}`, 'ServerSettings');
        } catch (error) {
            logger.error(`Version check failed: ${error.message}`, 'ServerSettings');
            this.versionCompatibility = null;
        }
    }
    
    /**
     * Render the component HTML
     */
    render() {
        const serverName = this.serverInfo?.server_name || 'Unknown Server';
        const version = this.serverInfo?.version || 'N/A';
        const edition = this.serverInfo?.edition || 'Unknown';
        const isDefault = this.serverInfo?.is_default_server !== false;
        
        // Edition badge color
        const editionColor = edition.toLowerCase().includes('saas') ? '#3b82f6' : 
                           edition.toLowerCase().includes('enterprise') ? '#8b5cf6' : 
                           '#10b981';
        
        // Build version warning HTML if needed
        const versionWarningHtml = this.buildVersionWarningHtml();
        
        this.container.innerHTML = `
            <div class="server-settings" style="font-size: 15px;">
                <div class="current-config">
                    <div style="margin-bottom: 20px;">
                        <p style="margin: 8px 0; line-height: 1.6;">
                            <strong style="color: #2c3e50;">Server Name:</strong> 
                            <span style="color: #5a6c7d;">${serverName}</span>
                        </p>
                        <p style="margin: 8px 0; line-height: 1.6;">
                            <strong style="color: #2c3e50;">URL:</strong> 
                            <span id="current-api-display" style="color: #5a6c7d;">Loading...</span>
                        </p>
                        <p style="margin: 8px 0; line-height: 1.6;">
                            <strong style="color: #2c3e50;">Version:</strong> 
                            <span style="color: #5a6c7d;">${version}</span>
                        </p>
                        ${versionWarningHtml}
                        <p style="margin: 8px 0; line-height: 1.6;">
                            <strong style="color: #2c3e50;">Edition:</strong> 
                            <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; background: ${editionColor}; color: white; font-size: 13px; font-weight: 500;">
                                ${edition.toUpperCase()}
                            </span>
                        </p>
                        ${isDefault ? `
                        <p style="margin: 8px 0; line-height: 1.6;">
                            <span style="display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 4px; background: #f0f9ff; color: #0369a1; font-size: 13px;">
                                <svg style="width: 14px; height: 14px; margin-right: 6px;" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                                </svg>
                                Official Server
                            </span>
                        </p>
                        ` : ''}
                    </div>
                </div>
                
                <p class="info-text" style="margin-top: 18px; padding-top: 18px; border-top: 1px solid #e5e7eb; color: #7f8c9a; font-size: 14px; line-height: 1.5;">
                    💡 To change the server, please log out first.
                </p>
            </div>
        `;
    }
    
    /**
     * Build version warning HTML based on compatibility check
     * @returns {string} HTML string for version warning or empty string
     */
    buildVersionWarningHtml() {
        if (!this.versionCompatibility) return '';
        
        const { compatible, warningType, backendVersion, extensionVersion, message } = this.versionCompatibility;
        
        // No warning needed if versions match perfectly
        if (!warningType) return '';
        
        let backgroundColor, borderColor, titleColor, icon, title;
        
        if (!compatible) {
            // Critical - red
            backgroundColor = '#fef2f2';
            borderColor = '#ef4444';
            titleColor = '#dc2626';
            icon = '🚫';
            title = warningType === 'extension_outdated' ? 'Extension Update Required' : 'Backend Update Required';
        } else {
            // Warning - yellow (version mismatch)
            backgroundColor = '#fef3c7';
            borderColor = '#f59e0b';
            titleColor = '#d97706';
            icon = '⚠️';
            title = 'Version Mismatch';
        }
        
        // Build version info text
        let versionText = '';
        if (backendVersion && backendVersion !== 'unknown') {
            versionText = `Backend: v${backendVersion}`;
        }
        if (extensionVersion) {
            versionText += versionText ? ` • Extension: v${extensionVersion}` : `Extension: v${extensionVersion}`;
        }
        
        return `
            <div style="margin: 12px 0; padding: 12px; background: ${backgroundColor}; border: 1px solid ${borderColor}; border-radius: 6px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                    <span style="font-size: 16px;">${icon}</span>
                    <strong style="color: ${titleColor}; font-size: 13px;">${title}</strong>
                </div>
                <div style="font-size: 12px; color: #78350f; padding-left: 24px;">${versionText}</div>
                ${message ? `<div style="font-size: 11px; color: #78350f; padding-left: 24px; margin-top: 4px; opacity: 0.9;">${message}</div>` : ''}
            </div>
        `;
    }
    
    /**
     * Load current settings from localStorage
     */
    async loadCurrentSettings() {
        try {
            const settings = await this.getServerSettings();
            
            // Update current config display
            const currentApiDisplay = document.getElementById('current-api-display');
            
            if (currentApiDisplay) currentApiDisplay.textContent = settings.apiUrl;
            
            logger.info('Current settings loaded', 'ServerSettings');
        } catch (error) {
            handleError(error, 'ServerSettings.loadCurrentSettings');
        }
    }
    
    /**
     * Get server settings from localStorage
     * @returns {Promise<{serverType: string, apiUrl: string}>}
     */
    async getServerSettings() {
        return new Promise((resolve) => {
            chrome.storage.local.get(['serverType', 'customApiUrl'], (result) => {
                const serverType = result.serverType || 'MAIN';
                
                if (serverType === 'CUSTOM') {
                    resolve({
                        serverType: 'CUSTOM',
                        apiUrl: result.customApiUrl || ''
                    });
                } else {
                    const config = SERVER_CONFIGS[serverType] || SERVER_CONFIGS.MAIN;
                    resolve({
                        serverType,
                        apiUrl: config.apiUrl
                    });
                }
            });
        });
    }
    
    /**
     * Fetch server information from the backend
     */
    async fetchServerInfo() {
        try {
            const serverUrls = await appConfig.getServerUrls();
            const infoUrl = `${serverUrls.apiUrl}/api/v1/server/info`;
            
            logger.info(`[SERVER_SETTINGS] Fetching server info from: ${infoUrl}`, 'ServerSettings.fetchServerInfo');
            
            const response = await fetch(infoUrl);
            
            if (!response.ok) {
                throw new Error(`Failed to fetch server info: ${response.status}`);
            }
            
            this.serverInfo = await response.json();
            logger.info('[SERVER_SETTINGS] Successfully fetched server info', 'ServerSettings.fetchServerInfo');
        } catch (error) {
            handleError(error, 'ServerSettings.fetchServerInfo');
            // Set default info if fetch fails
            this.serverInfo = {
                server_name: "Unknown Server",
                version: "N/A",
                edition: "Unknown",
                is_default_server: false
            };
        }
    }
    
    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // No event listeners needed - display only
    }
}

