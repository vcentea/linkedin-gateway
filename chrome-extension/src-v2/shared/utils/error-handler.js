//@ts-check

/**
 * Centralized Error Handling Module
 *
 * @fileoverview Provides a handleError function for consistent error logging,
 * custom error classes for different error types, and serialization utilities.
 */

import { logger } from './logger.js';

/**
 * Base error class for domain-specific errors.
 */
export class BaseError extends Error {
    /** @type {string | undefined} */
    context;
    /** @type {any} */
    details;

    /**
     * @param {string} message
     * @param {string} [context]
     * @param {any} [details]
     */
    constructor(message, context, details) {
        super(message);
        this.name = this.constructor.name;
        if (context) this.context = context;
        if (details) this.details = details;
        // Maintains proper stack trace in V8
        if (Error.captureStackTrace) {
            Error.captureStackTrace(this, this.constructor);
        }
    }
}

/**
 * API error class for backend/API errors.
 */
export class ApiError extends BaseError {
    /** @type {number | undefined} */
    statusCode;

    /**
     * @param {string} message
     * @param {number} [statusCode]
     * @param {string} [context]
     * @param {any} [details]
     */
    constructor(message, statusCode, context, details) {
        super(message, context, details);
        this.statusCode = statusCode;
    }
}

/**
 * Auth error class for authentication/authorization errors.
 */
export class AuthError extends BaseError {}

/**
 * WebSocket error class.
 */
export class WebSocketError extends BaseError {}

/**
 * Content script related error class.
 */
export class ContentScriptError extends BaseError {}

/**
 * Storage related error class.
 */
export class StorageError extends BaseError {}

/**
 * Configuration related error class.
 */
export class ConfigError extends BaseError {}


/**
 * Handles errors in a consistent way across the extension.
 * Logs the error using the centralized logger and provides context.
 * 
 * @param {Error|any} error - The error object or value.
 * @param {string} [context] - Optional context (e.g., 'module.functionName').
 */
export function handleError(error, context = 'unknown') {
    let errorMessage = 'An unknown error occurred';
    let errorObject = null;
    let errorContext = context;

    if (error instanceof Error) {
        errorMessage = error.message;
        errorObject = error;
        // Use context from BaseError if available and none provided
        if (error instanceof BaseError && error.context && context === 'unknown') {
            errorContext = error.context;
        }
        // Add specific details if available
        if (error instanceof ApiError && error.statusCode) {
            errorMessage += ` (Status: ${error.statusCode})`;
        }
        if (error instanceof BaseError && error.details) {
            errorMessage += ` | Details: ${JSON.stringify(error.details)}`;
        }
    } else if (typeof error === 'string') {
        errorMessage = error;
    } else {
        // Attempt to stringify other types, could be risky
        try {
            errorMessage = `Non-Error thrown: ${JSON.stringify(error)}`;
        } catch (e) {
            errorMessage = 'Non-Error thrown, unable to stringify';
        }
    }

    // Log the error using the logger
    logger.error(errorMessage, errorObject ?? undefined, errorContext);
}

/**
 * Creates a specific type of error.
 * @template {string} T Type name string (e.g., 'ApiError') corresponding to a key in ErrorClasses.
 * @param {T} type - The type of error (e.g., 'ApiError').
 * @param {string} message - The error message.
 * @param {any[]} args - Additional arguments for the specific error constructor.
 * @returns {Error} An instance of the specified error class.
 */
export function createError(type, message, ...args) {
    // Runtime check to ensure type is a valid key
    const errorKey = /** @type {keyof typeof ErrorClasses} */ (Object.keys(ErrorClasses).includes(type) ? type : 'BaseError');
    const ErrorClass = ErrorClasses[errorKey];
    // @ts-ignore Dynamically creating error, TS can't fully track this easily
    return new ErrorClass(message, ...args);
}

/**
 * Maps error type strings to their classes.
 */
const ErrorClasses = {
    BaseError,
    ApiError,
    AuthError,
    WebSocketError,
    ContentScriptError,
    StorageError,
    ConfigError
};

/**
 * Serializes an Error object into a plain object suitable for message passing.
 * @param {Error | any} error
 * @returns {{name: string, message: string, stack?: string, context?: string, details?: any, statusCode?: number} | { error: string }}
 */
export function serializeError(error) {
    if (error instanceof Error) {
        const serialized = {
            name: error.name,
            message: error.message,
            stack: error.stack,
        };
        // Add custom properties if they exist
        if (error instanceof BaseError && error.context) serialized.context = error.context;
        if (error instanceof BaseError && error.details) serialized.details = error.details;
        if (error instanceof ApiError && error.statusCode) serialized.statusCode = error.statusCode;
        // @ts-ignore
        return serialized;
    } else {
        // Handle non-Error types
        try {
            return { error: `Non-Error thrown: ${JSON.stringify(error)}` };
        } catch (e) {
            return { error: 'Non-Error thrown, unable to serialize' };
        }
    }
}

// Attach to window for easier debugging in console (optional)
// if (typeof window !== 'undefined') {
//     window.ExtensionErrors = { BaseError, ApiError, AuthError, WebSocketError, ContentScriptError, StorageError, ConfigError };
//     window.handleExtensionError = handleError;
// } 