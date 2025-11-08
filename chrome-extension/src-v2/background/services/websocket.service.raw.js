import { log, parseLinkedInPostUrl } from '../shared/utils.js';
import { 
    WSS_URL, 
    WS_INITIAL_RECONNECT_DELAY, 
    WS_MAX_RECONNECT_DELAY, 
    WS_RECONNECT_MULTIPLIER,
    WS_PING_INTERVAL,
    WS_PONG_TIMEOUT
} from '../shared/config.js';
import { MESSAGE_TYPES, STORAGE_KEYS, WS_MESSAGE_TYPES, INTERNAL_MESSAGE_TYPES } from '../shared/constants.js';
import { fetchPostsFromFeed } from '../utils/linkedin/feedPosts.js'; // Import the feed post fetching utility
import { getCsrfToken } from './linkedin.js'; 
// Import the (yet to be created) function for fetching commenters
import { fetchCommentersForPost } from '../utils/linkedin/comments.js';

// WebSocket instance
let ws = null;
// Connection status
let isWsConnected = false;
// Reconnection timer
let reconnectTimer = null;
// Current reconnect delay (will be increased on each failed attempt)
let currentReconnectDelay = WS_INITIAL_RECONNECT_DELAY;
// Keep-alive timers
let pingInterval = null;
let pongTimeout = null;

/**
 * Initialize the WebSocket connection
 */
export async function initWebSocket() {
    log('[BG_WS] Attempting initWebSocket...');
    
    // Don't open a new connection if one is already open or connecting
    if (ws !== null && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        log('WebSocket connection attempt skipped: Already open or connecting.');
        return;
    }
    
    // --- Get User ID and Instance ID before connecting ---
    let userId = null;
    let instanceId = null;
    try {
        const storage = await new Promise((resolve) => {
            chrome.storage.local.get([STORAGE_KEYS.USER_ID, 'instanceId'], resolve);
        });
        userId = storage[STORAGE_KEYS.USER_ID];
        instanceId = storage['instanceId']; // Get instance ID

        if (!userId) {
            log('[BG_WS] Connection skipped: No user ID found in storage.');
            // Don't schedule reconnect if user is simply not logged in
            isWsConnected = false;
            broadcastStatus(false);
            stopKeepAlive(); // Ensure timers are stopped
            ws = null; // Ensure ws is null
            return;
        }
        log(`[BG_WS] Found user ID for WebSocket: ${userId}`);

        if (instanceId) {
            log(`[BG_WS] Found instance ID for WebSocket: ${instanceId}`);
        } else {
            log('[BG_WS] No instance ID found - will connect as "default"');
        }
    } catch (error) {
        log(`[BG_WS] Error retrieving user ID/instance ID for WebSocket: ${error.message}`);
        // Schedule reconnect on storage error, as it might be temporary
        scheduleReconnect();
        return;
    }
    // --- End Get User ID and Instance ID ---

    // Construct the URL with user ID and optional instance_id query parameter
    let wsUrlWithUser = `${WSS_URL}/${userId}`;
    if (instanceId) {
        wsUrlWithUser += `?instance_id=${encodeURIComponent(instanceId)}`;
    }

    log(`[BG_WS] Preparing to connect with userId: ${userId}, instanceId: ${instanceId || 'default'} to URL: ${wsUrlWithUser}`);
    // Create a new WebSocket connection
    try {
        log(`[BG_WS] Connecting to WebSocket: ${wsUrlWithUser}`);
        ws = new WebSocket(wsUrlWithUser);
        
        // Set up event handlers
        ws.onopen = handleWsOpen;
        ws.onmessage = handleWsMessage;
        ws.onerror = handleWsError;
        // Pass user ID to onclose for potential specific cleanup
        ws.onclose = (event) => handleWsClose(event, userId); 
    } catch (error) {
        log(`WebSocket connection error: ${error.message}`);
        scheduleReconnect();
    }
}

/**
 * Handle WebSocket connection opened
 */
