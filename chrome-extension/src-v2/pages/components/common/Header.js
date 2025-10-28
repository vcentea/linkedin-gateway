/// <reference types="chrome"/>

import { MESSAGE_TYPES } from '../../../shared/constants/message-types.js';
import { logger } from '../../../shared/utils/logger.js';

// Header Component
/**
 * Manages the header UI, including user information and logout functionality.
 */
export class Header {
    /** @type {HTMLImageElement|null} */
    userAvatar = null;
    /** @type {HTMLElement|null} */
    userName = null;
    /** @type {HTMLButtonElement|null} */
    logoutBtn = null;
    
    constructor() {
        // DOM Elements
        this.userAvatar = /** @type {HTMLImageElement|null} */ (document.getElementById('userAvatar'));
        this.userName = document.getElementById('userName');
        this.logoutBtn = /** @type {HTMLButtonElement|null} */ (document.getElementById('logoutBtn'));
        
        // Initialize the component
        this.init();
    }
    
    init() {
        logger.info('Initializing Header component', 'Header.js:init');
        
        // Add event listeners if logout button exists
        if (this.logoutBtn) {
            this.logoutBtn.addEventListener('click', this.handleLogout.bind(this));
        } else {
            logger.warn('Logout button not found in the DOM, skipping event listener', 'Header.js:init');
        }
    }
    
    /**
     * Update user info in the header.
     * @param {Object} userData - User data object.
     * @param {string} [userData.name] - User's name.
     * @param {string} [userData.email] - User's email.
     * @param {string} [userData.profile_picture_url] - URL of the user's profile picture.
     */
    updateUserInfo(userData) {
        logger.info('Updating header with user data', 'Header.js:updateUserInfo');
        
        // Set user name if element exists
        if (this.userName) {
            this.userName.textContent = userData.name || userData.email || 'User';
        }
        
        // Set user avatar if element exists
        if (this.userAvatar) {
            // SVG placeholder as data URI - user icon
            const placeholderSvg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'%3E%3Crect fill='%23ddd' width='40' height='40'/%3E%3Ccircle cx='20' cy='14' r='6' fill='%23999'/%3E%3Cpath d='M 8 32 Q 8 24 20 24 Q 32 24 32 32 Z' fill='%23999'/%3E%3C/svg%3E";
            
            // Use profile picture if available, otherwise use placeholder
            this.userAvatar.src = userData.profile_picture_url || placeholderSvg;
            
            // Add error handler to fallback to placeholder if image fails to load
            this.userAvatar.onerror = () => {
                logger.warn('Failed to load user avatar, using placeholder', 'Header.js:updateUserInfo');
                this.userAvatar.src = placeholderSvg;
                // Remove error handler to prevent infinite loop
                this.userAvatar.onerror = null;
            };
        }
    }
    
    /**
     * Handle logout button click by sending a message to the background script.
     */
    handleLogout() {
        logger.info('Logout button clicked', 'Header.js:handleLogout');
        
        if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
            chrome.runtime.sendMessage({ type: MESSAGE_TYPES.LOGOUT_USER }, (response) => {
                if (chrome.runtime.lastError) {
                    logger.error(`Error during logout message: ${chrome.runtime.lastError.message}`, 'Header.js:handleLogout');
                } else {
                    logger.info(`Logout response: ${JSON.stringify(response)}`, 'Header.js:handleLogout');
                }
                
                // Force complete cleanup and redirect to login page
                // Using chrome.runtime.getURL to ensure correct path in extension context
                logger.info('Redirecting to login page after logout', 'Header.js:handleLogout');
                
                // Use location.replace to prevent back button from going to dashboard
                window.location.replace(chrome.runtime.getURL('login.html'));
            });
        } else {
            logger.error('Chrome runtime is not available. Cannot perform logout.', 'Header.js:handleLogout');
            // Attempt to redirect anyway, might fail if not in extension context
            try {
                window.location.replace('/login.html'); // Fallback path
            } catch (e) {
                logger.error('Failed to redirect using fallback path.', 'Header.js:handleLogout');
            }
        }
    }
} 