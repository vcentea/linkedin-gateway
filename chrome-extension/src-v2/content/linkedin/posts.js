//@ts-check
/// <reference types="chrome"/>

/**
 * LinkedIn Posts Extraction Module
 * 
 * @fileoverview This module contains functions for extracting posts from LinkedIn profiles.
 * It provides the core interface for fetching posts using LinkedIn's GraphQL API.
 */

import { logger } from '../../shared/utils/logger.js';
import { processPostsData } from './postDataProcessor.js';

/**
 * Extract profile ID from LinkedIn profile URL or return as-is if already an ID.
 * 
 * @param {string} profileInput - LinkedIn profile URL or profile ID
 * @returns {Promise<string>} - The profile ID
 * @private
 */
/**
 * Decode HTML entities (works in background script context)
 * Replicates the old project's decodeHTMLEntities function
 */
function decodeHTMLEntities(text) {
    const entities = {
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&#x27;': "'",
        '&#x2F;': '/',
        '&#47;': '/'
    };
    
    return text.replace(/&(?:amp|lt|gt|quot|#39|#x27|#x2F|#47);/g, match => entities[match] || match)
               .replace(/&#(\d+);/g, (match, dec) => String.fromCharCode(dec))
               .replace(/&#x([0-9a-f]+);/gi, (match, hex) => String.fromCharCode(parseInt(hex, 16)));
}

/**
 * Extract LinkedIn profile ID from URL (exact 1:1 copy from old project)
 * @param {string} url - LinkedIn profile URL or ID
 * @returns {Promise<string>} - The extracted profile ID
 */
async function extractProfileId(url) {
    try {
        // First, try to extract from the URL if it's a direct profile ID URL
        const urlMatch = url.match(/urn:li:fsd_profile:([A-Za-z0-9_-]+)/);
        if (urlMatch && urlMatch[1]) {
            return urlMatch[1];
        }
        
        // Check if input is already a profile ID (not a URL)
        // Profile IDs are alphanumeric with underscores and hyphens, typically start with "ACoA"
        // If it doesn't contain "linkedin.com" or "http", assume it's already a profile ID
        if (!/https?:\/\/|linkedin\.com/i.test(url)) {
            // Validate it looks like a profile ID (alphanumeric, underscores, hyphens)
            if (/^[A-Za-z0-9_-]+$/.test(url)) {
                logger.info(`Input is already a profile ID: ${url}`);
                return url;
            }
        }
        
        // Extract the vanity name from the URL if possible
        let vanityName = '';
        const vanityMatch = url.match(/linkedin\.com\/in\/([^\/\?]+)/);
        if (vanityMatch && vanityMatch[1]) {
            vanityName = vanityMatch[1];
            logger.info(`Extracted vanity name: ${vanityName}`);
        }
        
        // If not found in URL, fetch the page content
        const response = await fetch(url);
        const html = await response.text();
        
        // Array to store potential profile IDs with their priority
        const profileIdCandidates = [];
        
        // Method 0 (Highest Priority): Look for hidden code elements with bpr-guid- prefix
        // Using regex instead of DOMParser (which isn't available in background script context)
        const hiddenCodeRegex = /<code[^>]*style="display:\s*none"[^>]*id="bpr-guid-[^"]*"[^>]*>([^<]+)<\/code>/gi;
        const hiddenCodeMatches = html.matchAll(hiddenCodeRegex);
        
        for (const hiddenMatch of hiddenCodeMatches) {
            try {
                // IMPORTANT: Decode HTML entities before parsing JSON (like old project does)
                const content = decodeHTMLEntities(hiddenMatch[1]);
                const jsonData = JSON.parse(content);
                
                // Navigate to the specified JSON path
                if (jsonData && jsonData.data && jsonData.data.data && 
                    jsonData.data.data.identityDashProfilesByMemberIdentity && 
                    jsonData.data.data.identityDashProfilesByMemberIdentity['*elements'] && 
                    jsonData.data.data.identityDashProfilesByMemberIdentity['*elements'].length > 0) {
                    
                    const profileElement = jsonData.data.data.identityDashProfilesByMemberIdentity['*elements'][0];
                    const profileMatch = profileElement.match(/urn:li:fsd_profile:([A-Za-z0-9_-]+)/);
                    
                    if (profileMatch && profileMatch[1]) {
                        profileIdCandidates.push({
                            id: profileMatch[1],
                            priority: -1,
                            source: 'hidden code element with bpr-guid prefix'
                        });
                        logger.info(`Found profile ID in hidden code element: ${profileMatch[1]}`);
                    }
                }
            } catch (e) {
                logger.info(`Error parsing JSON from code element: ${e.message}`);
            }
        }
        
        // Look for profile ID in the page URL first (high priority)
        if (vanityName) {
            const pageUrlPattern = new RegExp(`"publicIdentifier":"${vanityName}"[^}]*"objectUrn":"urn:li:fsd_profile:([A-Za-z0-9_-]+)"`, 'i');
            const pageUrlMatch = html.match(pageUrlPattern);
            if (pageUrlMatch && pageUrlMatch[1]) {
                profileIdCandidates.push({
                    id: pageUrlMatch[1],
                    priority: 0,
                    source: 'vanity name in URL direct match'
                });
            }
        }
        
        // Method 1: Look for meta tags with profile information
        const metaTagMatch = html.match(/<meta\s+name="(?:profile|lnkd:profile|profile:entity)"\s+content="([^"]+)"/i);
        if (metaTagMatch && metaTagMatch[1]) {
            const metaContent = metaTagMatch[1];
            const metaProfileMatch = metaContent.match(/urn:li:fsd_profile:([A-Za-z0-9_-]+)/);
            if (metaProfileMatch && metaProfileMatch[1]) {
                profileIdCandidates.push({
                    id: metaProfileMatch[1],
                    priority: 1,
                    source: 'meta tag'
                });
            }
        }
        
        // Method 2: Look for profile data in JSON-LD structured data
        const jsonLdMatch = html.match(/<script type="application\/ld\+json">([^<]+)<\/script>/);
        if (jsonLdMatch && jsonLdMatch[1]) {
            try {
                const jsonLdData = JSON.parse(jsonLdMatch[1]);
                if (jsonLdData && jsonLdData.mainEntityOfPage) {
                    const mainEntityMatch = jsonLdData.mainEntityOfPage.match(/urn:li:fsd_profile:([A-Za-z0-9_-]+)/);
                    if (mainEntityMatch && mainEntityMatch[1]) {
                        profileIdCandidates.push({
                            id: mainEntityMatch[1],
                            priority: 2,
                            source: 'JSON-LD'
                        });
                    }
                }
            } catch (e) {
                logger.info('Error parsing JSON-LD data: ' + e.message);
            }
        }
        
        // Method 3: Look for profile ID near the vanity name in the HTML
        if (vanityName) {
            const vanityProfileRegex = new RegExp(`"${vanityName}"[^}]*"objectUrn"\\s*:\\s*"urn:li:fsd_profile:([A-Za-z0-9_-]+)"`, 'i');
            const vanityProfileMatch = html.match(vanityProfileRegex);
            if (vanityProfileMatch && vanityProfileMatch[1]) {
                profileIdCandidates.push({
                    id: vanityProfileMatch[1],
                    priority: 3,
                    source: 'vanity name association'
                });
            }
        }
        
        // Look for profile ID in page title context
        const titleMatch = html.match(/<title>([^<]+)<\/title>/);
        if (titleMatch && titleMatch[1]) {
            const title = titleMatch[1];
            const titleContextRegex = new RegExp(`"(firstName|lastName|headline)"[^}]*"${title.split(' ')[0]}"[^}]*"objectUrn"\\s*:\\s*"urn:li:fsd_profile:([A-Za-z0-9_-]+)"`, 'i');
            const titleContextMatch = html.match(titleContextRegex);
            if (titleContextMatch && titleContextMatch[2]) {
                profileIdCandidates.push({
                    id: titleContextMatch[2],
                    priority: 3.5,
                    source: 'page title context'
                });
            }
        }
        
        // Method 4: Look for profile ID in specific data structures
        const dataStructureMatch = html.match(/\{"data":\{"*profileView"*:.*?"miniProfile".*?urn:li:fsd_profile:([A-Za-z0-9_-]+)/s);
        if (dataStructureMatch && dataStructureMatch[1]) {
            profileIdCandidates.push({
                id: dataStructureMatch[1],
                priority: 4,
                source: 'profile data structure'
            });
        }
        
        // Method 5: Look for profile ID in code blocks
        const codeBlockRegex = /<code[^>]*id="bpr-guid-[^"]*"[^>]*>([^<]+)<\/code>/g;
        const codeMatches = html.matchAll(codeBlockRegex);
        
        for (const codeMatch of codeMatches) {
            if (codeMatch && codeMatch[1]) {
                // Decode HTML entities before checking content (like old project)
                const content = decodeHTMLEntities(codeMatch[1]);
                
                if (content.includes('"profileView"') || content.includes('"profile"')) {
                    const profileMatch = content.match(/urn:li:fsd_profile:([A-Za-z0-9_-]+)/);
                    if (profileMatch && profileMatch[1]) {
                        profileIdCandidates.push({
                            id: profileMatch[1],
                            priority: 5,
                            source: 'code block with profile data'
                        });
                    }
                }
            }
        }
        
        // Method 6: Look for all profile IDs in the page as a fallback
        const regex = /urn:li:fsd_profile:([A-Za-z0-9_-]+)/g;
        const matches = [...html.matchAll(regex)];
        
        if (matches && matches.length > 0) {
            const idCounts = {};
            
            matches.forEach(match => {
                const id = match[1];
                idCounts[id] = (idCounts[id] || 0) + 1;
            });
            
            let mostFrequentId = null;
            let highestCount = 0;
            
            for (const [id, count] of Object.entries(idCounts)) {
                if (count > highestCount) {
                    highestCount = count;
                    mostFrequentId = id;
                }
            }
            
            if (mostFrequentId) {
                profileIdCandidates.push({
                    id: mostFrequentId,
                    priority: 6,
                    source: 'most frequent occurrence',
                    count: highestCount
                });
            }
        }
        
        // Sort candidates by priority (lower number = higher priority)
        profileIdCandidates.sort((a, b) => a.priority - b.priority);
        
        logger.info('Profile ID candidates:');
        profileIdCandidates.forEach(candidate => {
            logger.info(`ID: ${candidate.id}, Priority: ${candidate.priority}, Source: ${candidate.source}`);
        });
        
        // Return the highest priority candidate, or null if none found
        return profileIdCandidates.length > 0 ? profileIdCandidates[0].id : null;
    } catch (error) {
        logger.error('Error extracting profile ID:', error);
        throw new Error('Failed to extract profile ID: ' + error.message);
    }
}

/**
 * Fetches posts for a given LinkedIn profile with automatic pagination.
 * 
 * Replicates the logic from the old project's collectProfilePosts function:
 * - Uses fixed page size of 20
 * - Automatically paginates using pagination tokens
 * - Collects posts until desired count is reached
 * 
 * @param {string} profileIdOrURL - The LinkedIn profile ID or URL
 * @param {number} desiredCount - The total number of posts to retrieve (default: 10)
 * @param {string} csrfToken - The LinkedIn CSRF token (JSESSIONID value).
 * @returns {Promise<Object>} - A promise that resolves with an object containing:
 *   - posts: Array of formatted post objects
 *   - hasMore: Boolean indicating if more posts are available
 *   - paginationToken: Token for the last page (if available)
 * @throws {Error} - Throws an error if fetching or parsing fails.
 */
export async function fetchPostsForProfile(profileIdOrURL, desiredCount = 10, csrfToken) {
    // Extract profile ID from URL if needed
    const profileId = await extractProfileId(profileIdOrURL);
    
    // Input validation
    if (!profileId || typeof profileId !== 'string') {
        const error = new Error('Profile ID is required and must be a string');
        logger.error(error.message);
        throw error;
    }
    
    if (typeof desiredCount !== 'number' || desiredCount <= 0) {
        const error = new Error(`Invalid count: ${desiredCount}. Must be a positive number.`);
        logger.error(error.message);
        throw error;
    }
    
    // Use the provided csrfToken
    if (!csrfToken) {
        const error = new Error('CSRF token not provided. Cannot fetch posts.');
        logger.error(error.message);
        throw error;
    }
    
    // Fixed page size of 20 (like old project)
    const pageSize = 20;
    const maxPages = Math.ceil(desiredCount / pageSize);
    
    logger.info(`Fetching ${desiredCount} posts for profile ${profileId}`);
    logger.info(`Using fixed page size: ${pageSize}, max pages: ${maxPages}`);
    logger.info(`Using CSRF token: ${csrfToken.substring(0, 6)}...`);

    let allPosts = [];
    let start = 0;
    let paginationToken = "";
    let hasMore = true;
    let sessionPageCount = 0;
    let emptyResponses = 0;
    
    // Build the profile URN
    const profileUrn = `urn:li:fsd_profile:${profileId}`;
    const encodedProfileUrn = encodeURIComponent(profileUrn);
    const queryId = 'voyagerFeedDashProfileUpdates.418845c51162bcbbda12be537ccc7976';
    
    while (hasMore && sessionPageCount < maxPages && allPosts.length < desiredCount) {
        // Build variables with pagination token if available
        let variables = `(count:${pageSize},start:${start},profileUrn:${encodedProfileUrn}`;
        
        if (paginationToken) {
            variables += `,paginationToken:${encodeURIComponent(paginationToken)}`;
            logger.info(`Using pagination token from previous response: ${paginationToken.substring(0, 15)}...`);
        } else {
            logger.info(`First request - no pagination token yet`);
        }
        
        variables += ")";
        
        const url = `https://www.linkedin.com/voyager/api/graphql?variables=${variables}&queryId=${queryId}`;
        
        logger.info(`Page ${sessionPageCount + 1} API request:`);
        logger.info(`Pagination params: start=${start}, count=${pageSize}${paginationToken ? ', using token' : ''}`);

        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'csrf-token': csrfToken,
                    "accept": "application/vnd.linkedin.normalized+json+2.1",
                    'X-RestLi-Protocol-Version': '2.0.0'
                },
                credentials: 'include'
            });

            logger.info(`LinkedIn API response status code: ${response.status}`);
            
            if (!response.ok) {
                const errorText = await response.text();
                logger.error(`HTTP error fetching posts: ${response.status} - ${errorText}`);
                throw new Error(`HTTP error: ${response.status} - ${response.statusText}`);
            }

            const data = await response.json();
            logger.info(`Received response for page ${sessionPageCount + 1}`);

            if (!data.included || !Array.isArray(data.included)) {
                logger.warn('LinkedIn API response does not contain the expected "included" array.');
                emptyResponses++;
                if (emptyResponses >= 3) {
                    logger.info(`Stopping after ${emptyResponses} consecutive empty responses`);
                    hasMore = false;
                    break;
                }
                start += pageSize;
                sessionPageCount++;
                continue;
            }

            // Process posts using the comprehensive processor
            const postsBatch = await processPostsData(data);
            logger.info(`Processed ${postsBatch.length} posts from page ${sessionPageCount + 1}`);
            
            if (postsBatch.length === 0) {
                emptyResponses++;
                if (emptyResponses >= 3) {
                    logger.info(`Stopping after ${emptyResponses} consecutive empty responses`);
                    hasMore = false;
                    break;
                }
            } else {
                emptyResponses = 0;
                allPosts = allPosts.concat(postsBatch);
            }

            // Extract pagination info from response (like old project)
            const metadata = data.data?.data?.feedDashProfileUpdatesByMemberShareFeed?.metadata || {};
            const paging = data.data?.data?.feedDashProfileUpdatesByMemberShareFeed?.paging || {};
            
            // Update pagination token for next request
            if (metadata.paginationToken) {
                paginationToken = metadata.paginationToken;
                logger.info(`Updated pagination token for next request`);
            } else {
                logger.info(`No new pagination token provided`);
            }
            
            // Update start value for next page (like old project)
            if (paging.start !== undefined) {
                const oldStart = start;
                start = paging.start;
                
                if (start === oldStart) {
                    logger.warn(`LinkedIn returned same start value (${start}). Forcing increment.`);
                    start += pageSize;
                }
                
                logger.info(`Next page will use start=${start}`);
                hasMore = true;
            } else {
                start += pageSize;
                logger.info(`No start value provided, incrementing to ${start}`);
                hasMore = false;
            }
            
            // Stop if we've collected enough posts
            if (allPosts.length >= desiredCount) {
                logger.info(`Stopping pagination: collected ${allPosts.length} posts (requested: ${desiredCount})`);
                hasMore = false;
                break;
            }
            
            sessionPageCount++;
            
            // Add random delay between pages to avoid rate limits (1-5 seconds)
            if (hasMore && sessionPageCount < maxPages) {
                const delay = Math.random() * 4 + 1; // Random between 1 and 5 seconds
                logger.info(`Waiting ${delay.toFixed(2)} seconds before next page to avoid rate limits...`);
                await new Promise(resolve => setTimeout(resolve, delay * 1000));
            }

        } catch (error) {
            logger.error(`Error during page ${sessionPageCount + 1}: ${error}`);
            throw error;
        }
    }
    
    // Limit to desired count
    allPosts = allPosts.slice(0, desiredCount);
    
    logger.info(`Collection complete: ${allPosts.length} posts, ${sessionPageCount} pages processed`);
    
    return {
        posts: allPosts,
        hasMore: hasMore,
        paginationToken: paginationToken
    };
}

