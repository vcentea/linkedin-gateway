/**
 * LinkedIn Post Data Processor
 * 
 * This module contains functions for processing LinkedIn API responses to extract post data.
 * It replicates the logic from the old project's processPostsData function 1:1.
 * 
 * This is a standalone, reusable module that can be imported wherever LinkedIn post processing is needed.
 */

import { logger } from '../../shared/utils/logger.js';

/**
 * Process LinkedIn API data to extract posts
 * This is a 1:1 replication of the old project's processPostsData function
 * 
 * @param {Object} data - The full LinkedIn API response
 * @returns {Array<Object>} - Array of processed post objects
 */
export async function processPostsData(data) {
    const processedPosts = [];
    
    try {
        logger.info('Starting to process posts data');
        
        if (!data) {
            logger.error('Error: data is null or undefined');
            return processedPosts;
        }
        
        if (typeof data !== 'object') {
            logger.error(`Error: data is not an object, got type: ${typeof data}`);
            return processedPosts;
        }
        
        logger.info(`Data keys: ${Object.keys(data).join(', ')}`);
        
        if (!data.included || !Array.isArray(data.included)) {
            logger.error('Error: data.included is not an array or is missing');
            return processedPosts;
        }
        
        logger.info(`Found ${data.included.length} included items`);
        
        // Create maps for quick lookup (like old project)
        const includedMap = {};
        const socialDetailMap = {};
        const actorMap = {};
        const contentMap = {};
        const shareContentMap = {};
        const socialActivityCountsMap = {};
        
        // Process included items for easier lookup
        data.included.forEach(item => {
            if (item.entityUrn) {
                includedMap[item.entityUrn] = item;
                
                // Map social details
                if (item.$type && item.$type.includes('SocialDetail')) {
                    socialDetailMap[item.entityUrn] = item;
                }
                
                // Map actor profiles
                if (item.$type && item.$type.includes('MiniProfile')) {
                    actorMap[item.entityUrn] = item;
                }
                
                // Map content items
                if (item.$type && (item.$type.includes('ShareContent') || item.$type.includes('ShareUpdate'))) {
                    contentMap[item.entityUrn] = item;
                    
                    // Also map by activity URN for easier lookup
                    if (item.activity) {
                        shareContentMap[item.activity] = item;
                    }
                }
                
                // Map SocialActivityCounts by post ID (COMPREHENSIVE - like old project)
                if (item.$type && (
                    item.$type.includes('SocialActivityCounts') || 
                    item.$type.includes('socialActivityCounts')
                )) {
                    // Extract the activity ID from the URN
                    const urnMatch = item.urn ? item.urn.match(/activity:(\d+)/) : null;
                    const entityUrnMatch = item.entityUrn ? item.entityUrn.match(/activity:(\d+)/) : null;
                    
                    // Extract ugcPost IDs for video posts
                    const ugcPostMatch = item.urn ? item.urn.match(/ugcPost:(\d+)/) : null;
                    const entityUgcPostMatch = item.entityUrn ? item.entityUrn.match(/ugcPost:(\d+)/) : null;
                    
                    // Look for article IDs
                    const articleMatch = item.urn ? item.urn.match(/article:(\d+)/) : null;
                    const entityArticleMatch = item.entityUrn ? item.entityUrn.match(/article:(\d+)/) : null;
                    
                    // Look for video asset IDs
                    const videoAssetMatch = item.urn ? item.urn.match(/videoAsset:(\d+)/) : null;
                    const entityVideoAssetMatch = item.entityUrn ? item.entityUrn.match(/videoAsset:(\d+)/) : null;
                    
                    if (urnMatch && urnMatch[1]) {
                        socialActivityCountsMap[urnMatch[1]] = item;
                        logger.info(`Mapped social activity counts for post ID ${urnMatch[1]}`);
                    } else if (entityUrnMatch && entityUrnMatch[1]) {
                        socialActivityCountsMap[entityUrnMatch[1]] = item;
                        logger.info(`Mapped social activity counts for post ID ${entityUrnMatch[1]} from entityUrn`);
                    } else if (ugcPostMatch && ugcPostMatch[1]) {
                        socialActivityCountsMap[ugcPostMatch[1]] = item;
                        logger.info(`Mapped social activity counts for ugcPost ID ${ugcPostMatch[1]}`);
                    } else if (entityUgcPostMatch && entityUgcPostMatch[1]) {
                        socialActivityCountsMap[entityUgcPostMatch[1]] = item;
                        logger.info(`Mapped social activity counts for ugcPost ID ${entityUgcPostMatch[1]} from entityUrn`);
                    } else if (articleMatch && articleMatch[1]) {
                        socialActivityCountsMap[articleMatch[1]] = item;
                        logger.info(`Mapped social activity counts for article ID ${articleMatch[1]}`);
                    } else if (entityArticleMatch && entityArticleMatch[1]) {
                        socialActivityCountsMap[entityArticleMatch[1]] = item;
                        logger.info(`Mapped social activity counts for article ID ${entityArticleMatch[1]} from entityUrn`);
                    } else if (videoAssetMatch && videoAssetMatch[1]) {
                        socialActivityCountsMap[videoAssetMatch[1]] = item;
                        logger.info(`Mapped social activity counts for videoAsset ID ${videoAssetMatch[1]}`);
                    } else if (entityVideoAssetMatch && entityVideoAssetMatch[1]) {
                        socialActivityCountsMap[entityVideoAssetMatch[1]] = item;
                        logger.info(`Mapped social activity counts for videoAsset ID ${entityVideoAssetMatch[1]} from entityUrn`);
                    }
                    
                    // Also map by the full URN for more reliable lookups
                    if (item.urn) {
                        socialActivityCountsMap[item.urn] = item;
                    }
                    if (item.entityUrn) {
                        socialActivityCountsMap[item.entityUrn] = item;
                    }
                    
                    // Log direct social metrics if available
                    if (item.numLikes !== undefined || item.numComments !== undefined) {
                        logger.info(`Direct social metrics - Likes: ${item.numLikes}, Comments: ${item.numComments}`);
                    }
                }
            }
        });
        
        logger.info(`Mapped ${Object.keys(socialDetailMap).length} social details, ${Object.keys(actorMap).length} actors, and ${Object.keys(contentMap).length} content items`);
        logger.info(`Mapped ${Object.keys(socialActivityCountsMap).length} social activity counts`);
        
        // Find all updates/activities that could be posts
        const updates = [];
        
        // First check in the main data structure
        if (data.data && data.data.data && data.data.data.feedDashProfileUpdatesByMemberShareFeed) {
            const feedData = data.data.data.feedDashProfileUpdatesByMemberShareFeed;
            if (feedData.elements && Array.isArray(feedData.elements)) {
                logger.info(`Found ${feedData.elements.length} elements in feedDashProfileUpdatesByMemberShareFeed`);
                updates.push(...feedData.elements);
            }
        }
        
        // Also check for updates directly in the included items
        data.included.forEach(item => {
            if (item.$type && (
                item.$type.includes('Update') || 
                item.$type.includes('Activity') || 
                item.$type.includes('ShareUpdate')
            )) {
                // Only add if not already in updates
                if (!updates.some(u => u.entityUrn === item.entityUrn)) {
                    updates.push(item);
                }
            }
        });
        
        logger.info(`Found a total of ${updates.length} potential updates/posts`);
        
        // Process each update/post (like old project)
        for (const update of updates) {
            try {
                const post = await processSinglePost(update, includedMap, socialDetailMap, actorMap, contentMap, shareContentMap, socialActivityCountsMap, data.included);
                
                // Only add post if it has id and text (like old project)
                if (post && post.id && post.text) {
                    processedPosts.push(post);
                    logger.info(`Successfully processed post ID: ${post.id}, text length: ${post.text.length}, has image: ${post.imageUrl ? 'yes' : 'no'}`);
                }
            } catch (error) {
                logger.error(`Error processing individual post: ${error}`);
            }
        }
    } catch (error) {
        logger.error(`Error in processPostsData: ${error}`);
        throw error;
    }
    
    logger.info(`Successfully processed ${processedPosts.length} posts with text content`);
    return processedPosts;
}

