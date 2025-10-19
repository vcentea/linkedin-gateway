//@ts-check
/// <reference types="chrome"/>

/**
 * LinkedIn Feed Interaction Module
 * 
 * @fileoverview This module contains functions for interacting with the LinkedIn feed,
 * including fetching posts, extracting post details, and parsing LinkedIn post URLs.
 * It serves as the core interface for LinkedIn feed-related operations used throughout
 * the extension.
 */

import { logger } from '../../shared/utils/logger.js';

/**
 * Parses a LinkedIn post URL to extract the URN (activity or ugcPost).
 * 
 * This function supports multiple URL formats:
 * - URLs with direct URN notation: containing "urn:li:activity:1234567890"
 * - URLs with simple ID notation: containing "activity:1234567890" or "ugcPost:1234567890"
 * - URLs with hyphen notation: containing "activity-1234567890" or "ugcPost-1234567890"
 * 
 * @param {string} postUrl - The full LinkedIn post URL.
 * @returns {string|null} The extracted URN or null if not found.
 */
export function parseLinkedInPostUrl(postUrl) {
    logger.info(`Parsing LinkedIn URL: ${postUrl}`);
    try {
        if (!postUrl || typeof postUrl !== 'string') {
            logger.warn(`Invalid postUrl provided: ${postUrl}`);
            return null;
        }

        // Try to find URN directly in the path or query parameters
        const urnRegex = /(urn:li:(?:activity|ugcPost):\d+)/;
        const urlMatch = postUrl.match(urnRegex);
        if (urlMatch && urlMatch[1]) {
            const urn = urlMatch[1];
            logger.info(`Parsed URN directly from URL: ${urn}`);
            return urn;
        }
        
        // Fallback: Look for activity or ugcPost colon patterns
        const activityMatch = postUrl.match(/(?:activity:|ugcPost:)(\d+)/);
        if (activityMatch && activityMatch[1]) {
            const id = activityMatch[1];
            const type = postUrl.includes('ugcPost:') ? 'ugcPost' : 'activity';
            const urn = `urn:li:${type}:${id}`;
            logger.info(`Parsed URN using fallback colon pattern: ${urn}`);
            return urn;
        }
        
        // New fallback: handle hyphen-based patterns in LinkedIn URLs (e.g., "activity-1234567890-")
        const hyphenActivity = postUrl.match(/activity-(\d+)/);
        if (hyphenActivity && hyphenActivity[1]) {
            const id = hyphenActivity[1];
            const urn = `urn:li:activity:${id}`;
            logger.info(`Parsed URN from hyphen pattern: ${urn}`);
            return urn;
        }
        const hyphenUgc = postUrl.match(/ugcPost-(\d+)/);
        if (hyphenUgc && hyphenUgc[1]) {
            const id = hyphenUgc[1];
            const urn = `urn:li:ugcPost:${id}`;
            logger.info(`Parsed URN from hyphen pattern: ${urn}`);
            return urn;
        }
        
        logger.warn(`Could not extract URN from URL: ${postUrl}`);
        return null;

    } catch (error) {
        logger.error(`Error parsing URL ${postUrl}: ${error.message}`);
        return null;
    }
}

/**
 * Fetches a specified number of posts from the LinkedIn feed starting at a given index.
 * 
 * This function makes a direct API call to LinkedIn's voyager API and processes the
 * response to extract post data, author information, and engagement metrics.
 * 
 * @param {number} startIndex - The starting index for fetching posts.
 * @param {number} count - The number of posts to fetch.
 * @param {string} csrfToken - The LinkedIn CSRF token (JSESSIONID value).
 * @returns {Promise<Array<Object>>} - A promise that resolves with an array of formatted post objects.
 * @throws {Error} - Throws an error if fetching or parsing fails.
 */
