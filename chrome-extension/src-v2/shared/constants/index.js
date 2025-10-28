//@ts-check

/**
 * Re-exports all constants from the constants directory
 * 
 * @fileoverview Central export point for all constants to simplify imports
 */

export * from './message-types.js';
export * from './storage-keys.js';
export * from './errors.js';

// Note: The old constants.js had a duplicate definition of GET_CSRF_TOKEN
// in both MESSAGE_TYPES and INTERNAL_MESSAGE_TYPES.
// We've eliminated this duplication by keeping it only in MESSAGE_TYPES. 