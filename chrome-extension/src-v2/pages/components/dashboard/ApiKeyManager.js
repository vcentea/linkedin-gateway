/// <reference types="chrome"/>

import { logger } from '../../../shared/utils/logger.js';
import { handleError, createError } from '../../../shared/utils/error-handler.js';
import { MESSAGE_TYPES } from '../../../shared/constants/message-types.js';
import { sendMessageToBackground } from '../../../background/services/messaging.service.js';
import apiConfig from '../../../shared/config/api.config.js';
import { showToast } from '../../../shared/utils/toast.utils.js';
import {
    listApiKeys,
    deleteApiKeyById,
    updateInstanceName,
    updateWebhookConfig,
    deleteWebhookConfig,
    updateLegacyWebhookConfig,
    deleteLegacyWebhookConfig
} from '../../../shared/api/keys.api.js';
import { getInstanceId } from '../../../shared/utils/instance-id.js';
import { formatDate } from '../../../shared/utils/date.utils.js';

/**
 * ApiKeyManager component for handling multi-key API operations (v1.1.0)
 * Supports multiple API keys per user with instance tracking
 */
export class ApiKeyManager {
    /**
     * @type {HTMLElement|null}
     */
    container = null;
    
    /**
     * @type {Array<Object>}
     */
    apiKeys = [];
    
    /**
     * @type {string|null}
     */
    currentInstanceId = null;
    
    /**
     * @type {string|null}
     */
    newlyGeneratedKey = null;
    
    /**
     * @type {boolean}
     */
    isMultiKeySupported = false;
    
    constructor() {
        this.container = document.getElementById('api-key-container');
        this.apiKeys = [];
        this.currentInstanceId = null;
        this.newlyGeneratedKey = null;
        this.isMultiKeySupported = false;
        this.expandedWebhookKeys = new Set();
        
        if (!this.container) {
            logger.error('API key container not found', 'ApiKeyManager');
            return;
        }
        
        logger.info('Initializing ApiKeyManager (Multi-Key v1.1.0)', 'ApiKeyManager');
        this.initialize();
    }
    
    /**
     * Initialize the component
     */
    async initialize() {
        try {
            // Get current instance ID
            this.currentInstanceId = await getInstanceId();
            logger.info(`Current instance ID: ${this.currentInstanceId}`, 'ApiKeyManager');
            
            // Load all API keys
            await this.loadAllApiKeys();
        } catch (error) {
            handleError(error, 'ApiKeyManager.initialize');
        }
    }
    
    /**
     * Load all API keys for the user
     * Supports backward compatibility with single-key backend
     */
    async loadAllApiKeys() {
        const logContext = 'ApiKeyManager:loadAllApiKeys';
        logger.info('Loading all API keys', logContext);
        
        try {
            // Get access token from auth service
            const authResponse = await sendMessageToBackground({ type: MESSAGE_TYPES.GET_USER_PROFILE });
            
            if (!authResponse || !authResponse.authenticated) {
                logger.warn('User not authenticated', logContext);
                this.renderNoAuth();
                return;
            }
            
            // Get access token from response
            const accessToken = authResponse.accessToken;
            
            if (!accessToken) {
                logger.warn('No access token available', logContext);
                this.renderNoAuth();
                return;
            }
            
            try {
                // Try multi-key endpoint first (v1.1.0)
                const response = await listApiKeys(accessToken);
                this.isMultiKeySupported = true;
                this.apiKeys = response.keys || [];
                this.cleanupExpandedWebhookStates();
                logger.info(`Multi-key backend detected: ${this.apiKeys.length} keys found`, logContext);
            } catch (error) {
                if (error.message && error.message.includes('404')) {
                    // Fall back to legacy single-key endpoint (v1.0.x backend)
                    logger.info('Multi-key endpoint not found, falling back to legacy single-key', logContext);
                    this.isMultiKeySupported = false;
                    await this.loadLegacySingleKey();
                } else {
                    throw error;
                }
            }
            
            // Render the UI
            this.renderApiKeysList();
            
        } catch (error) {
            handleError(error, logContext);
            logger.error(`Error loading API keys: ${error.message}`, logContext);
            this.renderError('Failed to load API keys. Please try again.');
        }
    }
    
    /**
     * Load legacy single key (backward compatibility)
     */
    async loadLegacySingleKey() {
        const logContext = 'ApiKeyManager:loadLegacySingleKey';
        logger.info('Loading legacy single key', logContext);
        
        try {
            const response = await sendMessageToBackground({ type: MESSAGE_TYPES.GET_API_KEY });
            
            if (response && response.success && response.keyExists) {
                // Create a pseudo-key object for display
                this.apiKeys = [{
                    id: 'legacy',
                    prefix: '****', // We don't have the prefix in legacy mode
                    instance_id: null,
                    instance_name: 'Legacy Key',
                    browser_info: null,
                    created_at: null,
                    last_used_at: null,
                    is_active: true,
                    isLegacy: true
                }];
                this.cleanupExpandedWebhookStates();
                logger.info('Legacy single key loaded', logContext);
            } else {
                this.apiKeys = [];
                logger.info('No legacy key found', logContext);
            }
        } catch (error) {
            handleError(error, logContext);
            this.apiKeys = [];
        }
    }
    