/**
 * Process a single post from the LinkedIn API response
 * This replicates the old project's logic exactly
 * 
 * @param {Object} update - The update/post item
 * @param {Object} includedMap - Map of all included items
 * @param {Object} socialDetailMap - Map of social detail items
 * @param {Object} actorMap - Map of actor/profile items
 * @param {Object} contentMap - Map of content items
 * @param {Object} shareContentMap - Map of share content items by activity
 * @param {Object} socialActivityCountsMap - Map of social activity counts
 * @param {Array} includedData - Full array of included items
 * @returns {Object|null} - Processed post object or null
 */
async function processSinglePost(update, includedMap, socialDetailMap, actorMap, contentMap, shareContentMap, socialActivityCountsMap, includedData) {
    try {
        // Initialize post object with default values (like old project)
        const post = {
            id: '',
            text: '',
            date: '',
            rawDateStr: '',  // Relative time string from LinkedIn (e.g., "1d", "2w ago")
            likes: 0,
            comments: 0,
            url: '',
            imageUrl: '',
            isVideo: false,
            hasVideo: false,
            videoType: '',
            ugcPostId: '',
            articleId: '',
            videoAssetId: '',
            authorName: '',
            authorProfileId: ''
        };
    
    // Extract post ID (COMPREHENSIVE - like old project)
    let postId = '';
    let activityUrn = '';
    let ugcPostId = '';
    let articleId = '';
    let videoAssetId = '';
    let allPostIds = []; // Store all possible IDs for this post
    
    // Helper function to extract and store all possible IDs (like old project)
    const extractAndStoreIds = (urn) => {
        if (!urn) return;
        
        // Extract activity ID
        const activityMatch = urn.match(/activity:(\d+)/);
        if (activityMatch && activityMatch[1]) {
            if (!postId) {
                postId = activityMatch[1];
                activityUrn = urn;
            }
            allPostIds.push(activityMatch[1]);
        }
        
        // Extract ugcPost ID
        const ugcMatch = urn.match(/ugcPost:(\d+)/);
        if (ugcMatch && ugcMatch[1]) {
            if (!postId) {
                postId = ugcMatch[1];
                ugcPostId = ugcMatch[1];
                activityUrn = urn;
            } else if (!ugcPostId) {
                ugcPostId = ugcMatch[1];
            }
            allPostIds.push(ugcMatch[1]);
        }
        
        // Extract article ID
        const articleMatch = urn.match(/article:(\d+)/);
        if (articleMatch && articleMatch[1]) {
            articleId = articleMatch[1];
            if (!postId) {
                postId = articleMatch[1];
                activityUrn = urn;
            }
            allPostIds.push(articleMatch[1]);
        }
        
        // Extract videoAsset ID
        const videoAssetMatch = urn.match(/videoAsset:(\d+)/);
        if (videoAssetMatch && videoAssetMatch[1]) {
            videoAssetId = videoAssetMatch[1];
            if (!postId) {
                postId = videoAssetMatch[1];
                activityUrn = urn;
            }
            allPostIds.push(videoAssetMatch[1]);
        }
        
        // Store the full URN as well
        allPostIds.push(urn);
    };
    
    // Extract IDs from all possible locations (like old project)
    if (update.entityUrn) {
        extractAndStoreIds(update.entityUrn);
    }
    
    if (!postId && update.updateMetadata && update.updateMetadata.urn) {
        extractAndStoreIds(update.updateMetadata.urn);
    }
    
    if (!postId && update.activity) {
        extractAndStoreIds(update.activity);
    }
    
    // Extract IDs from content (like old project)
    if (update.content) {
        // Check for video components
        if (update.content.linkedInVideoComponent) {
            const videoComponent = update.content.linkedInVideoComponent;
            if (videoComponent.videoUrn) {
                extractAndStoreIds(videoComponent.videoUrn);
            }
            if (videoComponent.urn) {
                extractAndStoreIds(videoComponent.urn);
            }
            post.isVideo = true;
        }
        
        if (update.content.externalVideoComponent) {
            const videoComponent = update.content.externalVideoComponent;
            if (videoComponent.videoUrn) {
                extractAndStoreIds(videoComponent.videoUrn);
            }
            if (videoComponent.urn) {
                extractAndStoreIds(videoComponent.urn);
            }
            post.isVideo = true;
        }
        
        // Check for shareUrn or backendUrn
        if (update.content.shareUrn) {
            extractAndStoreIds(update.content.shareUrn);
        }
        
        if (update.content.backendUrn) {
            extractAndStoreIds(update.content.backendUrn);
        }
    }
    
    // Look for shareUrn or backendUrn in metadata (like old project)
    if (update.metadata) {
        if (update.metadata.shareUrn) {
            extractAndStoreIds(update.metadata.shareUrn);
        }
        
        if (update.metadata.backendUrn) {
            extractAndStoreIds(update.metadata.backendUrn);
        }
        
        // Some video posts have a specific video ID in the metadata
        if (update.metadata.video) {
            if (update.metadata.video.videoUrn) {
                extractAndStoreIds(update.metadata.video.videoUrn);
            }
            post.isVideo = true;
        }
    }
    
    // Set post ID and URL if found
    if (postId) {
        post.id = postId;
        
        // Set the URL based on the ID type (like old project)
        if (ugcPostId) {
            post.ugcPostId = ugcPostId;
            post.url = `https://www.linkedin.com/feed/update/urn:li:ugcPost:${ugcPostId}/`;
        } else if (articleId) {
            post.articleId = articleId;
            post.url = `https://www.linkedin.com/pulse/article/${articleId}/`;
        } else if (videoAssetId) {
            post.videoAssetId = videoAssetId;
            post.url = `https://www.linkedin.com/video/event/${videoAssetId}/`;
        } else {
            post.url = `https://www.linkedin.com/feed/update/urn:li:activity:${postId}/`;
        }
        
        logger.info(`Processing post ID: ${postId} (${allPostIds.length} total IDs found)`);
    } else {
        // Skip posts without an ID
        return null;
    }
    
    // Extract author information from update.actor
    if (update.actor) {
        // Extract author profile ID
        if (update.actor.entityUrn) {
            const actorIdMatch = update.actor.entityUrn.match(/fsd_profile:([A-Za-z0-9_-]+)/);
            if (actorIdMatch && actorIdMatch[1]) {
                post.authorProfileId = actorIdMatch[1];
            }
        }
        
        // Extract author name
        if (update.actor.name && update.actor.name.text) {
            post.authorName = update.actor.name.text;
        } else if (update.actor.name && typeof update.actor.name === 'string') {
            post.authorName = update.actor.name;
        }
        
        // Look up actor in actorMap if not found directly
        if (!post.authorName && update.actor.entityUrn && actorMap[update.actor.entityUrn]) {
            const actorProfile = actorMap[update.actor.entityUrn];
            if (actorProfile.firstName && actorProfile.lastName) {
                post.authorName = `${actorProfile.firstName} ${actorProfile.lastName}`;
            }
        }
    }
    
    // STEP 1: Extract text content (COMPREHENSIVE - like old project)
    let hasText = false;
    
    // Check for text in the update itself
    if (update.commentary && update.commentary.text) {
        if (typeof update.commentary.text === 'string') {
            post.text = update.commentary.text;
            hasText = true;
            logger.info(`Found text directly in update: ${post.text.substring(0, 50)}...`);
        } else if (update.commentary.text.text) {
            post.text = update.commentary.text.text;
            hasText = true;
            logger.info(`Found text in update.commentary.text.text: ${post.text.substring(0, 50)}...`);
        }
    }
    
    // If no text found, check in content references
    if (!hasText && update.content) {
        // Check if content has a direct reference to a ShareContent
        if (update.content.contentEntities && update.content.contentEntities.length > 0) {
            for (const contentEntity of update.content.contentEntities) {
                if (contentEntity.entityUrn) {
                    const contentItem = includedMap[contentEntity.entityUrn];
                    if (contentItem && contentItem.commentary && contentItem.commentary.text) {
                        if (typeof contentItem.commentary.text === 'string') {
                            post.text = contentItem.commentary.text;
                            hasText = true;
                            logger.info(`Found text in content entity: ${post.text.substring(0, 50)}...`);
                            break;
                        } else if (contentItem.commentary.text.text) {
                            post.text = contentItem.commentary.text.text;
                            hasText = true;
                            logger.info(`Found text in content entity text.text: ${post.text.substring(0, 50)}...`);
                            break;
                        }
                    }
                }
            }
        }
        
        // Check if content has a shareContent reference
        if (!hasText && update.content.shareContent) {
            const shareContentUrn = update.content.shareContent;
            const shareContent = includedMap[shareContentUrn];
            
            if (shareContent && shareContent.commentary && shareContent.commentary.text) {
                if (typeof shareContent.commentary.text === 'string') {
                    post.text = shareContent.commentary.text;
                    hasText = true;
                    logger.info(`Found text in shareContent: ${post.text.substring(0, 50)}...`);
                } else if (shareContent.commentary.text.text) {
                    post.text = shareContent.commentary.text.text;
                    hasText = true;
                    logger.info(`Found text in shareContent text.text: ${post.text.substring(0, 50)}...`);
                }
            }
        }
    }
    
    // If no text found, check in shareContentMap using activityUrn
    if (!hasText && activityUrn && shareContentMap[activityUrn]) {
        const shareContent = shareContentMap[activityUrn];
        if (shareContent.commentary && shareContent.commentary.text) {
            if (typeof shareContent.commentary.text === 'string') {
                post.text = shareContent.commentary.text;
                hasText = true;
                logger.info(`Found text in shareContentMap: ${post.text.substring(0, 50)}...`);
            } else if (shareContent.commentary.text.text) {
                post.text = shareContent.commentary.text.text;
                hasText = true;
                logger.info(`Found text in shareContentMap text.text: ${post.text.substring(0, 50)}...`);
            }
        }
    }
    
    // If still no text, look through all included items for this activity
    if (!hasText) {
        for (const item of includedData) {
            if (item.activity === activityUrn || 
                (item.entityUrn && item.entityUrn === activityUrn) ||
                (item.updateMetadata && item.updateMetadata.urn === activityUrn)) {
                
                if (item.commentary && item.commentary.text) {
                    if (typeof item.commentary.text === 'string') {
                        post.text = item.commentary.text;
                        hasText = true;
                        logger.info(`Found text in included item: ${post.text.substring(0, 50)}...`);
                        break;
                    } else if (item.commentary.text.text) {
                        post.text = item.commentary.text.text;
                        hasText = true;
                        logger.info(`Found text in included item text.text: ${post.text.substring(0, 50)}...`);
                        break;
                    }
                }
            }
        }
    }
    
    // Skip posts without text content (like old project)
    if (!hasText) {
        logger.info(`Skipping post ID ${postId} - no text content found`);
        return null;
    }
    
    // STEP 2: Extract date (COMPREHENSIVE - like old project)
    let dateFound = false;
    
    // Method 1: Check common date fields in the update object
    if (!dateFound && (update.publishedAt || update.published || update.createdAt)) {
        post.date = new Date(update.publishedAt || update.published || update.createdAt).toISOString();
        logger.info(`Found date in common field: ${post.date}`);
        dateFound = true;
    }
    
    // Method 2: Check updateMetadata
    if (!dateFound && update.updateMetadata && update.updateMetadata.publishedAt) {
        post.date = new Date(update.updateMetadata.publishedAt).toISOString();
        logger.info(`Found date in updateMetadata: ${post.date}`);
        dateFound = true;
    }
    
    // Method 3: Look for relative time strings in actor description
    if (!dateFound && update.actor && update.actor.subDescription) {
        // First check for accessibilityText which contains the exact date string from LinkedIn
        if (update.actor.subDescription.accessibilityText) {
            post.rawDateStr = update.actor.subDescription.accessibilityText;
            // Try to parse the relative time to calculate actual date
            const parsedDate = parseRelativeTime(post.rawDateStr);
            if (parsedDate) {
                post.date = parsedDate.toISOString();
                logger.info(`Found raw date string in accessibilityText: ${post.rawDateStr} -> calculated date: ${post.date}`);
            } else {
                // If we can't parse it, use current date as fallback
                post.date = new Date().toISOString();
                logger.info(`Found raw date string in accessibilityText but couldn't parse: ${post.rawDateStr}, using current date`);
            }
            dateFound = true;
        } else {
            let relativeTimeStr = '';
            
            if (typeof update.actor.subDescription === 'string') {
                relativeTimeStr = update.actor.subDescription;
            } else if (update.actor.subDescription.text) {
                relativeTimeStr = update.actor.subDescription.text;
            }
            
            if (relativeTimeStr) {
                const parsedDate = parseRelativeTime(relativeTimeStr);
                if (parsedDate) {
                    post.date = parsedDate.toISOString();
                    post.rawDateStr = relativeTimeStr;
                    logger.info(`Extracted relative date from actor description: ${relativeTimeStr} -> ${post.date}`);
                    dateFound = true;
                }
            }
        }
    }
    
    // Method 4: Check for timeContext field
    if (!dateFound && update.timeContext) {
        if (update.timeContext.accessibilityText) {
            post.rawDateStr = update.timeContext.accessibilityText;
            // Try to parse the relative time to calculate actual date
            const parsedDate = parseRelativeTime(post.rawDateStr);
            if (parsedDate) {
                post.date = parsedDate.toISOString();
                logger.info(`Found raw date string in timeContext.accessibilityText: ${post.rawDateStr} -> calculated date: ${post.date}`);
            } else {
                // If we can't parse it, use current date as fallback
                post.date = new Date().toISOString();
                logger.info(`Found raw date string in timeContext.accessibilityText but couldn't parse: ${post.rawDateStr}, using current date`);
            }
            dateFound = true;
        } else if (update.timeContext.text) {
            const timeContextText = typeof update.timeContext.text === 'string' 
                ? update.timeContext.text 
                : update.timeContext.text.text;
            
            if (timeContextText) {
                const parsedDate = parseRelativeTime(timeContextText);
                if (parsedDate) {
                    post.date = parsedDate.toISOString();
                    post.rawDateStr = timeContextText;
                    logger.info(`Extracted relative date from timeContext: ${timeContextText} -> ${post.date}`);
                    dateFound = true;
                }
            }
        }
    }
    
    // Method 5: Check related items for date info
    if (!dateFound) {
        for (const item of includedData) {
            if ((item.activity === activityUrn || item.entityUrn === activityUrn) && 
                (item.publishedAt || item.published || item.createdAt)) {
                post.date = new Date(item.publishedAt || item.published || item.createdAt).toISOString();
                logger.info(`Found date in related included item: ${post.date}`);
                dateFound = true;
                break;
            }
        }
    }
    
    // Method 6: If no date found, use current date as fallback
    if (!dateFound) {
        post.date = new Date().toISOString();
        logger.info(`No date found, using current date as fallback: ${post.date}`);
    }
    
        // STEP 3: Extract social activity (likes, comments) - COMPREHENSIVE (like old project)
        const socialMetrics = extractSocialMetrics(update, allPostIds, socialActivityCountsMap, includedData, includedMap, socialDetailMap);
        post.likes = socialMetrics.likes;
        post.comments = socialMetrics.comments;
        
        // STEP 4: Extract image URL if available (like old project)
        post.imageUrl = extractImageUrl(update, includedMap);
        
        // STEP 5: Check for video content (like old project)
        const videoInfo = extractVideoInfo(update, post);
        Object.assign(post, videoInfo);
        
        return post;
    } catch (error) {
        logger.error(`Error in processSinglePost: ${error}`);
        // Return null to skip this post instead of breaking the entire batch
        return null;
    }
}