function handleWsOpen() {
    log('[BG_WS] WebSocket connection opened (onopen event)');
    isWsConnected = true;
    
    // Reset reconnect delay
    currentReconnectDelay = WS_INITIAL_RECONNECT_DELAY;
    
    // Clear any reconnect timer
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    
    // Start keep-alive mechanism
    startKeepAlive();
    
    // Authentication might no longer be needed here if URL implies user context
    // Or, keep it if your server requires a token message regardless
    // authenticateWs(); 
    
    // Broadcast status update to any open UI tabs
    broadcastStatus(true);
}

/**
 * Handle WebSocket messages
 * @param {MessageEvent} event - The message event
 */
function handleWsMessage(event) {
    try {
        const message = JSON.parse(event.data);
        log(`WebSocket message received: ${JSON.stringify(message)}`);
        log(`Detailed message type: ${message.type}, content: ${JSON.stringify(message, null, 2)}`);

        // Ensure pong timeout is cleared on ANY valid message from server
        // (Good practice in case pong message itself is missed)
        if (pongTimeout) {
            clearTimeout(pongTimeout);
            pongTimeout = null;
            log('Cleared pong timeout due to received message.');
        }

        switch (message.type) {
            case WS_MESSAGE_TYPES.PONG:
                // Server acknowledged our ping
                handlePong();
                break;
            
            case MESSAGE_TYPES.REQUEST_GET_POSTS:
                log(`Processing REQUEST_GET_POSTS: ${JSON.stringify(message)}`);
                handleRequestGetPosts(message);
                break;
                
            case MESSAGE_TYPES.REQUEST_PROFILE_DATA:
                // Handle request for profile data
                log(`Processing REQUEST_PROFILE_DATA: ${JSON.stringify(message)}`);
                if (message.request_type === 'vanity_name') {
                    handleVanityNameRequest(message);
                } else {
                    log(`Unhandled profile data request type: ${message.request_type}`);
                }
                break;
                
            // Add case for getting commenters
            case MESSAGE_TYPES.REQUEST_GET_COMMENTERS:
                log(`Processing REQUEST_GET_COMMENTERS: ${JSON.stringify(message)}`);
                log(`REQUEST_GET_COMMENTERS raw parameters: post_url=${message.post_url}, start=${message.start}, count=${message.count}, num_replies=${message.num_replies}`);
                handleRequestGetCommenters(message);
                break;
                
            case MESSAGE_TYPES.NOTIFICATION: // Handle notifications from server
                handleServerNotification(message);
                break;
                
            // Add other message type handlers from server if needed
            default:
                log(`Unhandled WebSocket message type: ${message.type}`);
        }
    } catch (error) {
        log(`Error processing WebSocket message: ${error.message}. Data: ${event.data}`);
    }
}

/**
 * Handle WebSocket errors
 * @param {Event} event - The error event
 */
function handleWsError(event) {
    log('WebSocket error occurred');
    // The onclose event will usually fire immediately after an error
}

/**
 * Handle WebSocket connection closed
 * @param {CloseEvent} event - The close event
 * @param {string} userId - The user ID associated with this connection attempt
 */
function handleWsClose(event, userId) {
    log(`[BG_WS] WebSocket connection closed (onclose event): 
        code=${event.code}, 
        reason='${event.reason}', 
        wasClean=${event.wasClean}, 
        user=${userId}`);
    
    // Update connection state
    isWsConnected = false;
    
    // Stop keep-alive
    stopKeepAlive();
    
    // Clear WebSocket instance
    ws = null;
    
    // Broadcast status update
    broadcastStatus(false);
    
    // Schedule reconnection only if it wasn't a clean close or specific error codes
    // Avoid reconnect loops on auth failures (e.g., 403 implies bad user_id/token)
    if (event.code !== 1000 && event.code !== 1008) { // 1000 = Normal, 1008 = Policy Violation (e.g., auth fail)
         scheduleReconnect();
    } else {
        log(`Skipping reconnect due to close code: ${event.code}`);
        // Reset delay if we are stopping reconnects for this reason
        currentReconnectDelay = WS_INITIAL_RECONNECT_DELAY;
    }
}

/**
 * Schedule a reconnection attempt with exponential backoff
 */
