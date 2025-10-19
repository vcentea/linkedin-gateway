//@ts-check

/**
 * Centralized Logging System
 * 
 * @fileoverview Provides a basic logger with levels (INFO, WARN, ERROR)
 * for consistent logging throughout the extension.
 */

/**
 * @typedef {'INFO' | 'WARN' | 'ERROR'} LogLevel
 */

/**
 * Formats the log message with timestamp, level, and context.
 * @param {LogLevel} level - The log level.
 * @param {string} message - The message to log.
 * @param {string} [context=''] - Optional context identifier.
 * @returns {string} Formatted log message.
 */
function formatMessage(level, message, context = '') {
    const timestamp = new Date().toISOString();
    const contextPrefix = context ? `[${context}] ` : '';
    return `[${timestamp}] [${level}] ${contextPrefix}${message}`;
}

/**
 * Basic logger instance.
 */
export const logger = {
    /**
     * Logs an informational message.
     * @param {string} message - The message to log.
     * @param {string} [context=''] - Optional context.
     */
    info: (message, context = '') => {
        console.log(formatMessage('INFO', message, context));
    },

    /**
     * Logs a warning message.
     * @param {string} message - The message to log.
     * @param {string} [context=''] - Optional context.
     */
    warn: (message, context = '') => {
        console.warn(formatMessage('WARN', message, context));
    },

    /**
     * Logs an error message.
     * @param {string} message - The message to log.
     * @param {Error} [error] - Optional error object.
     * @param {string} [context=''] - Optional context.
     */
    error: (message, error, context = '') => {
        let fullMessage = message;
        if (error) {
            fullMessage += ` | Error: ${error.message}`;
            if (error.stack) {
                fullMessage += `\nStack: ${error.stack}`;
            }
        }
        console.error(formatMessage('ERROR', fullMessage, context));
    }
}; 