/**
 * Parse relative time string (like "5m ago", "2h ago", etc.) to Date object
 * Like the old project
 */
function parseRelativeTime(relativeTimeStr) {
    const timeMatch = relativeTimeStr.match(/(\d+)\s*(m|minute|minutes|h|hour|hours|d|day|days|w|week|weeks|mo|month|months|y|year|years)(?:\s+ago)?/i);
    
    if (timeMatch) {
        const now = new Date();
        const value = parseInt(timeMatch[1]);
        const unit = timeMatch[2].toLowerCase();
        
        if (unit === 'm' || unit === 'minute' || unit === 'minutes') {
            now.setMinutes(now.getMinutes() - value);
        } else if (unit === 'h' || unit === 'hour' || unit === 'hours') {
            now.setHours(now.getHours() - value);
        } else if (unit === 'd' || unit === 'day' || unit === 'days') {
            now.setDate(now.getDate() - value);
        } else if (unit === 'w' || unit === 'week' || unit === 'weeks') {
            now.setDate(now.getDate() - (value * 7));
        } else if (unit === 'mo' || unit === 'month' || unit === 'months') {
            now.setMonth(now.getMonth() - value);
        } else if (unit === 'y' || unit === 'year' || unit === 'years') {
            now.setFullYear(now.getFullYear() - value);
        }
        
        return now;
    }
    
    return null;
}

