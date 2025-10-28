//@ts-check

/**
 * Type definitions for storage-related data structures.
 * 
 * @fileoverview Storage type definitions that can be used with JSDoc annotations
 * for improved type safety and autocompletion.
 */

/**
 * Storage key-value pair
 * @template T
 * @typedef {Object} StorageKeyValue
 * @property {string} key - The storage key
 * @property {T} value - The stored value
 */

/**
 * Storage get result
 * @template T
 * @typedef {Object} StorageGetResult
 * @property {T} [value] - The retrieved value, if present
 * @property {boolean} success - Whether the operation was successful
 * @property {string} [error] - Error message if unsuccessful
 */

/**
 * Storage set result
 * @typedef {Object} StorageSetResult
 * @property {boolean} success - Whether the operation was successful
 * @property {string} [error] - Error message if unsuccessful
 */

/**
 * Chrome storage areas
 * @typedef {'local'|'session'|'sync'|'managed'} StorageArea
 */

/**
 * Runtime state object 
 * @typedef {Object.<string, any>} RuntimeState
 */

/**
 * Default cache expiration times (ms)
 * @typedef {Object} CacheExpirationConfig
 * @property {number} SHORT - Short-lived cache (e.g., 5 minutes)
 * @property {number} MEDIUM - Medium-lived cache (e.g., 1 hour) 
 * @property {number} LONG - Long-lived cache (e.g., 24 hours)
 * @property {number} PERMANENT - No expiration
 */

// Reexport AuthData type for convenience
/** @typedef {import('./auth.types.js').AuthData} AuthData */

// Export nothing - this file is only for JSDoc type definitions
export {}; 