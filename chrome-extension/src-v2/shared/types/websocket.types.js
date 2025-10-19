// @ts-check

/**
 * TypeScript-compatible type definitions for WebSocket messages and operations.
 * These types define the shape of WebSocket messages, connection states,
 * and response statuses used throughout the application.
 * 
 * @fileoverview WebSocket type definitions that can be used with JSDoc annotations
 * for improved type safety and autocompletion.
 */

/**
 * Base WebSocket message interface
 * All WebSocket messages extend this base structure
 * @typedef {Object} WebSocketMessage
 * @property {string} type - The message type identifier
 * @property {number} [timestamp] - Optional timestamp of when the message was created
 */

/**
 * Authentication message sent to establish identity
 * @typedef {WebSocketMessage} WebSocketAuthMessage
 * @property {'auth'} type - Authentication message type
 * @property {string} token - Authentication token
 * @property {string} [user_id] - Optional user ID
 */

/**
 * Ping message for keep-alive
 * @typedef {WebSocketMessage} WebSocketPingMessage
 * @property {'ping'} type - Ping message type
 * @property {string} [id] - Optional message ID for correlation
 */

/**
 * Pong message response to ping
 * @typedef {WebSocketMessage} WebSocketPongMessage
 * @property {'pong'} type - Pong message type
 * @property {string} [id] - Optional corresponding ping ID
 * @property {number} [server_time] - Server timestamp
 */

/**
 * Error message from server
 * @typedef {WebSocketMessage} WebSocketErrorMessage
 * @property {'error'} type - Error message type
 * @property {string} message - Error description
 * @property {string} [code] - Error code
 * @property {Object} [details] - Additional error details
 */

/**
 * Notification message from server
 * @typedef {WebSocketMessage} WebSocketNotificationMessage
 * @property {'notification'} type - Notification message type
 * @property {string} message - Notification text
 * @property {'info'|'success'|'warning'|'error'} level - Notification severity level
 * @property {Object} [data] - Additional notification data
 */

/**
 * Request to get LinkedIn posts
 * @typedef {WebSocketMessage} WebSocketGetPostsRequestMessage
 * @property {'request_get_posts'} type - Get posts request type
 * @property {string} request_id - Request identifier for correlation
 * @property {number} [count] - Number of posts to retrieve
 * @property {number} [start] - Starting index
 */

/**
 * Response with LinkedIn posts
 * @typedef {WebSocketMessage} WebSocketGetPostsResponseMessage
 * @property {'response_get_posts'} type - Get posts response type
 * @property {string} request_id - Corresponding request identifier
 * @property {boolean} success - Whether the request was successful
 * @property {Array<Object>} [posts] - Array of post data if successful
 * @property {string} [error] - Error message if unsuccessful
 */

/**
 * Request to get profile data
 * @typedef {WebSocketMessage} WebSocketProfileDataRequestMessage
 * @property {'request_profile_data'} type - Profile data request type
 * @property {string} request_id - Request identifier for correlation
 * @property {'vanity_name'|'profile_id'} request_type - Type of profile identifier
 * @property {string} identifier - Profile identifier value
 */

/**
 * Response with profile data
 * @typedef {WebSocketMessage} WebSocketProfileDataResponseMessage
 * @property {'response_profile_data'} type - Profile data response type
 * @property {string} request_id - Corresponding request identifier
 * @property {boolean} success - Whether the request was successful
 * @property {Object} [profile_data] - Profile data if successful
 * @property {string} [error] - Error message if unsuccessful
 */

/**
 * Request to get commenters for a post
 * @typedef {WebSocketMessage} WebSocketGetCommentersRequestMessage
 * @property {'request_get_commenters'} type - Get commenters request type
 * @property {string} request_id - Request identifier for correlation
 * @property {string} post_url - URL of the post
 * @property {number} [start] - Starting index
 * @property {number} [count] - Number of commenters to retrieve
 * @property {number} [num_replies] - Number of replies per comment
 */

/**
 * Response with commenters data
 * @typedef {WebSocketMessage} WebSocketGetCommentersResponseMessage
 * @property {'response_get_commenters'} type - Get commenters response type
 * @property {string} request_id - Corresponding request identifier
 * @property {boolean} success - Whether the request was successful
 * @property {Array<Object>} [commenters] - Array of commenter data if successful
 * @property {string} [error] - Error message if unsuccessful
 */

/**
 * Union type of all possible WebSocket request messages
 * @typedef {WebSocketAuthMessage|WebSocketPingMessage|WebSocketGetPostsRequestMessage|WebSocketProfileDataRequestMessage|WebSocketGetCommentersRequestMessage} WebSocketRequestMessage
 */

/**
 * Union type of all possible WebSocket response messages
 * @typedef {WebSocketPongMessage|WebSocketErrorMessage|WebSocketNotificationMessage|WebSocketGetPostsResponseMessage|WebSocketProfileDataResponseMessage|WebSocketGetCommentersResponseMessage} WebSocketResponseMessage
 */

/**
 * Union type of all possible WebSocket messages
 * @typedef {WebSocketRequestMessage|WebSocketResponseMessage} WebSocketAnyMessage
 */

/**
 * WebSocket connection states
 * @typedef {'CONNECTING'|'OPEN'|'CLOSING'|'CLOSED'|'DISCONNECTED'} WebSocketConnectionState
 */

/**
 * WebSocket response status values
 * @typedef {'SUCCESS'|'ERROR'|'TIMEOUT'|'OFFLINE'|'AUTH_FAILED'} WebSocketResponseStatus
 */

/**
 * WebSocket connection status object
 * @typedef {Object} WebSocketStatus
 * @property {boolean} connected - Whether the WebSocket is currently connected
 * @property {WebSocketConnectionState} state - Current connection state
 * @property {number} [reconnectAttempt] - Current reconnect attempt (if reconnecting)
 * @property {number} [lastConnected] - Timestamp of last successful connection
 */

/**
 * WebSocket listener function type
 * @typedef {function(WebSocketAnyMessage): void} WebSocketMessageListener
 */

/**
 * WebSocket status change listener function type
 * @typedef {function(WebSocketStatus): void} WebSocketStatusListener
 */

/**
 * WebSocket error listener function type
 * @typedef {function(Error, string): void} WebSocketErrorListener
 */

// Export nothing - this file is only for JSDoc type definitions
export {}; 