//@ts-nocheck // Disabled for debugging
/// <reference types="chrome"/>

import { MESSAGE_TYPES } from '../../shared/constants/message-types.js';
import { logger } from '../../shared/utils/logger.js';
import { handleError, createError } from '../../shared/utils/error-handler.js';
import { formatDate } from '../../shared/utils/date.utils.js';
import { sendMessageToBackground } from '../../shared/utils/chrome-messaging.js';
import { Header } from '../components/common/Header.js';
import { LinkedInStatus } from '../components/dashboard/LinkedInStatus.js';
import { GeminiStatus } from '../components/dashboard/GeminiStatus.js'; // Gemini AI (v1.2.0)
import { DashboardCard } from '../components/dashboard/DashboardCard.js';
import { ApiStatus } from '../components/dashboard/ApiStatus.js';
import { ApiKeyManager } from '../components/dashboard/ApiKeyManager.js';
import { ServerSettings } from '../components/dashboard/ServerSettings.js';
import { ServerInfoTiles } from '../components/dashboard/ServerInfoTiles.js';

// DOM Elements
/** @type {HTMLElement|null} */
const loadingIndicator = document.getElementById('loadingIndicator');
/** @type {HTMLElement|null} */
const errorMessage = document.getElementById('errorMessage');
/** @type {HTMLElement|null} */
const dashboard = document.getElementById('dashboard');

// Component instances
/** @type {Header|null} */
let header;
/** @type {LinkedInStatus|null} */
let linkedInStatus;
/** @type {GeminiStatus|null} */
let geminiStatus; // Gemini AI (v1.2.0)
/** @type {DashboardCard|null} */
let dashboardCard;
/** @type {ApiStatus|null} */
let apiStatus;
/** @type {ApiKeyManager|null} */
let apiKeyManager;

/**
 * Initialize the dashboard
 */
async function init() {
    logger.info('Dashboard initializing', 'dashboard/index');
    
    try {
        // Check authentication first before initializing any components
        const isAuthenticated = await checkAuthentication();
        
        if (!isAuthenticated) {
            // Redirect to login page if not authenticated
            logger.info('User not authenticated, redirecting to login', 'dashboard/index');
            window.location.href = '/login.html';
            return;
        }
        
        // Only initialize components if authenticated
        header = new Header();
        linkedInStatus = new LinkedInStatus();
        geminiStatus = new GeminiStatus(); // Gemini AI (v1.2.0)
        dashboardCard = new DashboardCard();
        
        // Load user profile to populate the dashboard
        loadUserProfile();
    } catch (error) {
        handleError(error, 'dashboard/index.init');
        showError('Failed to initialize dashboard: ' + error.message);
    }
}

/**
 * Check if the user is authenticated
 * @returns {Promise<boolean>} True if authenticated, false otherwise
 */
async function checkAuthentication() {
    try {
        logger.info('Checking authentication status', 'dashboard/index');
        
        const response = await sendMessageToBackground({ type: MESSAGE_TYPES.GET_USER_PROFILE });
        
        if (!response || !response.authenticated) {
            logger.info('Not authenticated', 'dashboard/index');
            return false;
        }
        
        logger.info('User is authenticated', 'dashboard/index');
        return true;
    } catch (error) {
        handleError(error, 'dashboard/index.checkAuthentication');
        return false;
    }
}

/**
 * Load user profile data
 */
async function loadUserProfile() {
    logger.info('Requesting user profile from background service worker', 'dashboard/index');
    
    try {
        // Check if DOM elements exist
        if (!errorMessage || !loadingIndicator || !dashboard) {
            throw createError('DomError', 'Required DOM elements not found', 'dashboard/index.loadUserProfile');
        }
        
        // Hide any previous error messages
        errorMessage.style.display = 'none';
        
        // Show loading indicator
        loadingIndicator.style.display = 'block';
        dashboard.style.display = 'none';
        
        // Request user profile from background service worker using sendMessageToBackground
        // Use a timeout to prevent indefinite hanging if backend is down
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Request timeout')), 5000);
        });
        
        const response = await Promise.race([
            sendMessageToBackground({ type: MESSAGE_TYPES.GET_USER_PROFILE }),
            timeoutPromise
        ]);
        
        logger.info('User profile response received', 'dashboard/index');
        logger.info(`Dashboard received profile response: ${JSON.stringify(response)}`, 'dashboard/index');
        
        if (!response || !response.authenticated) {
            logger.info('Not authenticated or invalid response. Redirecting to login.', 'dashboard/index');
            // Redirect to login page if not authenticated
            window.location.href = '/login.html';
            return;
        }
        
        // We have a valid user profile, display it
        displayDashboard(response.userData);
    } catch (error) {
        handleError(error, 'dashboard/index.loadUserProfile');
        showError('Could not load your profile. Please try again later or re-login.');
    }
}