/**
 * Extract social metrics (likes, comments) from various sources
 * This is the comprehensive extractSocialMetrics function from the old project
 */
function extractSocialMetrics(update, allPostIds, socialActivityCountsMap, includedData, includedMap, socialDetailMap) {
    let likes = 0;
    let comments = 0;
    let foundSocialDetails = false;
    
    // Helper function to check social metrics from an item (like old project)
    const checkSocialMetrics = (item) => {
        let foundMetrics = false;
        let itemLikes = 0;
        let itemComments = 0;
        
        // Check direct numLikes and numComments properties
        if (item.numLikes !== undefined) {
            itemLikes = item.numLikes || 0;
            foundMetrics = true;
        }
        
        if (item.numComments !== undefined) {
            itemComments = item.numComments || 0;
            foundMetrics = true;
        }
        
        // Check totalSocialActivityCounts
        if (item.totalSocialActivityCounts) {
            if (item.totalSocialActivityCounts.numLikes !== undefined) {
                itemLikes = item.totalSocialActivityCounts.numLikes || 0;
                foundMetrics = true;
            }
            if (item.totalSocialActivityCounts.numComments !== undefined) {
                itemComments = item.totalSocialActivityCounts.numComments || 0;
                foundMetrics = true;
            }
        }
        
        // Check reactions array
        if (item.reactions && Array.isArray(item.reactions)) {
            let totalReactions = 0;
            for (const reaction of item.reactions) {
                if (reaction.count) {
                    totalReactions += reaction.count;
                }
            }
            if (totalReactions > 0) {
                itemLikes = totalReactions;
                foundMetrics = true;
            }
        }
        
        // Check reactionTypeCounts array
        if (item.reactionTypeCounts && Array.isArray(item.reactionTypeCounts)) {
            let totalReactions = 0;
            for (const reaction of item.reactionTypeCounts) {
                if (reaction.count) {
                    totalReactions += reaction.count;
                }
            }
            if (totalReactions > 0) {
                itemLikes = totalReactions;
                foundMetrics = true;
            }
        }
        
        return { foundMetrics, likes: itemLikes, comments: itemComments };
    };
    
    // Method 1: Try all mapped IDs in the socialActivityCountsMap (like old project)
    if (!foundSocialDetails) {
        for (const id of allPostIds) {
            if (socialActivityCountsMap[id]) {
                const socialCounts = socialActivityCountsMap[id];
                const { foundMetrics, likes: itemLikes, comments: itemComments } = checkSocialMetrics(socialCounts);
                
                if (foundMetrics) {
                    likes = itemLikes;
                    comments = itemComments;
                    logger.info(`Found social metrics using ID ${id}: ${likes} likes, ${comments} comments`);
                    foundSocialDetails = true;
                    break;
                }
            }
        }
    }
    
    // Method 2: Direct socialDetail reference in the update (like old project)
    if (!foundSocialDetails) {
        let socialDetailUrn = '';
        
        if (update.socialDetail) {
            socialDetailUrn = update.socialDetail.urn || update.socialDetail;
        } else if (update['*socialDetail']) {
            socialDetailUrn = update['*socialDetail'];
        }
        
        if (socialDetailUrn) {
            const socialDetailItem = includedMap[socialDetailUrn] || socialDetailMap[socialDetailUrn];
            
            if (socialDetailItem) {
                const { foundMetrics, likes: itemLikes, comments: itemComments } = checkSocialMetrics(socialDetailItem);
                
                if (foundMetrics) {
                    likes = itemLikes;
                    comments = itemComments;
                    logger.info(`Found social details via URN: ${likes} likes, ${comments} comments`);
                    foundSocialDetails = true;
                }
            }
        }
    }
    
    // Method 3: Search included items for social details related to this post (like old project - deep search)
    if (!foundSocialDetails) {
        for (const id of allPostIds) {
            for (const item of includedData) {
                if (item.$type && (
                    item.$type.includes('SocialActivityCounts') || 
                    item.$type.includes('SocialDetail') ||
                    item.$type.includes('socialActivityCounts') ||
                    item.$type.includes('socialDetail')
                )) {
                    // Check if this social detail is related to our post
                    const itemStr = JSON.stringify(item);
                    if (itemStr.includes(id)) {
                        const { foundMetrics, likes: itemLikes, comments: itemComments } = checkSocialMetrics(item);
                        
                        if (foundMetrics) {
                            likes = itemLikes;
                            comments = itemComments;
                            logger.info(`Found social metrics in included items for ID ${id}: ${likes} likes, ${comments} comments`);
                            foundSocialDetails = true;
                            break;
                        }
                    }
                }
            }
            if (foundSocialDetails) break;
        }
    }
    
    // Method 4: Look for direct reaction counts in the update itself (like old project)
    if (!foundSocialDetails) {
        // Check reactionSummaries
        if (update.reactionSummaries && Array.isArray(update.reactionSummaries)) {
            let totalLikes = 0;
            for (const reaction of update.reactionSummaries) {
                if (reaction.count) {
                    totalLikes += reaction.count;
                }
            }
            if (totalLikes > 0) {
                likes = totalLikes;
                logger.info(`Found likes directly in reactionSummaries: ${likes}`);
                foundSocialDetails = true;
            }
        }
        
        // Check for direct counts in the update
        if (!foundSocialDetails) {
            const { foundMetrics, likes: itemLikes, comments: itemComments } = checkSocialMetrics(update);
            if (foundMetrics) {
                likes = itemLikes;
                comments = itemComments;
                logger.info(`Found metrics directly in update: ${likes} likes, ${comments} comments`);
                foundSocialDetails = true;
            }
        }
    }
    
    // Method 5: For video posts, look for video-specific social metrics (like old project)
    if (!foundSocialDetails && (update.content && (update.content.linkedInVideoComponent || update.content.externalVideoComponent))) {
        const videoComponent = update.content.linkedInVideoComponent || update.content.externalVideoComponent;
        const { foundMetrics, likes: itemLikes, comments: itemComments } = checkSocialMetrics(videoComponent);
        
        if (foundMetrics) {
            likes = itemLikes;
            comments = itemComments;
            logger.info(`Found metrics in videoComponent: ${likes} likes, ${comments} comments`);
            foundSocialDetails = true;
        }
        
        // Also check for social metrics in related video data
        if (!foundSocialDetails && videoComponent.urn) {
            for (const item of includedData) {
                if (item.entityUrn === videoComponent.urn || item.urn === videoComponent.urn) {
                    const { foundMetrics, likes: itemLikes, comments: itemComments } = checkSocialMetrics(item);
                    
                    if (foundMetrics) {
                        likes = itemLikes;
                        comments = itemComments;
                        logger.info(`Found metrics in video component related item: ${likes} likes, ${comments} comments`);
                        foundSocialDetails = true;
                        break;
                    }
                }
            }
        }
    }
    
    // Method 6: Look in update metadata (like old project)
    if (!foundSocialDetails && update.updateMetadata && update.updateMetadata.socialDetail) {
        const metaSocialDetail = update.updateMetadata.socialDetail;
        const { foundMetrics, likes: itemLikes, comments: itemComments } = checkSocialMetrics(metaSocialDetail);
        
        if (foundMetrics) {
            likes = itemLikes;
            comments = itemComments;
            logger.info(`Found social details in updateMetadata: ${likes} likes, ${comments} comments`);
            foundSocialDetails = true;
        }
    }
    
    // Method 7: Deep search for any social metrics related to this post (like old project)
    if (!foundSocialDetails) {
        const relatedUrns = new Set(allPostIds);
        
        if (update.entityUrn) {
            relatedUrns.add(update.entityUrn);
        }
        
        // Look for any items that might contain social metrics for this post
        for (const item of includedData) {
            // Skip items that don't have social metrics properties
            if (!item.numLikes && !item.numComments && 
                !item.reactionTypeCounts && !item.reactions && 
                !item.totalSocialActivityCounts) {
                continue;
            }
            
            // Check if this item is related to our post
            let isRelated = false;
            
            // Check if the item has any URNs that match our post
            for (const urn of relatedUrns) {
                if (item.urn === urn || item.entityUrn === urn || 
                    (item.urn && item.urn.includes(urn)) || 
                    (item.entityUrn && item.entityUrn.includes(urn))) {
                    isRelated = true;
                    break;
                }
            }
            
            // If not directly related by URN, check if it contains our post ID in its JSON
            if (!isRelated) {
                const itemStr = JSON.stringify(item);
                for (const id of allPostIds) {
                    if (itemStr.includes(id)) {
                        isRelated = true;
                        break;
                    }
                }
            }
            
            if (isRelated) {
                const { foundMetrics, likes: itemLikes, comments: itemComments } = checkSocialMetrics(item);
                
                if (foundMetrics) {
                    likes = itemLikes;
                    comments = itemComments;
                    logger.info(`Found metrics in deep search: ${likes} likes, ${comments} comments`);
                    foundSocialDetails = true;
                    break;
                }
            }
        }
    }
    
    return { likes, comments };
}