    /**
     * Get access token from auth service
     * @returns {Promise<string|null>}
     */
    async getAccessToken() {
        try {
            const authResponse = await sendMessageToBackground({ type: MESSAGE_TYPES.GET_USER_PROFILE });
            return authResponse?.accessToken || null;
        } catch (error) {
            logger.error('Failed to get access token', 'ApiKeyManager');
            return null;
        }
    }
    
    /**
     * Render the API keys list
     */
    renderApiKeysList() {
        logger.info('Rendering API keys list', 'ApiKeyManager');
        
        try {
            if (this.apiKeys.length === 0) {
                this.renderNoKeys();
                return;
            }
            
            // Build HTML for key list
            const keysHtml = this.apiKeys.map(key => this.renderKeyCard(key)).join('');
            
        this.container.innerHTML = `
                <div class="api-keys-section">
                    <div class="api-keys-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <div>
                            <h3 style="margin: 0; font-size: 16px; color: #2c3e50;">Your API Keys</h3>
                            <p class="info-text" style="margin: 4px 0 0 0; font-size: 13px; color: #7f8c9a;">
                                ${this.isMultiKeySupported ? 'Manage API keys for all your browsers' : 'Legacy single-key mode'}
                            </p>
                        </div>
                        <div style="display: flex; gap: 10px;">
                            <button id="api-tester-btn" class="button secondary" style="background-color: #6366f1; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px; transition: all 0.2s ease;">
                                🧪 API Tester
                            </button>
                            <button id="generate-new-key-btn" class="button primary" style="background-color: #0077b5; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px; transition: all 0.2s ease;">
                                + Generate New Key
                            </button>
                        </div>
                    </div>
                    
                    <div class="api-keys-list" style="display: flex; flex-direction: column; gap: 12px;">
                        ${keysHtml}
                    </div>
                </div>
            `;
            
            this.addEventListeners();
            
        } catch (error) {
            handleError(error, 'ApiKeyManager.renderApiKeysList');
        }
    }
    
    /**
     * Render a single API key card
     * @param {Object} key - API key object
     * @returns {string} HTML for the key card
     */
    renderKeyCard(key) {
        const isCurrentInstance = key.instance_id === this.currentInstanceId;
        const isLegacy = key.isLegacy || !key.instance_id;
        const cardId = key.id || 'legacy';
        const isWebhookExpanded = this.expandedWebhookKeys.has(cardId);
        const webhookSection = isWebhookExpanded
            ? this.renderWebhookSection(key)
            : this.renderWebhookSummary(key);
        
        // Determine display name
        let instanceLabel = '🔑 Unknown Device';
        if (isLegacy) {
            instanceLabel = '🔑 Legacy Key (No Instance Tracking)';
        } else if (key.instance_name) {
            instanceLabel = `🖥️ ${key.instance_name}`;
        } else if (key.browser_info && key.browser_info.browser) {
            const browser = key.browser_info.browser.charAt(0).toUpperCase() + key.browser_info.browser.slice(1);
            const os = key.browser_info.os ? key.browser_info.os.charAt(0).toUpperCase() + key.browser_info.os.slice(1) : '';
            instanceLabel = `🖥️ ${browser}${os ? ' on ' + os : ''}`;
        }
        
        // Badge for current browser or not
        const browserBadge = isCurrentInstance 
            ? '<span style="background-color: #10b981; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; margin-left: 8px; white-space: nowrap; flex-shrink: 0;">This Browser</span>' 
            : '<span style="background-color: #9ca3af; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; margin-left: 8px; white-space: nowrap; flex-shrink: 0;">Not This Browser</span>';
        
        // Format dates
        const createdAt = key.created_at ? this.formatRelativeTime(key.created_at) : 'Unknown';
        const lastUsedAt = key.last_used_at ? this.formatRelativeTime(key.last_used_at) : 'Never used';
        
        // Prefix display
        const prefixDisplay = key.prefix ? `${key.prefix}****` : '****';
        
        // Action buttons (hide rename/delete for legacy keys if not supported)
        const showActions = !isLegacy || this.isMultiKeySupported;
        
        return `
            <div class="api-key-card" style="background-color: ${isCurrentInstance ? '#f0f9ff' : '#ffffff'}; border: 2px solid ${isCurrentInstance ? '#0077b5' : '#e8ecf1'}; border-radius: 10px; padding: 16px 20px; transition: all 0.2s ease;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 20px; width: 100%; flex-wrap: wrap;">
                    <!-- Left: Instance Name and Badge -->
                    <div style="display: flex; align-items: center; gap: 12px; flex: 1 1 200px; min-width: 0;">
                        <span style="font-weight: 600; font-size: 15px; color: #2c3e50; word-wrap: break-word; overflow-wrap: break-word;">${instanceLabel}</span>
                        ${browserBadge}
                    </div>
                
                    <!-- Center: Key Details -->
                    <div style="display: flex; align-items: center; gap: 16px; flex: 1 1 300px; min-width: 0; font-size: 13px; color: #5a6c7d; flex-wrap: wrap;">
                        <div style="display: flex; align-items: center; gap: 6px; min-width: 0;">
                            <strong style="color: #5a6c7d; white-space: nowrap;">Prefix:</strong> 
                            <code style="background-color: #f5f7fa; padding: 3px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; word-break: break-all;">${prefixDisplay}</code>
                        </div>
                        ${!isLegacy ? `
                            <div style="white-space: nowrap;"><strong style="color: #5a6c7d;">Created:</strong> ${createdAt}</div>
                            <div style="white-space: nowrap;"><strong style="color: #5a6c7d;">Last used:</strong> ${lastUsedAt}</div>
                        ` : ''}
                    </div>
                
                    <!-- Right: Action Buttons -->
                    ${showActions ? `
                        <div style="display: flex; gap: 8px; align-items: center; flex-shrink: 0;">
                            ${!isLegacy ? `<button class="btn-rename-key" data-key-id="${key.id}" data-key-name="${key.instance_name || ''}" style="background-color: #ffffff; color: #5a6c7d; border: 1px solid #e0e7ee; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-weight: 500; font-size: 13px; transition: all 0.2s ease; white-space: nowrap;">✏️ Rename</button>` : ''}
                            <button class="btn-delete-key" data-key-id="${key.id}" data-key-name="${instanceLabel.replace(/[🖥️🔑]/g, '').trim()}" style="background-color: #ef4444; color: white; border: none; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-weight: 500; font-size: 13px; transition: all 0.2s ease; white-space: nowrap;">🗑️ Delete</button>
                        </div>
                    ` : ''}
                </div>
                ${webhookSection}
            </div>
        `;
    }

