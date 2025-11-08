/**
 * @fileoverview Type definitions for Chrome Extension APIs
 * This file provides JSDoc type definitions for the most commonly used Chrome APIs
 * in the LinkedIn Gateway extension. These definitions help with intellisense support
 * and type checking.
 * 
 * Note: These are simplified versions of the full Chrome API definitions.
 * For complete definitions, use @types/chrome in a TypeScript project.
 */

/**
 * @typedef {Object} StorageArea
 * @property {function(string|string[]|Object|null): Promise<Object>} get - Gets one or more items from storage
 * @property {function(Object): Promise<void>} set - Sets multiple items in storage
 * @property {function(string|string[]): Promise<void>} remove - Removes one or more items from storage
 * @property {function(): Promise<void>} clear - Removes all items from storage
 * @property {function(): Promise<string[]>} getBytesInUse - Gets the amount of space used by one or more items
 */

/**
 * @typedef {Object} ChromeStorage
 * @property {StorageArea} local - Local storage area
 * @property {StorageArea} session - Session storage area (in-memory)
 * @property {StorageArea} sync - Synced storage area (across devices)
 * @property {function(function(Object): void): void} onChanged - Event fired when storage changes
 */

/**
 * @typedef {Object} ChromeRuntimeLastError
 * @property {string} message - Description of the error
 */

/**
 * @typedef {Object} ChromeRuntime
 * @property {function(string): string} getURL - Converts a relative path to a fully-qualified URL
 * @property {function(Object, function(any): void): void} sendMessage - Sends a message to the extension
 * @property {ChromeRuntimeLastError} lastError - Contains the last error if an API call failed
 * @property {Object} onMessage - Event fired when a message is received
 * @property {function(function(Object, MessageSender, function(any): void): boolean|void): void} onMessage.addListener - Adds a listener for messages
 * @property {function(function(Object, MessageSender, function(any): void): boolean|void): void} onMessage.removeListener - Removes a listener for messages
 */

/**
 * @typedef {Object} ChromeActionBadgeOptions
 * @property {string} text - Text to be displayed in the badge
 * @property {string|Object} color - Badge background color
 */

/**
 * @typedef {Object} ChromeAction
 * @property {function(ChromeActionBadgeOptions): void} setBadgeText - Sets the badge text
 * @property {function(ChromeActionBadgeOptions): void} setBadgeBackgroundColor - Sets the badge background color
 * @property {Object} onClicked - Event fired when the browser action icon is clicked
 * @property {function(function(Tab): void): void} onClicked.addListener - Adds a listener for browser action clicks
 */

/**
 * @typedef {Object} Tab
 * @property {number} id - The ID of the tab
 * @property {number} index - The zero-based index of the tab within its window
 * @property {number} windowId - The ID of the window the tab is in
 * @property {string} url - The URL of the page displayed in the tab
 * @property {string} title - The title of the page displayed in the tab
 * @property {boolean} active - Whether the tab is selected
 * @property {boolean} highlighted - Whether the tab is highlighted
 * @property {boolean} pinned - Whether the tab is pinned
 * @property {boolean} audible - Whether the tab is producing sound
 * @property {boolean} muted - Whether the tab is muted
 * @property {string} favIconUrl - The URL of the tab's favicon
 * @property {string} status - The loading status of the tab ("loading" or "complete")
 */

/**
 * @typedef {Object} CreateTabOptions
 * @property {string} url - The URL to navigate to
 * @property {number} [windowId] - The ID of the window to create the tab in
 * @property {number} [index] - The position the tab should take in the window
 * @property {boolean} [active] - Whether the tab should become the active tab
 * @property {boolean} [pinned] - Whether the tab should be pinned
 */

/**
 * @typedef {Object} QueryTabOptions
 * @property {boolean} [active] - Whether the tab is active in its window
 * @property {boolean} [currentWindow] - Whether the tab is in the current window
 * @property {string} [url] - URL pattern to match against the tab's URL
 * @property {boolean} [highlighted] - Whether the tab is highlighted
 * @property {number} [windowId] - The ID of the window the tab is in
 */

/**
 * @typedef {Object} ChromeTabs
 * @property {function(CreateTabOptions): Promise<Tab>} create - Creates a new tab
 * @property {function(number, Object): Promise<Tab>} update - Updates a tab
 * @property {function(number): Promise<void>} remove - Removes a tab
 * @property {function(QueryTabOptions): Promise<Tab[]>} query - Queries for tabs
 * @property {function(number): Promise<void>} reload - Reloads a tab
 */

/**
 * @typedef {Object} CookieDetails
 * @property {string} url - URL of the cookie
 * @property {string} name - Name of the cookie
 */

/**
 * @typedef {Object} Cookie
 * @property {string} name - Name of the cookie
 * @property {string} value - Value of the cookie
 * @property {string} domain - Domain of the cookie
 * @property {string} path - Path of the cookie
 * @property {boolean} secure - Whether the cookie is marked as secure
 * @property {boolean} httpOnly - Whether the cookie is marked as HttpOnly
 * @property {boolean} hostOnly - Whether the cookie is a host-only cookie
 * @property {string} sameSite - SameSite attribute of the cookie
 * @property {number} expirationDate - Expiration date of the cookie
 */

/**
 * @typedef {Object} ChromeCookies
 * @property {function(CookieDetails, function(Cookie): void): void} get - Gets a cookie
 * @property {function(Object): Promise<Cookie>} set - Sets a cookie
 * @property {function(CookieDetails): Promise<void>} remove - Removes a cookie
 */

/**
 * @typedef {Object} MessageSender
 * @property {Tab} [tab] - The tab from which the message was sent
 * @property {number} [frameId] - The frame from which the message was sent
 * @property {string} id - The extension ID of the sender
 * @property {string} url - The URL of the sender
 * @property {string} origin - The origin of the sender
 */

/**
 * Chrome Extension API namespace
 * @namespace
 * @name chrome
 */

/**
 * Chrome runtime API for messaging, extension info, etc.
 * @type {ChromeRuntime}
 * @memberof chrome
 */
const runtime = {};

/**
 * Chrome storage API for persistent and session storage.
 * @type {ChromeStorage}
 * @memberof chrome
 */
const storage = {};

/**
 * Chrome action API for browser action (extension icon) functionality.
 * @type {ChromeAction}
 * @memberof chrome
 */
const action = {};

/**
 * Chrome tabs API for controlling browser tabs.
 * @type {ChromeTabs}
 * @memberof chrome
 */
const tabs = {};

/**
 * Chrome cookies API for managing browser cookies.
 * @type {ChromeCookies}
 * @memberof chrome
 */
const cookies = {}; 