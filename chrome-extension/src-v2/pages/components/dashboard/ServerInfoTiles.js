//@ts-check
/// <reference types="chrome"/>

import { logger } from '../../../shared/utils/logger.js';
import { handleError } from '../../../shared/utils/error-handler.js';
import appConfig from '../../../shared/config/app.config.js';

/**
 * ServerInfoTiles component for displaying server information and announcements
 */
export class ServerInfoTiles {
    /**
     * @type {HTMLElement|null}
     */
    container = null;
    
    /**
     * @type {any|null}
     */
    serverInfo = null;
    
    /**
     * Creates a new ServerInfoTiles instance
     * @param {HTMLElement} container - Container element to render tiles in
     */
    constructor(container) {
        this.container = container;
        this.init();
    }
    
    /**
     * Initializes the component
     */
    async init() {
        logger.info('Initializing ServerInfoTiles component', 'ServerInfoTiles');
        
        try {
            await this.fetchServerInfo();
            this.render();
        } catch (error) {
            handleError(error, 'ServerInfoTiles.init');
            logger.warn('Failed to load server info, continuing anyway', 'ServerInfoTiles');
        }
    }
    
    /**
     * Fetches server information from the backend
     */
    async fetchServerInfo() {
        try {
            const serverUrls = await appConfig.getServerUrls();
            const infoUrl = `${serverUrls.apiUrl}/api/v1/server/info`;
            
            logger.info(`[SERVER_INFO] Fetching from: ${infoUrl}`, 'fetchServerInfo');
            
            const response = await fetch(infoUrl);
            
            if (!response.ok) {
                throw new Error(`Failed to fetch server info: ${response.status}`);
            }
            
            this.serverInfo = await response.json();
            logger.info('[SERVER_INFO] Successfully fetched server info', 'fetchServerInfo');
        } catch (error) {
            handleError(error, 'ServerInfoTiles.fetchServerInfo');
            // Set default info if fetch fails
            this.serverInfo = {
                server_name: "Server Information Unavailable",
                is_default_server: true,
                restrictions: [],
                whats_new: []
            };
        }
    }
    
    /**
     * Renders the tiles
     */
    render() {
        if (!this.container || !this.serverInfo) return;
        
        logger.info('[SERVER_INFO] Rendering tiles', 'render');
        
        // Clear existing content
        this.container.innerHTML = '';
        
        // Render restrictions tile if there are any
        if (this.serverInfo.restrictions && this.serverInfo.restrictions.length > 0) {
            const restrictionsTile = this.createRestrictionsTile(this.serverInfo.restrictions[0]);
            this.container.appendChild(restrictionsTile);
        }
        
        // Render what's new tile if there are updates (second to last)
        if (this.serverInfo.whats_new && this.serverInfo.whats_new.length > 0) {
            const whatsNewTile = this.createWhatsNewTile(this.serverInfo.whats_new);
            this.container.appendChild(whatsNewTile);
        }
        
        // Render LinkedIn limits tile (last tile)
        if (this.serverInfo.linkedin_limits && this.serverInfo.linkedin_limits.length > 0) {
            const limitsTile = this.createLinkedInLimitsTile(this.serverInfo.linkedin_limits);
            this.container.appendChild(limitsTile);
        }
    }
    
    /**
     * Creates a restrictions tile
     * @param {any} restriction - Restriction object
     * @returns {HTMLElement} The tile element
     */
    createRestrictionsTile(restriction) {
        const tile = document.createElement('div');
        tile.className = 'card';
        tile.style.borderLeft = '4px solid #f59e0b';
        
        tile.innerHTML = `
            <div class="card-title" style="color: #f59e0b;">⚠️ ${restriction.title}</div>
            <div class="card-content">
                <p style="color: #2c3e50; line-height: 1.6;">${restriction.message}</p>
            </div>
        `;
        
        return tile;
    }
    
    /**
     * Creates a what's new tile
     * @param {Array<any>} updates - Array of update objects
     * @returns {HTMLElement} The tile element
     */
    createWhatsNewTile(updates) {
        const tile = document.createElement('div');
        tile.className = 'card';
        tile.style.borderLeft = '4px solid #10b981';
        
        // Get the latest update
        const latest = updates[0];
        
        let highlightsHtml = '';
        if (latest.highlights && latest.highlights.length > 0) {
            highlightsHtml = '<ul style="margin: 0.5rem 0 0 1.5rem; padding: 0;">';
            latest.highlights.forEach(highlight => {
                highlightsHtml += `<li style="margin: 0.25rem 0;">${highlight}</li>`;
            });
            highlightsHtml += '</ul>';
        }
        
        tile.innerHTML = `
            <div class="card-title" style="color: #10b981;">🎉 What's New</div>
            <div class="card-content">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                    <strong style="font-size: 16px; color: #2c3e50;">${latest.title}</strong>
                    <span style="background: #10b981; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 12px; font-weight: 600;">${latest.version}</span>
                </div>
                <p style="color: #5a6c7d; margin-bottom: 0.5rem;">${latest.description}</p>
                ${highlightsHtml}
                <p style="margin-top: 0.75rem; font-size: 13px; color: #7f8c9a;">Released: ${latest.date}</p>
            </div>
        `;
        
        return tile;
    }
    
    /**
     * Creates a LinkedIn limits tile
     * @param {Array<any>} limits - Array of limit objects
     * @returns {HTMLElement} The tile element
     */
    createLinkedInLimitsTile(limits) {
        const tile = document.createElement('div');
        tile.className = 'card';
        tile.style.borderLeft = '4px solid #0077b5';
        
        let limitsHtml = '<div style="display: flex; flex-direction: column; gap: 0.75rem;">';
        
        limits.forEach(limit => {
            const limitText = limit.recommended 
                ? `<strong style="color: #0077b5;">${limit.limit}</strong> <span style="color: #7f8c9a;">(rec. ${limit.recommended})</span>`
                : `<strong style="color: #0077b5;">${limit.limit}</strong>`;
            
            limitsHtml += `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #2c3e50;">${limit.label}:</span>
                    <span>${limitText} / ${limit.period}</span>
                </div>
            `;
        });
        
        limitsHtml += '</div>';
        
        tile.innerHTML = `
            <div class="card-title" style="color: #0077b5;">📊 LinkedIn Limits</div>
            <div class="card-content">
                ${limitsHtml}
            </div>
        `;
        
        return tile;
    }
}

