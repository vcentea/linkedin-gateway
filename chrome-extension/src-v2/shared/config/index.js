//@ts-check

/**
 * Configuration module entry point
 * 
 * @fileoverview Re-exports all configuration modules for easier importing
 */

export { default as appConfig } from './app.config.js';
export { default as apiConfig } from './api.config.js';
export { default as websocketConfig } from './websocket.config.js';

// For backward compatibility
export * from './app.config.js'; 