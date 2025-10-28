//@ts-check

/**
 * General utility functions for the Chrome extension
 * 
 * @fileoverview This file contains general utility functions used throughout the extension.
 * Currently contains the randomDelay function for introducing controlled timing delays.
 */

/**
 * Waits for a random amount of time between minMs and maxMs milliseconds.
 * @param {number} minMs - Minimum delay in milliseconds.
 * @param {number} maxMs - Maximum delay in milliseconds.
 * @returns {Promise<void>} A promise that resolves after the delay.
 */
export function randomDelay(minMs, maxMs) {
    const delay = Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
    // Using console.log directly here as logger might introduce circular dependency risk
    // or might not be suitable for this low-level timing log.
    console.log(`Waiting for ${delay}ms...`); 
    return new Promise(resolve => setTimeout(resolve, delay));
} 