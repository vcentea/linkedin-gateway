//@ts-check
/// <reference types="chrome" />

/**
 * Storage Utilities
 * 
 * @fileoverview Provides wrapper functions for interacting with Chrome's storage API
 * (local and session), handling potential errors and providing a consistent interface.
 */

import { STORAGE_KEYS } from '../constants/storage-keys.js';
import { logger } from './logger.js'; // Updated import

/**
 * Gets an item from Chrome's local storage.
 * @param {string} key - The key of the item to retrieve.
 * @param {any} [defaultValue=null] - The default value to return if the key is not found.
 * @returns {Promise<any>} A promise that resolves with the retrieved value or the default value.
 */
export async function getLocalStorage(key, defaultValue = null) {
    return new Promise((resolve, reject) => {
        chrome.storage.local.get([key], (result) => {
            if (chrome.runtime.lastError) {
                logger.error(`Error getting local storage key: ${key}`, chrome.runtime.lastError, 'getLocalStorage');
                reject(chrome.runtime.lastError);
            } else {
                const value = result[key] === undefined ? defaultValue : result[key];
                logger.info(`Retrieved local storage key: ${key}`, 'getLocalStorage');
                resolve(value);
            }
        });
    });
}

/**
 * Sets an item in Chrome's local storage.
 * @param {string} key - The key of the item to set.
 * @param {any} value - The value to set.
 * @returns {Promise<void>} A promise that resolves when the item is set.
 */
export async function setLocalStorage(key, value) {
    return new Promise((resolve, reject) => {
        chrome.storage.local.set({ [key]: value }, () => {
            if (chrome.runtime.lastError) {
                logger.error(`Error setting local storage key: ${key}`, chrome.runtime.lastError, 'setLocalStorage');
                reject(chrome.runtime.lastError);
            } else {
                logger.info(`Set local storage key: ${key}`, 'setLocalStorage');
                resolve();
            }
        });
    });
}

/**
 * Removes an item from Chrome's local storage.
 * @param {string} key - The key of the item to remove.
 * @returns {Promise<void>} A promise that resolves when the item is removed.
 */
export async function removeLocalStorage(key) {
    return new Promise((resolve, reject) => {
        chrome.storage.local.remove(key, () => {
            if (chrome.runtime.lastError) {
                logger.error(`Error removing local storage key: ${key}`, chrome.runtime.lastError, 'removeLocalStorage');
                reject(chrome.runtime.lastError);
            } else {
                logger.info(`Removed local storage key: ${key}`, 'removeLocalStorage');
                resolve();
            }
        });
    });
}

/**
 * Gets an item from Chrome's session storage.
 * Session storage is cleared when the browser session ends.
 * @param {string} key - The key of the item to retrieve.
 * @param {any} [defaultValue=null] - The default value to return if the key is not found.
 * @returns {Promise<any>} A promise that resolves with the retrieved value or the default value.
 */
export async function getSessionStorage(key, defaultValue = null) {
    return new Promise((resolve, reject) => {
        chrome.storage.session.get([key], (result) => {
            if (chrome.runtime.lastError) {
                logger.error(`Error getting session storage key: ${key}`, chrome.runtime.lastError, 'getSessionStorage');
                reject(chrome.runtime.lastError);
            } else {
                const value = result[key] === undefined ? defaultValue : result[key];
                logger.info(`Retrieved session storage key: ${key}`, 'getSessionStorage');
                resolve(value);
            }
        });
    });
}

/**
 * Sets an item in Chrome's session storage.
 * @param {string} key - The key of the item to set.
 * @param {any} value - The value to set.
 * @returns {Promise<void>} A promise that resolves when the item is set.
 */
export async function setSessionStorage(key, value) {
    return new Promise((resolve, reject) => {
        chrome.storage.session.set({ [key]: value }, () => {
            if (chrome.runtime.lastError) {
                logger.error(`Error setting session storage key: ${key}`, chrome.runtime.lastError, 'setSessionStorage');
                reject(chrome.runtime.lastError);
            } else {
                logger.info(`Set session storage key: ${key}`, 'setSessionStorage');
                resolve();
            }
        });
    });
}

/**
 * Removes an item from Chrome's session storage.
 * @param {string} key - The key of the item to remove.
 * @returns {Promise<void>} A promise that resolves when the item is removed.
 */
export async function removeSessionStorage(key) {
    return new Promise((resolve, reject) => {
        chrome.storage.session.remove(key, () => {
            if (chrome.runtime.lastError) {
                logger.error(`Error removing session storage key: ${key}`, chrome.runtime.lastError, 'removeSessionStorage');
                reject(chrome.runtime.lastError);
            } else {
                logger.info(`Removed session storage key: ${key}`, 'removeSessionStorage');
                resolve();
            }
        });
    });
}

/**
 * TODO: Consider moving runtime state management (like tracking connection status)
 * to a dedicated background service (e.g., storage.service.js) instead of keeping it
 * purely within these utility functions.
 */