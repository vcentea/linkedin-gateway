//@ts-check

/**
 * Type definitions for message-related data structures.
 * 
 * @fileoverview Message type definitions that can be used with JSDoc annotations
 * for improved type safety and autocompletion.
 */

/**
 * Base message interface
 * @typedef {Object} Message
 * @property {string} type - Message type identifier from MESSAGE_TYPES constants
 * @property {Object} [data] - Message payload data
 */

/**
 * Auth-related messages
 */

/**
 * Get user profile message
 * @typedef {Message} GetUserProfileMessage
 * @property {'GET_USER_PROFILE'} type - Message type
 */

/**
 * Logout user message
 * @typedef {Message} LogoutUserMessage
 * @property {'LOGOUT_USER'} type - Message type
 */

/**
 * Auth session message
 * @typedef {Message} AuthSessionMessage
 * @property {'auth_session'} type - Message type
 * @property {Object} data - Auth session data
 * @property {string} data.token - Authentication token
 * @property {string} data.userId - User ID
 */

/**
 * API-related messages
 */

/**
 * API request message
 * @typedef {Message} ApiRequestMessage
 * @property {'API_REQUEST'} type - Message type
 * @property {import('./api.types.js').ApiRequestOptions} data - API request options
 */

/**
 * Get API key message
 * @typedef {Message} GetApiKeyMessage
 * @property {'GET_API_KEY'} type - Message type
 */

/**
 * Generate API key message
 * @typedef {Message} GenerateApiKeyMessage
 * @property {'GENERATE_API_KEY'} type - Message type
 */

/**
 * Delete API key message
 * @typedef {Message} DeleteApiKeyMessage
 * @property {'DELETE_API_KEY'} type - Message type
 */

/**
 * WebSocket-related messages
 */

/**
 * Get WebSocket status message
 * @typedef {Message} GetWebSocketStatusMessage
 * @property {'GET_WEBSOCKET_STATUS'} type - Message type
 */

/**
 * Reconnect WebSocket message
 * @typedef {Message} ReconnectWebSocketMessage
 * @property {'RECONNECT_WEBSOCKET'} type - Message type
 */

/**
 * WebSocket status update message
 * @typedef {Message} WebSocketStatusUpdateMessage
 * @property {'WEBSOCKET_STATUS_UPDATE'} type - Message type
 * @property {Object} status - WebSocket status
 * @property {boolean} status.connected - Whether WebSocket is connected
 * @property {number} status.timestamp - Status timestamp
 */

/**
 * LinkedIn-related messages
 */

/**
 * Check LinkedIn logged in message
 * @typedef {Message} CheckLinkedInLoggedInMessage
 * @property {'CHECK_LINKEDIN_LOGGED_IN'} type - Message type
 */

/**
 * Open LinkedIn message
 * @typedef {Message} OpenLinkedInMessage
 * @property {'OPEN_LINKEDIN'} type - Message type
 */

/**
 * Content script function execution message
 * @typedef {Message} RunContentScriptFunctionMessage
 * @property {'RUN_CONTENT_SCRIPT_FUNCTION'} type - Message type
 * @property {string} functionName - Function name to run
 * @property {Object} params - Function parameters
 */

/**
 * Message handler type
 * @typedef {Object} MessageHandler
 * @property {(message: Message, sendResponse: Function) => boolean} handleMessage - Function to handle the message
 */

/**
 * Union type of all possible messages
 * @typedef {GetUserProfileMessage|LogoutUserMessage|AuthSessionMessage|ApiRequestMessage|GetApiKeyMessage|GenerateApiKeyMessage|DeleteApiKeyMessage|GetWebSocketStatusMessage|ReconnectWebSocketMessage|WebSocketStatusUpdateMessage|CheckLinkedInLoggedInMessage|OpenLinkedInMessage|RunContentScriptFunctionMessage} AnyMessage
 */

// Export nothing - this file is only for JSDoc type definitions
export {}; 