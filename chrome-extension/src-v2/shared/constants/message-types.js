//@ts-check

/**
 * Message type constants for communication between extension components
 * 
 * @fileoverview Defines all message types used for communication between 
 * background scripts, content scripts, and UI pages.
 */

/**
 * Message types for communication between components
 * @readonly
 * @enum {string}
 */
export const MESSAGE_TYPES = {
  // LinkedIn status checks
  /** Request to check if user is logged into LinkedIn */
  CHECK_LINKEDIN_LOGGED_IN: 'check_linkedin_logged_in',
  /** Request to open LinkedIn in a new tab */
  OPEN_LINKEDIN: 'open_linkedin',
  /** Request to get the current LinkedIn integration status */
  GET_LINKEDIN_STATUS: 'get_linkedin_status',
  /** Request to toggle the LinkedIn integration status */
  TOGGLE_LINKEDIN: 'toggle_linkedin',
  /** Notification that the LinkedIn integration status has updated */
  LINKEDIN_STATUS_UPDATE: 'linkedin_status_update',
  
  // User profile and auth
  /** Request to get the current user's profile */
  GET_USER_PROFILE: 'get_user_profile',
  /** Request to log out the current user */
  LOGOUT_USER: 'logout_user',
  /** Request to get the user's API key */
  GET_API_KEY: 'get_api_key',
  /** Request to generate a new API key */
  GENERATE_API_KEY: 'generate_api_key',
  /** Request to delete the user's API key */
  DELETE_API_KEY: 'delete_api_key',
  
  // WebSocket communication
  /** Request to get the current WebSocket connection status */
  GET_WEBSOCKET_STATUS: 'get_websocket_status',
  /** Notification of WebSocket status change */
  WEBSOCKET_STATUS_UPDATE: 'websocket_status_update',
  /** Request to send a message via WebSocket */
  SEND_WEBSOCKET_REQUEST: 'send_websocket_request',
  /** Response from a WebSocket request */
  WEBSOCKET_RESPONSE: 'websocket_response',
  /** Request to reconnect the WebSocket */
  RECONNECT_WEBSOCKET: 'reconnect_websocket',
  /** Request to get LinkedIn posts */
  REQUEST_GET_POSTS: 'request_get_posts',
  /** Response with LinkedIn posts data */
  RESPONSE_GET_POSTS: 'response_get_posts',
  /** Request to get profile data */
  REQUEST_PROFILE_DATA: 'request_profile_data',
  /** Response with profile data */
  RESPONSE_PROFILE_DATA: 'response_profile_data',
  /** Request to get commenters on a post */
  REQUEST_GET_COMMENTERS: 'request_get_commenters',
  /** Response with commenters data */
  RESPONSE_GET_COMMENTERS: 'response_get_commenters',
  /** General notification message */
  NOTIFICATION: 'notification',
  
  // API Testing
  /** Request to make an API call via the API Tester */
  API_REQUEST: 'api_request',
  
  // CSRF Token for local testing
  /** Request to get CSRF token */
  GET_CSRF_TOKEN: 'get_csrf_token',

  // API Tester specific
  /** Request API endpoint definitions */
  GET_API_ENDPOINTS: 'get_api_endpoints',
  
  /**
   * Execute a LinkedIn utility function directly
   * 
   * This message can be handled either by:
   * 1. The background script (for direct LinkedIn API calls, no DOM interaction)
   * 2. The content script (for DOM interactions or when running in LinkedIn context)
   * 
   * Used for:
   * - Local testing via API tester (UI → Background → LinkedIn API → UI)
   * - Background operations that don't need content script intervention
   * 
   * Format:
   * {
   *   type: 'execute_function',
   *   data: {
   *     functionName: 'nameOfUtilityFunction',
   *     params: { ...functionParameters }
   *   }
   * }
   */
  EXECUTE_FUNCTION: 'execute_function',
  
  // Content Script Lifecycle
  /** Sent by content script when it loads on a target page */
  CONTENT_SCRIPT_READY: 'content_script_ready',
  /** Request from UI to find an active content script tab */
  GET_ACTIVE_LINKEDIN_TAB: 'get_active_linkedin_tab',

  // Add other message types as needed
};

/**
 * WebSocket message types
 * @readonly
 * @enum {string}
 */
export const WS_MESSAGE_TYPES = {
  /** Ping message to keep connection alive */
  PING: 'ping',
  /** Pong response from server */
  PONG: 'pong',
  /** Authentication message */
  AUTH: 'auth',
  /** Authentication success response */
  AUTH_SUCCESS: 'auth_success',
  /** Authentication error response */
  AUTH_ERROR: 'auth_error',
  /** Error message */
  ERROR: 'error',
  /** Status update notification */
  STATUS_UPDATE: 'status_update',
  /** LinkedIn event notification */
  LINKEDIN_EVENT: 'linkedin_event',
  
  // LinkedIn Data Requests (from server to extension)
  /** Request to get LinkedIn posts */
  REQUEST_GET_POSTS: 'request_get_posts',
  /** Response with LinkedIn posts data */
  RESPONSE_GET_POSTS: 'response_get_posts',
  /** Request to get profile data */
  REQUEST_PROFILE_DATA: 'request_profile_data',
  /** Response with profile data */
  RESPONSE_PROFILE_DATA: 'response_profile_data',
  /** Request to get commenters on a post */
  REQUEST_GET_COMMENTERS: 'request_get_commenters',
  /** Response with commenters data */
  RESPONSE_GET_COMMENTERS: 'response_get_commenters',
  /** Request to get posts from a profile */
  REQUEST_GET_PROFILE_POSTS: 'request_get_profile_posts',
  /** Response with profile posts data */
  RESPONSE_GET_PROFILE_POSTS: 'response_get_profile_posts',
  
  // Generic HTTP Proxy (for transparent LinkedIn API proxying)
  /** Request to execute an HTTP request as a transparent proxy */
  REQUEST_PROXY_HTTP: 'request_proxy_http',
  /** Response with raw HTTP response data */
  RESPONSE_PROXY_HTTP: 'response_proxy_http',
  
  // Refresh LinkedIn session (cookies + CSRF)
  /** Request to refresh LinkedIn cookies and CSRF token */
  REQUEST_REFRESH_LINKEDIN_SESSION: 'request_refresh_linkedin_session',
  /** Response carrying refreshed LinkedIn cookies and CSRF token */
  RESPONSE_REFRESH_LINKEDIN_SESSION: 'response_refresh_linkedin_session',
  
  /** General notification message */
  NOTIFICATION: 'notification'
}; 