/**
 * Extract image URL from post (like old project)
 */
function extractImageUrl(update, includedMap) {
    let imageUrl = '';
    
    // Check for image in content
    if (update.content && update.content.imageComponent) {
        const imageComponent = update.content.imageComponent;
        if (imageComponent.images && imageComponent.images.length > 0) {
            const image = imageComponent.images[0];
            if (image.attributes && image.attributes.length > 0) {
                const attribute = image.attributes[0];
                if (attribute.detailData && attribute.detailData.vectorImage) {
                    const vectorImage = attribute.detailData.vectorImage;
                    if (vectorImage.rootUrl && vectorImage.artifacts && vectorImage.artifacts.length > 0) {
                        // Find the largest image
                        let largestArtifact = vectorImage.artifacts[0];
                        for (const artifact of vectorImage.artifacts) {
                            if (artifact.width > largestArtifact.width) {
                                largestArtifact = artifact;
                            }
                        }
                        imageUrl = vectorImage.rootUrl + largestArtifact.fileIdentifyingUrlPathSegment;
                        logger.info(`Found image URL: ${imageUrl}`);
                    }
                }
            }
        }
    }
    
    // If no image found, check in content entities
    if (!imageUrl && update.content && update.content.contentEntities) {
        for (const contentEntity of update.content.contentEntities) {
            if (contentEntity.entityUrn) {
                const contentItem = includedMap[contentEntity.entityUrn];
                if (contentItem && contentItem.thumbnails && contentItem.thumbnails.length > 0) {
                    const thumbnail = contentItem.thumbnails[0];
                    if (thumbnail.url) {
                        imageUrl = thumbnail.url;
                        logger.info(`Found image URL in content entity: ${imageUrl}`);
                        break;
                    }
                }
            }
        }
    }
    
    return imageUrl;
}