function scheduleReconnect() {
    // Clear any existing reconnect timer
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
    }
    
    log(`[BG_WS] Scheduling reconnection attempt in ${currentReconnectDelay}ms`);
    
    // Set timer for reconnection
    reconnectTimer = setTimeout(() => {
        log('[BG_WS] Attempting to reconnect WebSocket via timer');
        initWebSocket();
    }, currentReconnectDelay);
    
    // Increase reconnect delay (exponential backoff) for next attempt
    currentReconnectDelay = Math.min(
        currentReconnectDelay * WS_RECONNECT_MULTIPLIER,
        WS_MAX_RECONNECT_DELAY
    );
}

/**
 * Start the keep-alive mechanism
 */
function startKeepAlive() {
    log('[BG_WS] Starting WebSocket keep-alive mechanism');
    
    // Clear any existing timers
    stopKeepAlive();
    
    // Set up ping interval
    pingInterval = setInterval(() => {
        sendPing();
    }, WS_PING_INTERVAL);
}

/**
 * Stop the keep-alive mechanism
 */
function stopKeepAlive() {
    // Clear ping interval
    if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
    }
    
    // Clear pong timeout
    if (pongTimeout) {
        clearTimeout(pongTimeout);
        pongTimeout = null;
    }
}

/**
 * Send a ping message
 */
function sendPing() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        log('[BG_WS] Sending ping to WebSocket server');
        
        ws.send(JSON.stringify({ 
            type: WS_MESSAGE_TYPES.PING 
        }));
        
        // Set timeout for pong response
        pongTimeout = setTimeout(() => {
            handlePongTimeout();
        }, WS_PONG_TIMEOUT);
    }
}

/**
 * Handle pong timeout (no response received)
 */
function handlePongTimeout() {
    log('[BG_WS] WebSocket pong timeout - no response from server');
    
    // Consider connection dead
    if (ws) {
        ws.close();
        // This will trigger onclose and reconnection logic
    }
}

/**
 * Broadcast WebSocket status to all open UI tabs
 * @param {boolean} status - The connection status
 */
function broadcastStatus(status) {
    chrome.tabs.query({}, (tabs) => {
        for (const tab of tabs) {
            chrome.tabs.sendMessage(tab.id, {
                type: MESSAGE_TYPES.WEBSOCKET_STATUS_UPDATE,
                status: status
            }).catch(() => {
                // Ignore errors - tab may not have a listener
            });
        }
    });
}

/**
 * Get current WebSocket connection status
 * @returns {boolean} isWsConnected - Whether the WebSocket is connected
 */
export function getWsStatus() {
    return isWsConnected;
}

/**
 * Reconnect WebSocket (disconnect and reconnect)
 * Used when API key is regenerated to sync with new instance_id
 */
export async function reconnectWebSocket() {
    log('[BG_WS] Reconnecting WebSocket...');
    await disconnectWebSocket();
    // Wait a bit before reconnecting
    await new Promise(resolve => setTimeout(resolve, 500));
    await initWebSocket();
}

/**
 * Disconnect WebSocket cleanly
 * Used when API key is deleted or needs to be reset
 */
export async function disconnectWebSocket() {
    log('[BG_WS] Disconnecting WebSocket...');
    
    // Stop keep-alive
    stopKeepAlive();
    
    // Clear reconnect timer
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    
    // Close connection if open
    if (ws !== null) {
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
            ws.close(1000, 'Client disconnect'); // Normal closure
        }
        ws = null;
    }
    
    isWsConnected = false;
    broadcastStatus(false);
    log('[BG_WS] WebSocket disconnected');
}

/**
 * Handle pong message received from server
 */
function handlePong() {
    log('[BG_WS] Received pong from server');
    // Clear the pong timeout timer
    if (pongTimeout) {
        clearTimeout(pongTimeout);
        pongTimeout = null;
    }
}