    /**
     * Render webhook configuration section for a key
     * @param {Object} key - API key object
     * @returns {string} - HTML markup
     */
    renderWebhookSection(key) {
        const cardId = key.id || 'legacy';
        const hasWebhook = Boolean(key.webhook_url);
        const { headerName, headerValue } = this.extractWebhookHeaderPair(key.webhook_headers);
        const helperText = this.isMultiKeySupported && !key.isLegacy
            ? 'This webhook will only fire for requests authenticated with this API key.'
            : 'Legacy backends use a single webhook for all devices.';

        return `
            <div class="webhook-config" style="margin-top: 18px; padding-top: 18px; border-top: 1px solid #e5e7eb;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <strong style="color: #2c3e50;">Webhook (optional)</strong>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <span style="font-size: 12px; font-weight: 600; color: ${hasWebhook ? '#10b981' : '#9ca3af'};">
                            ${hasWebhook ? 'Configured' : 'Not configured'}
                        </span>
                        <button class="btn-toggle-webhook" data-key-id="${cardId}" data-expanded="true" style="background: none; border: none; color: #0077b5; font-weight: 600; cursor: pointer;">
                            Hide
                        </button>
                    </div>
                </div>
                <p style="margin: 6px 0 14px 0; color: #7f8c9a; font-size: 12px;">
                    ${helperText}
                </p>
                <div style="display: flex; flex-direction: column; gap: 12px;">
                    <div style="display: flex; flex-direction: column;">
                        <label for="webhook-url-${cardId}" style="font-size: 12px; color: #5a6c7d; margin-bottom: 4px;">Webhook URL</label>
                        <input type="url" id="webhook-url-${cardId}" value="${this.escapeHtml(key.webhook_url || '')}" placeholder="https://example.com/linkedIn/webhook" style="width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; color: #374151;" />
                    </div>
                    <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                        <div style="flex: 1; min-width: 160px;">
                            <label for="webhook-header-name-${cardId}" style="font-size: 12px; color: #5a6c7d; margin-bottom: 4px;">Header Name (optional)</label>
                            <input type="text" id="webhook-header-name-${cardId}" value="${this.escapeHtml(headerName)}" placeholder="X-Webhook-Token" style="width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; color: #374151;" />
                        </div>
                        <div style="flex: 1; min-width: 160px;">
                            <label for="webhook-header-value-${cardId}" style="font-size: 12px; color: #5a6c7d; margin-bottom: 4px;">Header Value</label>
                            <input type="text" id="webhook-header-value-${cardId}" value="${this.escapeHtml(headerValue)}" placeholder="secret-token" style="width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; color: #374151;" />
                        </div>
                    </div>
                    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                        <button class="btn-save-webhook" data-key-id="${cardId}" style="background-color: #0077b5; color: #ffffff; border: none; padding: 8px 18px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px; transition: all 0.2s ease;">
                            💾 Save Webhook
                        </button>
                        <button class="btn-delete-webhook" data-key-id="${cardId}" ${hasWebhook ? '' : 'disabled'} style="background-color: ${hasWebhook ? '#ef4444' : '#f3f4f6'}; color: ${hasWebhook ? '#ffffff' : '#9ca3af'}; border: none; padding: 8px 18px; border-radius: 6px; cursor: ${hasWebhook ? 'pointer' : 'not-allowed'}; font-weight: 600; font-size: 13px; transition: all 0.2s ease;">
                            🧹 Remove Webhook
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render collapsed summary for webhook section
     * @param {Object} key - API key object
     * @returns {string}
     */
    renderWebhookSummary(key) {
        const cardId = key.id || 'legacy';
        const hasWebhook = Boolean(key.webhook_url);
        const summaryText = hasWebhook
            ? `Sends events to ${this.escapeHtml(key.webhook_url)}`
            : 'No webhook configured';

        return `
            <div class="webhook-summary" style="margin-top: 16px; padding: 12px 16px; border: 1px dashed #d1d5db; border-radius: 8px; background-color: #f9fafb; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;">
                <div style="font-size: 13px; color: ${hasWebhook ? '#374151' : '#9ca3af'};">
                    ${summaryText}
                </div>
                <button class="btn-toggle-webhook" data-key-id="${cardId}" data-expanded="false" style="background-color: #ffffff; color: #0077b5; border: 1px solid #cfe0f5; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 12px;">
                    ${hasWebhook ? 'Edit Webhook' : 'Add Webhook'}
                </button>
            </div>
        `;
    }

    /**
     * Extract first webhook header key/value
     * @param {Object} headers - Headers object
     * @returns {{headerName: string, headerValue: string}}
     */
    extractWebhookHeaderPair(headers) {
        if (!headers || typeof headers !== 'object') {
            return { headerName: '', headerValue: '' };
        }
        const keys = Object.keys(headers);
        if (!keys.length) {
            return { headerName: '', headerValue: '' };
        }
        const firstKey = keys[0];
        const rawValue = headers[firstKey];
        return {
            headerName: typeof firstKey === 'string' ? firstKey : '',
            headerValue: typeof rawValue === 'string' ? rawValue : ''
        };
    }

    /**
     * Escape HTML entities for safe rendering
     * @param {string} value - Raw text
     * @returns {string} Escaped text
     */
    escapeHtml(value) {
        if (!value) return '';
        return value.replace(/[&<>"']/g, (char) => {
            switch (char) {
                case '&': return '&amp;';
                case '<': return '&lt;';
                case '>': return '&gt;';
                case '"': return '&quot;';
                case '\'': return '&#39;';
                default: return char;
            }
        });
    }
    
    /**
     * Format timestamp as relative time (e.g., "2 days ago")
     * @param {string} timestamp - ISO timestamp
     * @returns {string} Relative time string
     */
    formatRelativeTime(timestamp) {
        try {
            const date = new Date(timestamp);
            const now = new Date();
            const diffMs = now - date;
            const diffSec = Math.floor(diffMs / 1000);
            const diffMin = Math.floor(diffSec / 60);
            const diffHour = Math.floor(diffMin / 60);
            const diffDay = Math.floor(diffHour / 24);
            
            if (diffSec < 60) return 'Just now';
            if (diffMin < 60) return `${diffMin} minute${diffMin !== 1 ? 's' : ''} ago`;
            if (diffHour < 24) return `${diffHour} hour${diffHour !== 1 ? 's' : ''} ago`;
            if (diffDay < 30) return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`;
            
            return formatDate(timestamp);
        } catch (error) {
            return 'Unknown';
        }
    }
    
    /**
     * Render "no keys" state
     */
    renderNoKeys() {
        this.container.innerHTML = `
            <div class="no-api-keys" style="text-align: center; padding: 40px 20px;">
                <div style="font-size: 48px; margin-bottom: 16px;">🔑</div>
                <h3 style="margin: 0 0 12px 0; font-size: 18px; color: #2c3e50;">No API Keys Yet</h3>
                <p style="margin: 0 0 24px 0; color: #5a6c7d; font-size: 15px;">
                    Generate your first API key to start using the LinkedIn Gateway API.
                </p>
                <button id="generate-first-key-btn" class="button primary" style="background-color: #0077b5; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px; transition: all 0.2s ease;">
                    Generate API Key
                </button>
            </div>
        `;
        
        this.addEventListeners();
    }
    
    /**
     * Render "not authenticated" state
     */
    renderNoAuth() {
        this.container.innerHTML = `
            <div class="error-message" style="background-color: #ffebee; color: #c62828; padding: 18px; border-radius: 12px; text-align: center;">
                Please log in to manage your API keys.
            </div>
        `;
    }
    
    /**
     * Render error state
     * @param {string} message - Error message
     */
    renderError(message) {
        this.container.innerHTML = `
            <div class="error-message" style="background-color: #ffebee; color: #c62828; padding: 18px; border-radius: 12px; text-align: center;">
                ${message}
            </div>
        `;
    }
    
    /**
     * Add event listeners to buttons
     */
    addEventListeners() {
        try {
            // API Tester button
            const apiTesterBtn = document.getElementById('api-tester-btn');
            if (apiTesterBtn) {
                apiTesterBtn.addEventListener('click', () => {
                    window.location.href = '../api-tester/index.html';
                });
                apiTesterBtn.addEventListener('mouseenter', () => {
                    apiTesterBtn.style.backgroundColor = '#4f46e5';
                    apiTesterBtn.style.transform = 'translateY(-1px)';
                    apiTesterBtn.style.boxShadow = '0 4px 8px rgba(99,102,241,0.2)';
                });
                apiTesterBtn.addEventListener('mouseleave', () => {
                    apiTesterBtn.style.backgroundColor = '#6366f1';
                    apiTesterBtn.style.transform = 'translateY(0)';
                    apiTesterBtn.style.boxShadow = 'none';
                });
            }

            // Generate key buttons
            const generateBtn = document.getElementById('generate-new-key-btn');
            const generateFirstBtn = document.getElementById('generate-first-key-btn');
            
            if (generateBtn) {
                generateBtn.addEventListener('click', () => this.generateApiKey());
                this.addButtonHoverEffect(generateBtn, true);
            }
            
            if (generateFirstBtn) {
                generateFirstBtn.addEventListener('click', () => this.generateApiKey());
                this.addButtonHoverEffect(generateFirstBtn, true);
            }
            
            // Delete buttons
            const deleteButtons = document.querySelectorAll('.btn-delete-key');
            deleteButtons.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const keyId = e.target.getAttribute('data-key-id');
                    const keyName = e.target.getAttribute('data-key-name');
                    this.deleteApiKey(keyId, keyName);
                });
                this.addButtonHoverEffect(btn, false, true);
            });
            
            // Rename buttons
            const renameButtons = document.querySelectorAll('.btn-rename-key');
            renameButtons.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const keyId = e.target.getAttribute('data-key-id');
                    const currentName = e.target.getAttribute('data-key-name');
                    this.renameInstance(keyId, currentName);
                });
                this.addButtonHoverEffect(btn, false, false);
            });

            // Webhook save buttons
            const saveWebhookButtons = document.querySelectorAll('.btn-save-webhook');
            saveWebhookButtons.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const keyId = e.currentTarget.getAttribute('data-key-id');
                    this.handleWebhookSave(keyId);
                });
                this.addButtonHoverEffect(btn, true);
            });

            // Webhook delete buttons
            const deleteWebhookButtons = document.querySelectorAll('.btn-delete-webhook');
            deleteWebhookButtons.forEach(btn => {
                if (!btn.disabled) {
                    btn.addEventListener('click', (e) => {
                        const keyId = e.currentTarget.getAttribute('data-key-id');
                        this.handleWebhookDelete(keyId);
                    });
                }
                this.addButtonHoverEffect(btn, false, true);
            });

            // Webhook toggle buttons
            const toggleWebhookButtons = document.querySelectorAll('.btn-toggle-webhook');
            toggleWebhookButtons.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const keyId = e.currentTarget.getAttribute('data-key-id');
                    const expanded = e.currentTarget.getAttribute('data-expanded') === 'true';
                    if (expanded) {
                        this.expandedWebhookKeys.delete(keyId);
                    } else {
                        this.expandedWebhookKeys.add(keyId);
                    }
                    this.renderApiKeysList();
                });
                this.addButtonHoverEffect(btn, false);
            });
            
        } catch (error) {
            handleError(error, 'ApiKeyManager.addEventListeners');
        }
    }
    
    /**
     * Add hover effect to button
     * @param {HTMLElement} button - Button element
     * @param {boolean} isPrimary - Is primary button
     * @param {boolean} isDanger - Is danger button
     */
    addButtonHoverEffect(button, isPrimary, isDanger = false) {
        if (!button || button.disabled) {
            return;
        }

        const originalBgColor = button.style.backgroundColor || window.getComputedStyle(button).backgroundColor;
        const originalTransform = button.style.transform || 'translateY(0)';
        const originalBoxShadow = button.style.boxShadow || 'none';

        const handleMouseOver = () => {
            if (isPrimary) {
                button.style.backgroundColor = '#006097';
                button.style.transform = 'translateY(-1px)';
                button.style.boxShadow = '0 4px 8px rgba(0,119,181,0.2)';
            } else if (isDanger) {
                button.style.backgroundColor = '#dc2626';
                button.style.transform = 'translateY(-1px)';
            } else {
                button.style.backgroundColor = '#f8fafc';
            }
        };
        
        const handleMouseOut = () => {
            if (isPrimary) {
                button.style.backgroundColor = '#0077b5';
                button.style.transform = originalTransform;
                button.style.boxShadow = originalBoxShadow;
            } else if (isDanger) {
                button.style.backgroundColor = '#ef4444';
                button.style.transform = originalTransform;
            } else {
                button.style.backgroundColor = originalBgColor;
            }
        };

        button.addEventListener('mouseenter', handleMouseOver);
        button.addEventListener('mouseleave', handleMouseOut);
        button.addEventListener('blur', handleMouseOut);
    }
    
    /**
     * Generate a new API key
     */
    async generateApiKey() {
        logger.info('Generating new API key', 'ApiKeyManager');

        try {
            const response = await sendMessageToBackground({ type: MESSAGE_TYPES.GENERATE_API_KEY });

            if (response && response.success && response.key) {
                this.newlyGeneratedKey = response.key;

                // Show modal with full key
                this.showKeyGeneratedModal(response.key);

                // Reload keys list
                await this.loadAllApiKeys();

                showToast('API key generated successfully!', 'success', 3000);
            } else {
                logger.warn('Generate API key response negative or missing key', 'ApiKeyManager', response);
                showToast('Failed to generate API key. Please try again.', 'error');
            }
        } catch (error) {
            handleError(error, 'ApiKeyManager.generateApiKey');
            showToast('Failed to generate API key. Please try again.', 'error');
        }
    }
    
    /**
     * Show modal with newly generated API key
     * @param {string} apiKey - The full API key
     */
    showKeyGeneratedModal(apiKey) {
        // Create modal overlay
        const modal = document.createElement('div');
        modal.id = 'api-key-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
        `;
        
        modal.innerHTML = `
            <div class="modal-content" style="background-color: white; border-radius: 12px; padding: 32px; max-width: 600px; width: 90%; box-shadow: 0 20px 60px rgba(0,0,0,0.3);">
                <div style="text-align: center; margin-bottom: 24px;">
                    <div style="font-size: 48px; margin-bottom: 12px;">✅</div>
                    <h2 style="margin: 0 0 8px 0; font-size: 24px; color: #2c3e50;">API Key Generated!</h2>
                    <p style="margin: 0; color: #5a6c7d; font-size: 14px;">Instance: ${this.getCurrentInstanceName()}</p>
                </div>
                
                <div style="background-color: #f5f7fa; border-radius: 8px; padding: 16px; margin-bottom: 20px; position: relative;">
                    <pre style="margin: 0; font-family: monospace; font-size: 13px; color: #2c3e50; word-wrap: break-word; white-space: pre-wrap;">${apiKey}</pre>
                </div>
                
                <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 12px 16px; margin-bottom: 24px; border-radius: 4px;">
                    <p style="margin: 0; color: #856404; font-size: 14px; font-weight: 600;">⚠️ IMPORTANT: Copy this key now!</p>
                    <p style="margin: 4px 0 0 0; color: #856404; font-size: 13px;">You won't be able to see the full key again. Only the prefix will be visible.</p>
                </div>
                
                <div style="display: flex; gap: 12px; justify-content: center;">
                    <button id="copy-key-btn" class="button primary" style="background-color: #0077b5; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px;">
                        📋 Copy to Clipboard
                    </button>
                    <button id="close-modal-btn" class="button secondary" style="background-color: #e8ecf1; color: #2c3e50; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px;">
                        Close
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Add event listeners
        const copyBtn = document.getElementById('copy-key-btn');
        const closeBtn = document.getElementById('close-modal-btn');
        
        copyBtn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(apiKey);
                copyBtn.textContent = '✅ Copied!';
                copyBtn.style.backgroundColor = '#10b981';
                showToast('API key copied to clipboard!', 'success');
                
                setTimeout(() => {
                    copyBtn.textContent = '📋 Copy to Clipboard';
                    copyBtn.style.backgroundColor = '#0077b5';
                }, 2000);
            } catch (error) {
                showToast('Failed to copy to clipboard', 'error');
            }
        });
        
        closeBtn.addEventListener('click', () => {
            document.body.removeChild(modal);
        });
        
        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        });
    }
    
    /**
     * Get current instance name for display
     * @returns {string}
     */
    getCurrentInstanceName() {
        const currentKey = this.apiKeys.find(k => k.instance_id === this.currentInstanceId);
        if (currentKey && currentKey.instance_name) {
            return currentKey.instance_name;
        }
        return 'This Browser';
    }
    
    /**
     * Delete an API key
     * @param {string} keyId - Key ID to delete
     * @param {string} keyName - Key name for confirmation
     */
    async deleteApiKey(keyId, keyName) {
        logger.info(`Deleting API key: ${keyId}`, 'ApiKeyManager');
        
        const confirmDelete = confirm(`Are you sure you want to delete the API key for "${keyName}"?\n\nThis action cannot be undone.`);
        if (!confirmDelete) return;

        try {
            // Get access token
            const accessToken = await this.getAccessToken();
            
            if (!accessToken) {
                showToast('Not authenticated', 'error');
            return;
        }

            // Handle legacy key deletion
            if (keyId === 'legacy') {
                const response = await sendMessageToBackground({ type: MESSAGE_TYPES.DELETE_API_KEY });
                if (response && response.success) {
                    await this.loadAllApiKeys();
                    showToast('API key deleted successfully!', 'success');
                } else {
                    showToast('Failed to delete API key', 'error');
                }
                return;
            }
            
            // Delete via multi-key API
            const result = await deleteApiKeyById(accessToken, keyId);
            
            if (result.success) {
                await this.loadAllApiKeys();
                showToast('API key deleted successfully!', 'success');
            } else {
                showToast(result.error || 'Failed to delete API key', 'error');
            }
            
        } catch (error) {
            handleError(error, 'ApiKeyManager.deleteApiKey');
            showToast('Failed to delete API key. Please try again.', 'error');
        }
    }
    
    /**
     * Rename instance for an API key
     * @param {string} keyId - Key ID
     * @param {string} currentName - Current instance name
     */
    async renameInstance(keyId, currentName) {
        logger.info(`Renaming instance for key: ${keyId}`, 'ApiKeyManager');
        
        const newName = prompt('Enter new instance name:', currentName);
        
        if (!newName) {
            return; // User cancelled
        }
        
        if (newName === currentName) {
            return; // No change
        }
        
        try {
            // Get access token
            const accessToken = await this.getAccessToken();
            
            if (!accessToken) {
                showToast('Not authenticated', 'error');
                return;
            }
            
            // Update via API
            const result = await updateInstanceName(accessToken, keyId, newName);
            
            if (result.success) {
                // Update locally
                const key = this.apiKeys.find(k => k.id === keyId);
                if (key) {
                    key.instance_name = newName;
                }
                
                // Re-render
                this.renderApiKeysList();
                
                showToast('Instance name updated successfully!', 'success');
            } else {
                showToast(result.error || 'Failed to update instance name', 'error');
            }
            
        } catch (error) {
            handleError(error, 'ApiKeyManager.renameInstance');
            showToast('Failed to update instance name. Please try again.', 'error');
        }
    }

    /**
     * Handle webhook save for a specific key
     * @param {string} keyId - Key identifier
     */
    async handleWebhookSave(keyId) {
        const context = 'ApiKeyManager.handleWebhookSave';
        try {
            if (!keyId) {
                showToast('Missing key identifier.', 'error');
                return;
            }

            const elements = this.getWebhookElements(keyId);
            if (!elements.urlInput) {
                showToast('Webhook inputs not found.', 'error');
                return;
            }

            const webhookUrl = elements.urlInput.value.trim();
            if (!webhookUrl) {
                showToast('Please enter a webhook URL.', 'error');
                return;
            }

            try {
                // Validate URL format
                new URL(webhookUrl);
            } catch {
                showToast('Please enter a valid webhook URL.', 'error');
                return;
            }

            const headerName = elements.headerNameInput ? elements.headerNameInput.value.trim() : '';
            const headerValue = elements.headerValueInput ? elements.headerValueInput.value.trim() : '';

            if ((headerName && !headerValue) || (!headerName && headerValue)) {
                showToast('Header name and value must both be provided.', 'error');
                return;
            }

            if (headerName && !/^[A-Za-z0-9-]+$/.test(headerName)) {
                showToast('Header name can only contain letters, numbers, and dashes.', 'error');
                return;
            }

            const payload = {
                webhook_url: webhookUrl,
                webhook_headers: headerName ? { [headerName]: headerValue } : {}
            };

            const accessToken = await this.getAccessToken();
            if (!accessToken) {
                showToast('Not authenticated', 'error');
                return;
            }

            this.setButtonLoading(elements.saveButton, 'Saving...');

            if (this.isLegacyKeyMode(keyId)) {
                await updateLegacyWebhookConfig(accessToken, payload);
            } else {
                await updateWebhookConfig(accessToken, keyId, payload);
            }

            const targetKey = this.getKeyByIdentifier(keyId);
            if (targetKey) {
                targetKey.webhook_url = webhookUrl;
                targetKey.webhook_headers = payload.webhook_headers;
            }

            this.expandedWebhookKeys.delete(keyId);
            this.renderApiKeysList();
            showToast('Webhook saved successfully!', 'success');
        } catch (error) {
            handleError(error, context);

            const friendlyMessage = error?.code === 'WEBHOOK_NOT_SUPPORTED'
                ? 'Your backend does not support webhook storage yet. Please update the server.'
                : (error?.message || 'Failed to save webhook.');

            showToast(friendlyMessage, 'error');

            const elements = this.getWebhookElements(keyId);
            this.setButtonLoading(elements.saveButton, null, true);
        }
    }

    /**
     * Handle webhook delete for a specific key
     * @param {string} keyId - Key identifier
     */
    async handleWebhookDelete(keyId) {
        const context = 'ApiKeyManager.handleWebhookDelete';
        try {
            if (!keyId) {
                showToast('Missing key identifier.', 'error');
                return;
            }

            const confirmation = confirm('Remove webhook configuration for this key?');
            if (!confirmation) {
                return;
            }

            const accessToken = await this.getAccessToken();
            if (!accessToken) {
                showToast('Not authenticated', 'error');
                return;
            }

            const elements = this.getWebhookElements(keyId);
            this.setButtonLoading(elements.deleteButton, 'Removing...');

            if (this.isLegacyKeyMode(keyId)) {
                await deleteLegacyWebhookConfig(accessToken);
            } else {
                await deleteWebhookConfig(accessToken, keyId);
            }

            const targetKey = this.getKeyByIdentifier(keyId);
            if (targetKey) {
                targetKey.webhook_url = null;
                targetKey.webhook_headers = {};
            }

            this.expandedWebhookKeys.delete(keyId);
            this.renderApiKeysList();
            showToast('Webhook removed successfully.', 'success');
        } catch (error) {
            handleError(error, context);

            const friendlyMessage = error?.code === 'WEBHOOK_NOT_SUPPORTED'
                ? 'Your backend does not support webhook storage yet. Please update the server.'
                : (error?.message || 'Failed to remove webhook.');

            showToast(friendlyMessage, 'error');

            const elements = this.getWebhookElements(keyId);
            this.setButtonLoading(elements.deleteButton, null, true);
        }
    }

    /**
     * Determine if we should use legacy webhook endpoints
     * @param {string} keyId - Key identifier
     * @returns {boolean}
     */
    isLegacyKeyMode(keyId) {
        if (!this.isMultiKeySupported) {
            return true;
        }
        if (keyId === 'legacy' || !keyId) {
            return true;
        }
        const key = this.getKeyByIdentifier(keyId);
        return Boolean(key?.isLegacy);
    }

    /**
     * Get key object by identifier
     * @param {string} keyId - Key identifier
     * @returns {Object|undefined}
     */
    getKeyByIdentifier(keyId) {
        return this.apiKeys.find(k => (k.id || 'legacy') === keyId);
    }

    /**
     * Grab DOM references for webhook inputs/buttons
     * @param {string} keyId - Key identifier
     * @returns {{urlInput: HTMLInputElement|null, headerNameInput: HTMLInputElement|null, headerValueInput: HTMLInputElement|null, saveButton: HTMLButtonElement|null, deleteButton: HTMLButtonElement|null}}
     */
    getWebhookElements(keyId) {
        return {
            urlInput: /** @type {HTMLInputElement|null} */ (document.getElementById(`webhook-url-${keyId}`)),
            headerNameInput: /** @type {HTMLInputElement|null} */ (document.getElementById(`webhook-header-name-${keyId}`)),
            headerValueInput: /** @type {HTMLInputElement|null} */ (document.getElementById(`webhook-header-value-${keyId}`)),
            saveButton: /** @type {HTMLButtonElement|null} */ (document.querySelector(`.btn-save-webhook[data-key-id="${keyId}"]`)),
            deleteButton: /** @type {HTMLButtonElement|null} */ (document.querySelector(`.btn-delete-webhook[data-key-id="${keyId}"]`))
        };
    }

    /**
     * Toggle loading state for a button
     * @param {HTMLButtonElement|null} button - Target button
     * @param {string|null} loadingText - Text while loading, null to reset
     * @param {boolean} reset - Force reset regardless of DOM state
     */
    setButtonLoading(button, loadingText, reset = false) {
        if (!button) return;

        if (loadingText) {
            button.dataset.originalText = button.textContent || '';
            button.textContent = loadingText;
            button.disabled = true;
            button.style.opacity = '0.7';
            button.style.cursor = 'not-allowed';
        } else if (reset) {
            if (button.dataset.originalText) {
                button.textContent = button.dataset.originalText;
                delete button.dataset.originalText;
            }
            button.disabled = false;
            button.style.opacity = '1';
            button.style.cursor = 'pointer';
        }
    }

    /**
     * Remove webhook expansion entries for keys that no longer exist
     */
    cleanupExpandedWebhookStates() {
        const validIds = new Set(this.apiKeys.map(key => key.id || 'legacy'));
        this.expandedWebhookKeys.forEach(id => {
            if (!validIds.has(id)) {
                this.expandedWebhookKeys.delete(id);
            }
        });
    }
}