export async function fetchPostsFromFeed(startIndex, count, csrfToken) {
    logger.info(`Attempting to fetch ${count} posts starting from index ${startIndex}`);
    
    // Input validation
    if (typeof startIndex !== 'number' || startIndex < 0) {
        const error = new Error(`Invalid startIndex: ${startIndex}. Must be a non-negative number.`);
        logger.error(error.message);
        throw error;
    }
    
    if (typeof count !== 'number' || count <= 0) {
        const error = new Error(`Invalid count: ${count}. Must be a positive number.`);
        logger.error(error.message);
        throw error;
    }
    
    // Use the provided csrfToken
    if (!csrfToken) {
        const error = new Error('CSRF token not provided. Cannot fetch posts.');
        logger.error(error.message);
        throw error;
    }
    logger.info(`Using CSRF token: ${csrfToken.substring(0, 6)}...`);

    const requestedCount = count + 1; // Request one more than needed
    const url = `https://www.linkedin.com/voyager/api/feed/updatesV2?count=${requestedCount}&start=${startIndex}&q=feed&includeLongTermHistory=true&useCase=DEFAULT`;
    logger.info(`Fetching from URL (requesting ${requestedCount} items): ${url}`);

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'csrf-token': csrfToken,
                "accept": "application/vnd.linkedin.normalized+json+2.1",
                'X-RestLi-Protocol-Version': '2.0.0',
                'cookie': `JSESSIONID="${csrfToken}";`, // Ensure quotes for header value
            },
            credentials: 'include'
        });

        // Log the HTTP status code immediately after receiving the response
        logger.info(`LinkedIn API response status code: ${response.status}`);
        
        if (!response.ok) {
            const errorText = await response.text();
            logger.error(`HTTP error fetching posts: ${response.status} - ${errorText}`);
            throw new Error(`HTTP error: ${response.status} - ${response.statusText}`);
        }

        const data = await response.json();
        logger.info('Received data from LinkedIn API.');

        if (!data.included || !Array.isArray(data.included)) {
            logger.warn('LinkedIn API response does not contain the expected "included" array.');
            return []; // Return empty array if no posts found or unexpected structure
        }

        const postsArray = [];
        const postDetailsMap = {}; // For likes/comments

        // First pass: Collect likes and comments
        for (const item of data.included) {
            if (item.entityUrn && item.entityUrn.includes('Reaction')) continue; // Skip reaction details

            const socialDetailUrn = item.entityUrn;
            if (socialDetailUrn && (socialDetailUrn.includes('likes') || socialDetailUrn.includes('comments'))) {
                 const likes = item.likes?.paging?.total || item.paging?.total || 0; // Check both structures
                 const comments = item.comments?.paging?.total || 0;
                 let postId = item.entityUrn.split(':').pop().split(',')[0]; // Extract post ID

                 if (postId) {
                    postDetailsMap[postId] = { 
                        likes: postDetailsMap[postId]?.likes || likes, // Prioritize likes if already found
                        comments: postDetailsMap[postId]?.comments || comments // Prioritize comments
                     };
                 }
             }
        }

        // Second pass: Extract post details
        for (const item of data.included) {
            if (!item.updateMetadata || !item.updateMetadata.urn) continue; // Skip items without updateMetadata
            
            try {
                const postData = await extractPostDetailsMinimal(item);

                if (postData && postData.postId) {
                     // Get likes and comments from map
                     const { likes, comments } = postDetailsMap[postData.postId.split(':').pop()] || { likes: 0, comments: 0 };

                    postsArray.push({
                        postId: postData.postId, 
                        postUrl: `https://www.linkedin.com/feed/update/${postData.postId}`,
                        authorName: postData.authorName,
                        authorProfileId: postData.profileID,
                        authorJobTitle: postData.job_title,
                        authorConnectionDegree: postData.conn_degree,
                        postContent: postData.postContent,
                        likes: likes,
                        comments: comments,
                        timestamp: postData.timestamp ? new Date(postData.timestamp).toISOString() : null
                     });
                }
            } catch (extractError) {
                // Log error but continue processing other posts
                logger.error(`Error extracting post details: ${extractError.message}`);
            }
        }

        logger.info(`Extracted ${postsArray.length} posts successfully.`);
        return postsArray;

    } catch (error) {
        logger.error(`Error during fetchPostsFromFeed: ${error.message}`);
        throw error; // Re-throw the error to be caught by the caller
    }
}

/**
 * Extracts essential details from a single LinkedIn feed item.
 * This is a simplified version focused only on extraction for this feature.
 * 
 * @param {Object} item - A single item from the LinkedIn API /feed/updatesV2 response.
 * @returns {Promise<Object|null>} - An object with extracted post details or null if not a valid post.
 * @private
 */
async function extractPostDetailsMinimal(item) {
    // Basic check for a valid post structure
    if (!item.actor || !item.commentary?.text?.text) {
        return null;
    }

    /** @type {{
     *   postId: string|null,
     *   authorName: string,
     *   profileID: string,
     *   postContent: string,
     *   conn_degree: string,
     *   job_title: string,
     *   timestamp: number|null
     * }} */
    const extractedData = {
        postId: item.updateMetadata?.urn || null, // The full URN
        authorName: item.actor.name?.text || "",
        profileID: "", // Will be extracted below
        postContent: item.commentary.text.text,
        conn_degree: "",
        job_title: item.actor.description?.text || "",
        timestamp: item.updateMetadata?.timestamp || null
    };
    
    // Extract Profile ID
    const profileAttribute = item.actor.name?.attributes?.find(attr => attr['*miniProfile']);
    if (profileAttribute && profileAttribute['*miniProfile']) {
        const urnParts = profileAttribute['*miniProfile'].split(':');
        extractedData.profileID = urnParts[urnParts.length - 1];
    } else {
        // Attempt to get from actor urn itself if miniProfile is missing
        if (item.actor.urn && item.actor.urn.includes(':member:')) {
             const urnParts = item.actor.urn.split(':');
             extractedData.profileID = urnParts[urnParts.length - 1];
        }
    }

    // Extract Connection Degree
    const supplementaryInfo = item.actor.supplementaryActorInfo;
    if (supplementaryInfo) {
        extractedData.conn_degree = supplementaryInfo.text || supplementaryInfo.accessibilityText || "";
    }
    
    // Ensure essential fields are present
    if (!extractedData.postId || !extractedData.authorName || !extractedData.profileID) {
         return null;
    }

    return extractedData;
} 