// --- Handler for REQUEST_GET_POSTS --- 
async function handleRequestGetPosts(message) {
    log(`[BG_WS] Received request to get posts: ${JSON.stringify(message)}`);
    const { start_index, count, request_id } = message;
    
    if (request_id === undefined || start_index === undefined || count === undefined) {
        log("Missing parameters in REQUEST_GET_POSTS message");
        return;
    }

    let responsePayload;
    try {
        // Get CSRF token first
        let csrfToken;
        try {
            csrfToken = await getCsrfToken();
        } catch (tokenError) {
            log(`Failed to get CSRF token: ${tokenError}`);
            // Throw a new error to be caught by the outer catch block
            throw new Error(`Failed to get LinkedIn CSRF token: ${tokenError}`); 
                }
                
        // Call the utility function with the token
        log(`Fetching LinkedIn posts via API: start=${start_index}, count=${count}, request_id=${request_id}`);
        const posts = await fetchPostsFromFeed(start_index, count, csrfToken); // Pass token
        
        log(`Successfully fetched ${posts.length} posts via API for request_id ${request_id}.`);
        
        // Construct success response payload
        responsePayload = {
            type: MESSAGE_TYPES.RESPONSE_GET_POSTS,
            request_id: request_id,
            status: "success",
            data: posts
        };
        
    } catch (error) {
        // Log the specific error (could be token error or fetch error)
        log(`Error during post fetch process for request_id ${request_id}: ${error.message}`); 
        // Construct error response payload
        responsePayload = {
            type: MESSAGE_TYPES.RESPONSE_GET_POSTS,
            request_id: request_id,
            status: "error",
            // Use the error message from the caught error
            error_message: error.message || "Failed to fetch posts from LinkedIn API." 
        };
    }
    
    // Send the response back via WebSocket
    if (ws && ws.readyState === WebSocket.OPEN) {
        log(`Sending RESPONSE_GET_POSTS for request_id ${request_id}`);
        ws.send(JSON.stringify(responsePayload));
    } else {
        log(`WebSocket not open when trying to send RESPONSE_GET_POSTS for request_id ${request_id}.`);
    }
}
// --- End Handler --- 

// Function to handle notifications received from the server
function handleServerNotification(message) {
    log(`Received server notification: ${message.title} - ${message.message}`);
    // You could display this using chrome.notifications API
    // chrome.notifications.create(...);
}

/**
 * Handle a request for LinkedIn profile vanity name
 * @param {Object} message - Message from the server
 * @param {string} message.request_id - The unique ID of the request
 * @param {string} message.profile_id - The LinkedIn profile ID to get the vanity name for
 */
function handleVanityNameRequest(message) {
    log(`Handling vanity name request: ${JSON.stringify(message)}`);
    
    // Find active LinkedIn tabs
    chrome.tabs.query({ 
        url: ["*://*.linkedin.com/*"],
        active: true,
        currentWindow: true
    }, (tabs) => {
        if (tabs.length === 0) {
            // No active LinkedIn tab found, try any LinkedIn tab
            chrome.tabs.query({ 
                url: ["*://*.linkedin.com/*"] 
            }, (allLinkedInTabs) => {
                if (allLinkedInTabs.length === 0) {
                    log("No LinkedIn tabs found to get vanity name");
                    sendVanityNameErrorResponse(message.request_id, "No LinkedIn tabs found");
                    return;
                }
                
                // Use the first available LinkedIn tab
                sendMessageToTab(allLinkedInTabs[0].id, message);
            });
            return;
        }
        
        // Send message to the active LinkedIn tab
        sendMessageToTab(tabs[0].id, message);
    });
}

/**
 * Send message to content script in specified tab
 * @param {number} tabId - The ID of the tab to send the message to
 * @param {Object} message - The original request message
 */
function sendMessageToTab(tabId, message) {
    chrome.tabs.sendMessage(tabId, {
        type: 'get_vanity_name',
        profile_id: message.profile_id,
        request_id: message.request_id
    }, (response) => {
        if (chrome.runtime.lastError) {
            log(`Error sending message to content script: ${chrome.runtime.lastError.message}`);
            sendVanityNameErrorResponse(message.request_id, 
                `Failed to communicate with LinkedIn tab: ${chrome.runtime.lastError.message}`);
            return;
        }
        
        // Handle the response from the content script
        if (response) {
            log(`Received response from content script: ${JSON.stringify(response)}`);
            
            if (response.status === 'success') {
                // Forward the successful response to the backend
                sendVanityNameResponse(
                    response.request_id,
                    response.vanity_name
                );
            } else {
                // Forward the error response to the backend
                sendVanityNameErrorResponse(
                    response.request_id,
                    response.error_message || 'Unknown error getting vanity name'
                );
            }
        } else {
            // No response received
            sendVanityNameErrorResponse(
                message.request_id,
                'No response received from content script'
            );
        }
    });
}

