//@ts-check

import { logger } from '../../../shared/utils/logger.js';
import { handleError, createError } from '../../../shared/utils/error-handler.js';

/**
 * DashboardCard component for creating and managing dashboard cards
 */
export class DashboardCard {
    /** 
     * @type {HTMLElement|null} 
     */
    dashboard = null;
    
    /**
     * Create a new DashboardCard component
     */
    constructor() {
        this.dashboard = /** @type {HTMLElement|null} */ (document.getElementById('dashboard'));
        
        if (!this.dashboard) {
            logger.warn('Dashboard element not found during DashboardCard initialization', 'DashboardCard');
        }
    }
    
    /**
     * Add a new card to the dashboard
     * @param {string} title - Card title
     * @param {string} content - HTML content for the card
     * @param {object} [options={}] - Optional settings like actions
     * @param {Array<{text: string, onClick?: (event: Event) => void, primary?: boolean}>} [options.actions] - Action buttons for the card
     * @param {boolean} [options.fullWidth] - Make the card span full width
     * @returns {HTMLElement|null} - The created card element or null if dashboard not found
     */
    addCard(title, content, options = {}) {
        try {
            logger.info(`Adding dashboard card: ${title}`, 'DashboardCard');
        
        if (!this.dashboard) {
                throw createError('DomError', 'Dashboard element not found', 'DashboardCard.addCard');
        }
        
        // Create card element
        const card = document.createElement('div');
        card.className = options.fullWidth ? 'card card-wide' : 'card';
        
        // Add title
        const titleElement = document.createElement('div');
        titleElement.className = 'card-title';
        titleElement.textContent = title;
        card.appendChild(titleElement);
        
        // Add content
        const contentElement = document.createElement('div');
        contentElement.className = 'card-content';
        contentElement.innerHTML = content;
        card.appendChild(contentElement);
        
        // Add actions if provided
            if (options.actions && Array.isArray(options.actions)) {
                this.addCardActions(card, options.actions);
            }
            
            // Add to dashboard
            this.dashboard.appendChild(card);
            
            return card;
        } catch (error) {
            handleError(error, 'DashboardCard.addCard');
            return null;
        }
    }
    
    /**
     * Add action buttons to a card
     * @param {HTMLElement} card - The card element to add actions to
     * @param {Array<{text: string, onClick?: (event: Event) => void, primary?: boolean}>} actions - Action buttons configuration
     */
    addCardActions(card, actions) {
        try {
            const actionsContainer = document.createElement('div');
            actionsContainer.className = 'card-actions';
            actionsContainer.style.marginTop = '20px';
            actionsContainer.style.display = 'flex';
            actionsContainer.style.gap = '12px';
            actionsContainer.style.flexWrap = 'wrap';
            
            actions.forEach(action => {
                const button = document.createElement('button');
                button.textContent = action.text;
                button.className = action.primary ? 'card-btn card-btn-primary' : 'card-btn';
                button.style.backgroundColor = action.primary ? '#0077b5' : '#ffffff';
                button.style.color = action.primary ? 'white' : '#5a6c7d';
                button.style.border = action.primary ? 'none' : '1px solid #e0e7ee';
                button.style.padding = '10px 20px';
                button.style.borderRadius = '8px';
                button.style.cursor = 'pointer';
                button.style.fontWeight = '600';
                button.style.fontSize = '14px';
                button.style.transition = 'all 0.2s ease';
                
                button.addEventListener('mouseover', () => {
                    if (action.primary) {
                        button.style.backgroundColor = '#006097';
                        button.style.transform = 'translateY(-1px)';
                        button.style.boxShadow = '0 4px 8px rgba(0,119,181,0.2)';
                    } else {
                        button.style.backgroundColor = '#f8fafc';
                        button.style.borderColor = '#cbd5e0';
                    }
                });
                
                button.addEventListener('mouseout', () => {
                    if (action.primary) {
                        button.style.backgroundColor = '#0077b5';
                        button.style.transform = 'translateY(0)';
                        button.style.boxShadow = 'none';
                    } else {
                        button.style.backgroundColor = '#ffffff';
                        button.style.borderColor = '#e0e7ee';
                    }
                });
                
                if (action.onClick && typeof action.onClick === 'function') {
                    button.addEventListener('click', action.onClick);
                }
                
                actionsContainer.appendChild(button);
            });
            
            card.appendChild(actionsContainer);
        } catch (error) {
            handleError(error, 'DashboardCard.addCardActions');
        }
    }
    
    /**
     * Clear all cards from the dashboard
     */
    clearCards() {
        try {
            logger.info('Clearing all dashboard cards', 'DashboardCard');
            
            if (!this.dashboard) {
                throw createError('DomError', 'Dashboard element not found', 'DashboardCard.clearCards');
            }
            
            this.dashboard.innerHTML = '';
        } catch (error) {
            handleError(error, 'DashboardCard.clearCards');
        }
    }
} 