/**
 * Processes a batch of LinkedIn API response data to extract post details.
 * 
 * @param {Array<Object>} includedData - The 'included' array from the LinkedIn API response
 * @returns {Array<Object>} - Array of formatted post objects
 * @private
 */
function processPostsBatch(includedData) {
    if (!Array.isArray(includedData)) {
        logger.error('Invalid includedData: not an array');
        return [];
    }
    
    const posts = [];
    
    // Create maps for quick lookup
    const socialDetailMap = {};
    const actorMap = {};
    const contentMap = {};
    const socialActivityCountsMap = {};
    
    // First pass: Build lookup maps
    for (const item of includedData) {
        if (!item || typeof item !== 'object') continue;
        
        const entityUrn = item.entityUrn || '';
        
        // Map social details (for metrics)
        if (entityUrn && entityUrn.includes('socialDetail')) {
            socialDetailMap[entityUrn] = item;
        }
        
        // Map actors (for author info)
        if (entityUrn && entityUrn.includes('actor')) {
            actorMap[entityUrn] = item;
        }
        
        // Map content
        if (item.content) {
            contentMap[entityUrn] = item;
        }
        
        // Map social activity counts (likes/comments) - COMPREHENSIVE like old project
        if (item.$type && (
            item.$type.includes('SocialActivityCounts') || 
            item.$type.includes('socialActivityCounts')
        )) {
            const urn = item.urn || entityUrn;
            const entityUrnToCheck = entityUrn || item.urn;
            
            // Extract activity ID (PRIMARY for profile posts)
            const urnMatch = urn ? urn.match(/activity:(\d+)/) : null;
            const entityUrnMatch = entityUrnToCheck ? entityUrnToCheck.match(/activity:(\d+)/) : null;
            
            if (urnMatch && urnMatch[1]) {
                socialActivityCountsMap[urnMatch[1]] = item;
                logger.info(`Mapped social activity counts for post ID ${urnMatch[1]}`);
            } else if (entityUrnMatch && entityUrnMatch[1]) {
                socialActivityCountsMap[entityUrnMatch[1]] = item;
                logger.info(`Mapped social activity counts for post ID ${entityUrnMatch[1]} from entityUrn`);
            }
            
            // Extract ugcPost ID
            const ugcPostMatch = urn ? urn.match(/ugcPost:(\d+)/) : null;
            const entityUgcPostMatch = entityUrnToCheck ? entityUrnToCheck.match(/ugcPost:(\d+)/) : null;
            
            if (ugcPostMatch && ugcPostMatch[1]) {
                socialActivityCountsMap[ugcPostMatch[1]] = item;
                logger.info(`Mapped social activity counts for ugcPost ID ${ugcPostMatch[1]}`);
            } else if (entityUgcPostMatch && entityUgcPostMatch[1]) {
                socialActivityCountsMap[entityUgcPostMatch[1]] = item;
                logger.info(`Mapped social activity counts for ugcPost ID ${entityUgcPostMatch[1]} from entityUrn`);
            }
            
            // Extract article ID
            const articleMatch = urn ? urn.match(/article:(\d+)/) : null;
            const entityArticleMatch = entityUrnToCheck ? entityUrnToCheck.match(/article:(\d+)/) : null;
            
            if (articleMatch && articleMatch[1]) {
                socialActivityCountsMap[articleMatch[1]] = item;
                logger.info(`Mapped social activity counts for article ID ${articleMatch[1]}`);
            } else if (entityArticleMatch && entityArticleMatch[1]) {
                socialActivityCountsMap[entityArticleMatch[1]] = item;
                logger.info(`Mapped social activity counts for article ID ${entityArticleMatch[1]} from entityUrn`);
            }
            
            // Extract videoAsset ID
            const videoAssetMatch = urn ? urn.match(/videoAsset:(\d+)/) : null;
            const entityVideoAssetMatch = entityUrnToCheck ? entityUrnToCheck.match(/videoAsset:(\d+)/) : null;
            
            if (videoAssetMatch && videoAssetMatch[1]) {
                socialActivityCountsMap[videoAssetMatch[1]] = item;
                logger.info(`Mapped social activity counts for videoAsset ID ${videoAssetMatch[1]}`);
            } else if (entityVideoAssetMatch && entityVideoAssetMatch[1]) {
                socialActivityCountsMap[entityVideoAssetMatch[1]] = item;
                logger.info(`Mapped social activity counts for videoAsset ID ${entityVideoAssetMatch[1]} from entityUrn`);
            }
            
            // ALWAYS map by full URN for reliable lookups (not else-if!)
            if (urn) {
                socialActivityCountsMap[urn] = item;
            }
            if (entityUrnToCheck && entityUrnToCheck !== urn) {
                socialActivityCountsMap[entityUrnToCheck] = item;
            }
            
            // Log if we have direct social metrics
            if (item.numLikes !== undefined || item.numComments !== undefined) {
                logger.info(`Direct social metrics - Likes: ${item.numLikes}, Comments: ${item.numComments}`);
            }
        }
    }
    
    logger.info(`Built maps: social_details=${Object.keys(socialDetailMap).length}, actors=${Object.keys(actorMap).length}, social_counts=${Object.keys(socialActivityCountsMap).length}`);
    
    // Second pass: Extract posts
    for (const item of includedData) {
        if (!item || typeof item !== 'object') continue;
        
        // Look for items that appear to be posts
        // These have updateMetadata or are feed update types
        if (!item.updateMetadata && !item.$type?.endsWith('Update')) {
            continue;
        }
        
        try {
            const postData = extractPostDetails(item, actorMap, socialActivityCountsMap, includedData);
            if (postData) {
                posts.push(postData);
            }
        } catch (error) {
            logger.error(`Error extracting post details: ${error.message}`);
        }
    }
    
    logger.info(`Extracted ${posts.length} posts from batch`);
    return posts;
}