/**
 * Send error response for vanity name request
 * @param {string} requestId - The request ID from the original request
 * @param {string} errorMessage - The error message
 */
function sendVanityNameErrorResponse(requestId, errorMessage) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: MESSAGE_TYPES.RESPONSE_PROFILE_DATA,
            request_id: requestId,
            status: "error",
            error_message: errorMessage
        }));
    } else {
        log(`WebSocket not open when trying to send vanity name error response for request_id ${requestId}`);
    }
}

/**
 * Send successful vanity name response
 * @param {string} requestId - The request ID from the original request
 * @param {string} vanityName - The extracted vanity name
 */
function sendVanityNameResponse(requestId, vanityName) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: MESSAGE_TYPES.RESPONSE_PROFILE_DATA,
            request_id: requestId,
            status: "success",
            data: {
                vanity_name: vanityName
            }
        }));
        log(`Sent successful vanity name response for request_id ${requestId}: ${vanityName}`);
    } else {
        log(`WebSocket not open when trying to send vanity name response for request_id ${requestId}`);
    }
}

// --- Handler for REQUEST_GET_COMMENTERS --- 
async function handleRequestGetCommenters(message) {
    log(`Handling request to get commenters: ${JSON.stringify(message)}`);
    const { post_url, request_id, start = 0, count = 10, num_replies = 1 } = message;

    if (!post_url || !request_id) {
        log('Missing post_url or request_id in REQUEST_GET_COMMENTERS');
        sendCommenterErrorResponse(request_id || 'unknown', 'Missing required parameters (post_url, request_id).');
        return;
    }

    log(`Request parameters: post_url=${post_url}, start=${start}, count=${count}, num_replies=${num_replies}`);
    
    try {
        // 1. Get CSRF Token
        log('Getting CSRF token for fetching commenters...');
        const csrfToken = await getCsrfToken();
        if (!csrfToken) {
            throw new Error('Failed to retrieve CSRF token.');
        }
        log('CSRF token obtained.');

        // 2. Call GraphQL Utility Function - pass all parameters properly
        log(`Calling fetchCommentersForPost with GraphQL endpoint for URL: ${post_url}, start: ${start}, count: ${count}, numReplies: ${num_replies}`);
        const commenters = await fetchCommentersForPost(post_url, csrfToken, start, count, num_replies);
        log(`Successfully fetched ${commenters.length} commenter details.`);

        // 3. Send Success Response
        sendCommenterResponse(request_id, commenters);

    } catch (error) {
        log(`Error handling REQUEST_GET_COMMENTERS: ${error.message}`, 'error');
        sendCommenterErrorResponse(request_id, error.message || 'Failed to fetch commenters.');
    }
}

/**
 * Send successful commenters response back to backend.
 * @param {string} requestId 
 * @param {Array<Object>} commentersData 
 */
function sendCommenterResponse(requestId, commentersData) {
    const payload = {
        type: MESSAGE_TYPES.RESPONSE_GET_COMMENTERS,
        request_id: requestId,
        status: "success",
        data: commentersData
    };
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        log(`Sending RESPONSE_GET_COMMENTERS for request_id ${requestId} with ${commentersData.length} commenters`);
        ws.send(JSON.stringify(payload));
    } else {
        log(`WebSocket not open when trying to send RESPONSE_GET_COMMENTERS for request_id ${requestId}.`);
    }
}

/**
 * Send error commenters response back to backend.
 * @param {string} requestId 
 * @param {string} errorMessage 
 */
function sendCommenterErrorResponse(requestId, errorMessage) {
    const payload = {
        type: MESSAGE_TYPES.RESPONSE_GET_COMMENTERS,
        request_id: requestId,
        status: "error",
        error_message: errorMessage
    };
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        log(`Sending ERROR RESPONSE_GET_COMMENTERS for request_id ${requestId}: ${errorMessage}`);
        ws.send(JSON.stringify(payload));
    } else {
        log(`WebSocket not open when trying to send ERROR RESPONSE_GET_COMMENTERS for request_id ${requestId}.`);
    }
}
// --- End Handler --- 