/**
 * Extract video information from post (like old project)
 */
function extractVideoInfo(update, post) {
    let isVideo = post.isVideo || false;
    let hasVideo = false;
    let videoType = '';
    
    // Check for video components (like old project)
    if (update.content) {
        if (update.content.linkedInVideoComponent) {
            logger.info(`Found LinkedIn video component in post ${post.id}`);
            isVideo = true;
            hasVideo = true;
            videoType = 'linkedin';
        } else if (update.content.externalVideoComponent) {
            logger.info(`Found external video component in post ${post.id}`);
            isVideo = true;
            hasVideo = true;
            videoType = 'external';
        }
    }
    
    // Check for video in metadata (like old project)
    if (!hasVideo && update.metadata && update.metadata.video) {
        logger.info(`Found video in metadata for post ${post.id}`);
        isVideo = true;
        hasVideo = true;
        videoType = 'metadata';
    }
    
    // Check for video in URNs (like old project)
    if (!hasVideo && (
        (post.videoAssetId && post.videoAssetId.length > 0) ||
        (post.url && post.url.includes('video'))
    )) {
        logger.info(`Detected video from URNs or URL for post ${post.id}`);
        isVideo = true;
        hasVideo = true;
        videoType = 'urn';
    }
    
    // Check for video in content entities (like old project)
    if (!hasVideo && update.content && update.content.contentEntities) {
        for (const contentEntity of update.content.contentEntities) {
            if (contentEntity.entityUrn && contentEntity.entityUrn.includes('video')) {
                logger.info(`Found video in content entity for post ${post.id}`);
                isVideo = true;
                hasVideo = true;
                videoType = 'entity';
                break;
            }
            
            // Check for video in thumbnails
            if (contentEntity.thumbnails && contentEntity.thumbnails.length > 0) {
                for (const thumbnail of contentEntity.thumbnails) {
                    if (thumbnail.videoUnion || 
                        (thumbnail.url && thumbnail.url.includes('video')) ||
                        (thumbnail.$type && thumbnail.$type.includes('Video'))) {
                        
                        logger.info(`Found video in thumbnail for post ${post.id}`);
                        isVideo = true;
                        hasVideo = true;
                        videoType = 'thumbnail';
                        break;
                    }
                }
                
                if (hasVideo) break;
            }
        }
    }
    
    return {
        isVideo,
        hasVideo,
        videoType
    };
}

export default {
    processPostsData,
    extractSocialMetrics,
    extractImageUrl,
    extractVideoInfo
};