/**
 * Extracts details from a single post item.
 * 
 * @param {Object} item - A single item from the LinkedIn API response
 * @param {Object} actorMap - Map of actor entities
 * @param {Object} socialActivityCountsMap - Map of social activity counts
 * @param {Array} includedData - Full array of included items for deep search
 * @returns {Object|null} - Formatted post object or null if extraction fails
 * @private
 */
function extractPostDetails(item, actorMap, socialActivityCountsMap, includedData) {
    // Extract post ID
    let postId = null;
    let ugcPostId = null;
    const entityUrn = item.entityUrn || '';
    const updateMetadata = item.updateMetadata || {};
    
    // Try to get post ID from updateMetadata
    if (updateMetadata && updateMetadata.urn) {
        const postUrn = updateMetadata.urn;
        postId = postUrn;
        
        // Extract ugcPost ID if present
        if (postUrn.includes('ugcPost:')) {
            const ugcMatch = postUrn.split('ugcPost:');
            if (ugcMatch.length > 1) {
                ugcPostId = ugcMatch[1].split(',')[0].split(')')[0];
            }
        }
    }
    
    // Fallback to entityUrn
    if (!postId && entityUrn) {
        postId = entityUrn;
    }
    
    if (!postId) {
        return null;
    }
    
    // Extract author info
    const actor = item.actor || {};
    let authorName = "";
    let authorProfileId = "";
    let authorJobTitle = null;
    
    if (actor) {
        // Author name
        if (typeof actor.name === 'object' && actor.name.text) {
            authorName = actor.name.text;
        } else if (typeof actor.name === 'string') {
            authorName = actor.name;
        }
        
        // Profile ID
        if (typeof actor.name === 'object' && actor.name.attributes) {
            for (const attr of actor.name.attributes) {
                if (attr['*miniProfile']) {
                    const miniProfile = attr['*miniProfile'];
                    const urnParts = miniProfile.split(':');
                    authorProfileId = urnParts[urnParts.length - 1] || "";
                    break;
                }
            }
        }
        
        // Job title
        if (typeof actor.description === 'object' && actor.description.text) {
            authorJobTitle = actor.description.text;
        } else if (typeof actor.description === 'string') {
            authorJobTitle = actor.description;
        }
    }
    
    // Extract post content
    let postContent = "";
    const commentary = item.commentary || {};
    if (typeof commentary.text === 'object' && commentary.text.text) {
        postContent = commentary.text.text;
    } else if (typeof commentary.text === 'string') {
        postContent = commentary.text;
    }
    
    // Extract timestamp
    const timestamp = updateMetadata.timestamp || null;
    
    // Extract likes and comments - comprehensive check (from old project)
    let likes = 0;
    let comments = 0;
    let foundMetrics = false;
    
    // Helper function to extract social metrics from an item (like old project)
    const extractSocialMetrics = (source) => {
        let itemLikes = 0;
        let itemComments = 0;
        let found = false;
        
        // Check direct numLikes and numComments properties
        if (source.numLikes !== undefined) {
            itemLikes = source.numLikes || 0;
            found = true;
        }
        if (source.numComments !== undefined) {
            itemComments = source.numComments || 0;
            found = true;
        }
        
        // Check totalSocialActivityCounts
        if (source.totalSocialActivityCounts) {
            if (source.totalSocialActivityCounts.numLikes !== undefined) {
                itemLikes = source.totalSocialActivityCounts.numLikes || 0;
                found = true;
            }
            if (source.totalSocialActivityCounts.numComments !== undefined) {
                itemComments = source.totalSocialActivityCounts.numComments || 0;
                found = true;
            }
        }
        
        // Check reactions array
        if (source.reactions && Array.isArray(source.reactions)) {
            const totalReactions = source.reactions.reduce((acc, reaction) => 
                acc + (reaction.count || 0), 0);
            if (totalReactions > 0) {
                itemLikes = totalReactions;
                found = true;
            }
        }
        
        // Check reactionTypeCounts array
        if (source.reactionTypeCounts && Array.isArray(source.reactionTypeCounts)) {
            const totalReactions = source.reactionTypeCounts.reduce((acc, reaction) => 
                acc + (reaction.count || 0), 0);
            if (totalReactions > 0) {
                itemLikes = totalReactions;
                found = true;
            }
        }
        
        return { found, likes: itemLikes, comments: itemComments };
    };
    
    // Extract ALL possible IDs from this post (like old project does)
    const allPostIds = [];
    
    // Add simple post ID
    const simplePostId = postId.includes(':') ? postId.split(':').pop() : postId;
    if (simplePostId) allPostIds.push(simplePostId);
    
    // Add UGC post ID if different
    if (ugcPostId && ugcPostId !== simplePostId) {
        allPostIds.push(ugcPostId);
    }
    
    // Add full post ID
    if (postId && postId !== simplePostId) {
        allPostIds.push(postId);
    }
    
    // Add entity URN if available
    if (item.entityUrn) {
        allPostIds.push(item.entityUrn);
        // Extract any IDs from entity URN
        const activityMatch = item.entityUrn.match(/activity:(\d+)/);
        if (activityMatch && activityMatch[1]) allPostIds.push(activityMatch[1]);
        const ugcMatch = item.entityUrn.match(/ugcPost:(\d+)/);
        if (ugcMatch && ugcMatch[1]) allPostIds.push(ugcMatch[1]);
    }
    
    // Add URN from updateMetadata if available
    if (updateMetadata && updateMetadata.urn) {
        allPostIds.push(updateMetadata.urn);
        const activityMatch = updateMetadata.urn.match(/activity:(\d+)/);
        if (activityMatch && activityMatch[1]) allPostIds.push(activityMatch[1]);
    }
    
    // Method 1: Check directly on the update item itself
    const directMetrics = extractSocialMetrics(item);
    if (directMetrics.found) {
        likes = directMetrics.likes;
        comments = directMetrics.comments;
        foundMetrics = true;
    }
    
    // Method 2: Try ALL post IDs in social activity counts map (like old project)
    if (!foundMetrics) {
        for (const id of allPostIds) {
            if (socialActivityCountsMap[id]) {
                const mapMetrics = extractSocialMetrics(socialActivityCountsMap[id]);
                if (mapMetrics.found) {
                    likes = mapMetrics.likes;
                    comments = mapMetrics.comments;
                    foundMetrics = true;
                    break;
                }
            }
        }
    }
    
    // Method 3: DEEP SEARCH - Look through ALL included items (like old project Method 7)
    if (!foundMetrics && includedData && Array.isArray(includedData)) {
        logger.info(`Deep search for metrics - checking all IDs: ${allPostIds.join(', ')}`);
        
        for (const includedItem of includedData) {
            // Skip items that don't have social metrics properties
            if (!includedItem.numLikes && !includedItem.numComments && 
                !includedItem.reactionTypeCounts && !includedItem.reactions && 
                !includedItem.totalSocialActivityCounts) {
                continue;
            }
            
            // Check if this item is related to our post
            let isRelated = false;
            
            // Check if the item has any URNs that match our post
            for (const urn of allPostIds) {
                if (includedItem.urn === urn || includedItem.entityUrn === urn || 
                    (includedItem.urn && includedItem.urn.includes(urn)) || 
                    (includedItem.entityUrn && includedItem.entityUrn.includes(urn))) {
                    isRelated = true;
                    break;
                }
            }
            
            // If not directly related by URN, check if it contains our post ID in its JSON
            if (!isRelated) {
                const itemStr = JSON.stringify(includedItem);
                for (const id of allPostIds) {
                    if (itemStr.includes(id)) {
                        isRelated = true;
                        break;
                    }
                }
            }
            
            if (isRelated) {
                const deepMetrics = extractSocialMetrics(includedItem);
                if (deepMetrics.found) {
                    likes = deepMetrics.likes;
                    comments = deepMetrics.comments;
                    foundMetrics = true;
                    logger.info(`Found metrics via deep search: ${likes} likes, ${comments} comments`);
                    break;
                }
            }
        }
    }
    
    // Only return if we have essential fields
    if (!postId || !authorName || !postContent) {
        return null;
    }
    
    // Build post URL
    let postUrl = `https://www.linkedin.com/feed/update/${postId}`;
    if (ugcPostId) {
        postUrl = `https://www.linkedin.com/feed/update/urn:li:ugcPost:${ugcPostId}`;
    }
    
    return {
        postId: postId,
        postUrl: postUrl,
        ugcPostId: ugcPostId,
        authorName: authorName,
        authorProfileId: authorProfileId,
        authorJobTitle: authorJobTitle,
        postContent: postContent,
        timestamp: timestamp ? new Date(timestamp).toISOString() : null,
        likes: likes,
        comments: comments
    };
}