/**
 * Display the dashboard with user data
 * @param {any} userData - User data object from the API
 */
function displayDashboard(userData) {
    logger.info('Displaying dashboard with user data', 'dashboard/index');
    
    try {
        if (!loadingIndicator || !dashboard || !header) {
            throw createError('DomError', 'Required DOM elements not found in displayDashboard', 'dashboard/index.displayDashboard');
        }
        
        // Update header with user info
        header.updateUserInfo(userData);
        
        // Update account summary in consolidated tile
        const accountEmail = document.getElementById('account-email');
        const accountCreated = document.getElementById('account-created');
        if (accountEmail) {
            accountEmail.textContent = userData.email || 'N/A';
        }
        if (accountCreated) {
            accountCreated.textContent = formatDate(userData.created_at) || 'N/A';
        }
        
        // Hide loading indicator
        loadingIndicator.style.display = 'none';
        
        // Show dashboard
        dashboard.style.display = 'grid';
        
        // Initialize server info tiles
        const serverInfoContainer = document.getElementById('server-info-tiles-container');
        const serverInfoSection = document.getElementById('server-info-section');
        if (serverInfoContainer && serverInfoSection) {
            new ServerInfoTiles(serverInfoContainer);
            // Show the server info section
            serverInfoSection.style.display = 'block';
        }
        
        // Add dashboard cards
        loadDashboardContent(userData);
        
        // Initialize API status component
        apiStatus = new ApiStatus();
        
        // Initialize API key manager
        apiKeyManager = new ApiKeyManager();
        
        // Version checking is now handled by the ServerSettings component
        
        logger.info('Dashboard displayed successfully', 'dashboard/index');
    } catch (error) {
        handleError(error, 'dashboard/index.displayDashboard');
        showError('Could not display dashboard: ' + error.message);
    }
}

/**
 * Load dashboard content with cards
 * @param {any} userData - User data object from the API
 */
function loadDashboardContent(userData) {
    logger.info('Loading dashboard content', 'dashboard/index');
    
    try {
        if (!dashboardCard) {
            throw createError('ComponentError', 'DashboardCard component not initialized', 'dashboard/index.loadDashboardContent');
        }
        
        // Add dashboard cards based on user data and permissions
        // Account Summary is now consolidated with Services Availability tile in HTML
        
        // Add more cards based on the application features
        dashboardCard.addCard('Getting Started', `
            <p>Tutorials, API Reference, Examples</p>
            <p>Start exploring</p>
            <p><a href="https://ainnovate.tech/lg-api-docs/" target="_blank" rel="noopener noreferrer" class="doc-link">📚 View API Documentation and Examples</a></p>
        `);
        
        // Add Server Settings card
        dashboardCard.addCard('Settings', `
            <div id="server-settings-container"></div>
        `);
        
        // Add API Key Management card (full width) - placed before status tiles
        dashboardCard.addCard('API Key Management', `
            <div id="api-key-container"></div>
        `, { fullWidth: true });
        
        // Initialize ServerSettings component
        const serverSettingsContainer = document.getElementById('server-settings-container');
        if (serverSettingsContainer) {
            new ServerSettings(serverSettingsContainer);
        }
        
        logger.info('Dashboard content loaded successfully', 'dashboard/index');
    } catch (error) {
        handleError(error, 'dashboard/index.loadDashboardContent');
        showError('Could not load dashboard content: ' + error.message);
    }
}

// Version checking is now handled by the ServerSettings component

/**
 * Show error message
 * @param {string} message - Error message to display
 */
function showError(message) {
    logger.error(`Error displayed: ${message}`, undefined, 'dashboard/index'); // Pass undefined for optional error object
    
    if (!loadingIndicator || !errorMessage) {
        console.error('Required DOM elements not found in showError');
        return;
    }
    
    loadingIndicator.style.display = 'none';
    errorMessage.textContent = `Error: ${message}`;
    errorMessage.style.display = 'block';
}

// Initialize on DOM content loaded
document.addEventListener('DOMContentLoaded', init); 