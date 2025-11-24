//@ts-check
/// <reference types="chrome"/>

/**
 * LinkedIn Comments Module
 * 
 * @fileoverview This module contains functions for fetching and processing comments
 * from LinkedIn posts using the LinkedIn GraphQL API. It provides the core functionality
 * for extracting commenter details which can be used by the extension for analytics
 * and engagement tracking.
 */

import { randomDelay } from '../../shared/utils/general.utils.js';
import { parseLinkedInPostUrl } from './feed.js';
import { logger } from '../../shared/utils/logger.js';
/** @typedef {import('../../shared/types/linkedin.types.js').CommenterDetail} CommenterDetail */

/** 
 * Base URL for LinkedIn GraphQL API requests 
 * @type {string}
 */
const GRAPHQL_BASE_URL = 'https://www.linkedin.com/voyager/api/graphql';

/**
 * Query ID for fetching post comments (used in GraphQL request)
 * @type {string}
 */
const COMMENTS_QUERY_ID = 'voyagerSocialDashComments.95ed44bc87596acce7c460c70934d0ff';

/**
 * Fetches a batch of comments for a given LinkedIn post URL using the GraphQL endpoint.
 * 
 * This function makes a direct API call to LinkedIn's GraphQL endpoint, parses the 
 * response, and extracts commenter details from the returned data structure.
 * 
 * @param {string} postUrl - The FULL URL of the post.
 * @param {string} csrfToken - The CSRF token for making authenticated requests.
 * @param {number} [start=0] - The starting index for fetching comments.
 * @param {number} [count=10] - The number of comments to fetch per request.
 * @param {number} [numReplies=1] - The number of replies to fetch for each comment.
 * @returns {Promise<Array<CommenterDetail>>} A promise that resolves to a list of commenter detail objects.
 * @throws {Error} When failing to parse post URN or on request failure
 */
export async function fetchCommentersForPost(postUrl, csrfToken, start = 0, count = 10, numReplies = 1) {
    // Input validation
    if (!postUrl || typeof postUrl !== 'string') {
        const error = new Error('Post URL is required and must be a string');
        logger.error(error.message);
        throw error;
    }

    if (!csrfToken || typeof csrfToken !== 'string') {
        const error = new Error('CSRF token is required and must be a string');
        logger.error(error.message);
        throw error;
    }

    if (typeof start !== 'number' || start < 0) {
        const error = new Error(`Invalid start index: ${start}. Must be a non-negative number.`);
        logger.error(error.message);
        throw error;
    }

    if (typeof count !== 'number' || count <= 0) {
        const error = new Error(`Invalid count: ${count}. Must be a positive number.`);
        logger.error(error.message);
        throw error;
    }

    if (typeof numReplies !== 'number' || numReplies < 0) {
        const error = new Error(`Invalid numReplies: ${numReplies}. Must be a non-negative number.`);
        logger.error(error.message);
        throw error;
    }

    // Parse the Post URN from the full URL
    const postUrn = parseLinkedInPostUrl(postUrl);
    if (!postUrn) {
        const error = new Error(`Could not parse Post URN from URL: ${postUrl}`);
        logger.error(error.message);
        throw error;
    }
    logger.info(`[COMMENTS_GQL] Using Post URN: ${postUrn}, start: ${start}, count: ${count}, numReplies: ${numReplies}`);

    // Build the GraphQL API URL
    try {
        const url = `${GRAPHQL_BASE_URL}?variables=(count:${count},numReplies:${numReplies},socialDetailUrn:urn%3Ali%3Afsd_socialDetail%3A%28${encodeURIComponent(postUrn)}%2C${encodeURIComponent(postUrn)}%2Curn%3Ali%3AhighlightedReply%3A-%29,sortOrder:RELEVANCE,start:${start})&queryId=${COMMENTS_QUERY_ID}`;
        logger.info(`[COMMENTS_GQL] Final URL: ${url}`);

        // Define Headers
        const headers = {
            'csrf-token': csrfToken,
            'accept': 'application/vnd.linkedin.normalized+json+2.1',
            'X-RestLi-Protocol-Version': '2.0.0',
            'cookie': `JSESSIONID="${csrfToken}";`, 
        };

        // Define Fetch Options
        /** @type {RequestInit} */
        const requestOptions = {
            method: 'GET',
            headers: headers,
            credentials: 'include'
        };

        logger.info(`[COMMENTS_GQL] Request Options - method: ${requestOptions.method}, headers present: ${!!requestOptions.headers}`);

        // Make the request and handle response
        const response = await fetch(url, requestOptions);
        logger.info(`[COMMENTS_GQL] Received response status: ${response.status}`);

        let responseText = '';
        try {
            responseText = await response.text();
            logger.info(`[COMMENTS_GQL] Received raw response text (length: ${responseText.length})`); 
        } catch (textError) {
            logger.error(`[COMMENTS_GQL] Could not read response text: ${textError.message}`);
            throw new Error(`Failed to read response text: ${textError.message}`);
        }

        if (!response.ok) {
            logger.error(`[COMMENTS_GQL] Error response body: ${responseText}`);
            let errorMsg = `Failed to fetch comments: ${response.status} ${response.statusText}`;
            // Add specific checks if needed based on GraphQL error responses
            if (response.status === 403) {
                 errorMsg = `Failed to fetch comments: LinkedIn permission denied (403). Check login/CSRF token.`;
            } else if (response.status === 429) {
                 errorMsg = `Rate limit exceeded (429). Try again later.`;
            }
            throw new Error(errorMsg);
        }

        let data;
        try {
            if (!responseText) {
                 logger.warn('[COMMENTS_GQL] Received empty response text. Assuming no comments.');
                 return [];
            }
            data = JSON.parse(responseText);
            logger.info(`[COMMENTS_GQL] Successfully parsed JSON response.`);
        } catch (parseError) {
             logger.error(`[COMMENTS_GQL] Failed to parse JSON response: ${parseError.message}`);
             throw new Error(`Failed to parse JSON response from LinkedIn GraphQL API: ${parseError.message}`);
        }
        
        logger.info(`[COMMENTS_GQL] Response data snippet: ${JSON.stringify(data?.data?.data).substring(0, 300)}...`);

        let commenters = [];
        // Process included data - needs adjustment for GraphQL response structure
        if (data.included && Array.isArray(data.included)) {
            commenters = processCommentBatch(data.included);
            logger.info(`[COMMENTS_GQL] Processed ${commenters.length} commenter details from 'included' array.`);
        } else {
            logger.warn(`[COMMENTS_GQL] No 'included' data found or it's not an array. Structure: ${Object.keys(data)}`);
        }

        logger.info(`[COMMENTS_GQL] Finished fetching batch. Commenter details extracted: ${commenters.length}`);
        return commenters;

    } catch (error) {
        logger.error(`[COMMENTS_GQL] Error during fetch/processing for ${postUrn} (start: ${start}, count: ${count}): ${error.message}`);
        logger.error(`[COMMENTS_GQL] Error stack: ${error.stack}`);
        throw error;
    }
}

