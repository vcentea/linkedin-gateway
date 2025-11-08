//@ts-check

/**
 * Date utility functions for the Chrome extension
 * 
 * @fileoverview This file contains date-related utility functions used throughout the extension.
 */

import { logger } from './logger.js';

/**
 * Format a date string to a more readable format
 * @param {string} dateString - Date string to format
 * @returns {string} Formatted date string
 */
export function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        });
    } catch (error) {
        logger.error(`Error formatting date: ${error instanceof Error ? error.message : String(error)}`);
        return dateString; // Return original if formatting fails
    }
}

/**
 * Calculate the time difference between now and a given date
 * @param {string|Date} date - The date to compare with now
 * @returns {string} A human-readable string representing the time difference
 */
export function timeAgo(date) {
    if (!date) return '';
    
    try {
        const dateObj = date instanceof Date ? date : new Date(date);
        const now = new Date();
        
        const secondsAgo = Math.floor((now.getTime() - dateObj.getTime()) / 1000);
        
        if (secondsAgo < 60) return 'just now';
        if (secondsAgo < 3600) return `${Math.floor(secondsAgo / 60)} minutes ago`;
        if (secondsAgo < 86400) return `${Math.floor(secondsAgo / 3600)} hours ago`;
        if (secondsAgo < 2592000) return `${Math.floor(secondsAgo / 86400)} days ago`;
        if (secondsAgo < 31536000) return `${Math.floor(secondsAgo / 2592000)} months ago`;
        
        return `${Math.floor(secondsAgo / 31536000)} years ago`;
    } catch (error) {
        logger.error(`Error calculating time ago: ${error instanceof Error ? error.message : String(error)}`);
        return '';
    }
} 