/**
 * Processes a batch of response data (included array) to extract commenter details.
 * 
 * @param {Array<Object>} includedData - The 'included' array from the API response.
 * @returns {Array<CommenterDetail>} A list of commenter detail objects for this batch.
 * @private
 */
function processCommentBatch(includedData) {
    if (!Array.isArray(includedData)) {
        logger.error('[PROCESS_BATCH] Invalid includedData provided: not an array');
        return [];
    }

    const commenters = [];
    
    try {
        // Filter for items that have commentary text.
        const commentsWithText = includedData.filter(item => 
            item && typeof item === 'object' && 
            item.commentary && item.commentary.text // Ensure commentary text exists, implicitly filtering for comments
        );
        
        logger.info(`[PROCESS_BATCH] Found ${commentsWithText.length} items with commentary text in included data (total length: ${includedData.length}).`);

        for (const comment of commentsWithText) {
            try {
                // Extract details using the refined paths
                const commentText = comment.commentary.text; // Already confirmed this exists by the filter
                const userName = comment.commenter?.title?.text;
                const userId = comment.commenter?.commenterProfileId; // Direct ID seems more reliable
                const userTitle = comment.commenter?.subtitle;

                if (userId && userName) { // Ensure we have the core details
                    /** @type {CommenterDetail} */
                    const commenterDetail = {
                        userId: userId,
                        userName: userName, // Already checked it exists
                        userTitle: userTitle ?? null, // Use null if subtitle is missing
                        commentText: commentText // Already checked it exists
                    };
                    commenters.push(commenterDetail);
                } else {
                    logger.warn(`[PROCESS_BATCH] Could not extract required details (userId/userName) for comment URN: ${comment.urn}. UserID found: ${!!userId}, UserName found: ${!!userName}`);
                }
            } catch (commentError) {
                logger.error(`[PROCESS_BATCH] Error processing individual comment: ${commentError.message}`);
                // Continue processing other comments, don't throw
            }
        }
    } catch (error) {
        logger.error(`[PROCESS_BATCH] Error processing comment batch: ${error.message}`);
        // Return what we've got so far rather than throwing
    }
    
    logger.info(`[PROCESS_BATCH] Extracted ${commenters.length} commenter details from batch.`);
    return commenters;
}

/**
 * Extracts the unique profile ID from various LinkedIn URN formats.
 * 
 * @param {string} urn - The entityUrn (e.g., urn:li:fsd_profile:ACoAA..., urn:li:fs_miniProfile:...). 
 * @returns {string|null} The extracted profile ID or null.
 * @private
 */
function extractProfileId(urn) {
    if (!urn || typeof urn !== 'string') {
        logger.warn(`[EXTRACT_ID] Invalid URN provided: ${urn}`);
        return null;
    }
    
    try {
        // Regex to capture the ID part after the last colon in common profile URN patterns
        // Handles variations like fsd_profile, fs_miniProfile, profile, member etc.
        const match = urn.match(/urn:li:(?:fsd_profile|fs_miniProfile|profile|member):([^,)]+)/);
        if (match && match[1]) {
            // Basic validation: Ensure it looks like a plausible ID (alphanumeric, may include -_)
            if (/^[a-zA-Z0-9_-]+$/.test(match[1])) {
                return match[1];
            } else {
                logger.warn(`[EXTRACT_ID] Pattern matched but result (${match[1]}) doesn't look like a valid ID for URN: ${urn}`);
            }
        }
        
        // Fallback: If the specific pattern doesn't match, try to grab the ID after the last colon generically
        const genericMatch = urn.match(/([^:]+)$/);
        const potentialId = genericMatch ? genericMatch[0] : null;
        
        // Basic sanity check - profile IDs usually contain letters and numbers, hyphens, underscores
        if (potentialId && /^[a-zA-Z0-9_-]+$/.test(potentialId)) {
            logger.info(`[EXTRACT_ID] Used fallback regex for URN: ${urn}, Extracted ID: ${potentialId}`);
            return potentialId;
        }
        
        logger.warn(`[EXTRACT_ID] Could not extract profile ID from URN: ${urn}`);
        return null;
    } catch (error) {
        logger.error(`[EXTRACT_ID] Error extracting profile ID from URN ${urn}: ${error.message}`);
        return null;
    }
} 