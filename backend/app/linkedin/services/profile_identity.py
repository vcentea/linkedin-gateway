"""
LinkedIn Profile Identity Service - Identity Cards and HTML data extraction.
"""
import logging
import re
import httpx
from typing import Dict, Any

from .base import LinkedInServiceBase
from ..utils.profile_id_extractor import extract_profile_id

logger = logging.getLogger(__name__)


class LinkedInProfileIdentityService(LinkedInServiceBase):
    """Service for fetching LinkedIn profile identity data."""
    
    async def get_profile_identity_cards(self, profile_id: str) -> Dict[str, Any]:
        """
        Fetch profile identity cards data (vanity name, first/last name, follower counts).
        
        URL pattern from user:
        /graphql?includeWebMetadata=true&variables=(profileUrn:urn%3Ali%3Afsd_profile%3A{profile_id})
        &queryId=voyagerIdentityDashProfileCards.c5c6ae006152475b00720b4f9b83f6ff
        
        Returns:
            Dictionary with identity data (vanity_name, first_name, last_name, follower_count)
        """
        logger.info(f"[IDENTITY_CARDS] ========================================")
        logger.info(f"[IDENTITY_CARDS] Fetching identity cards for: {profile_id}")
        logger.info(f"[IDENTITY_CARDS] ========================================")
        
        profile_urn_encoded = f"urn%3Ali%3Afsd_profile%3A{profile_id}"
        url = (
            f"{self.GRAPHQL_BASE_URL}?"
            f"includeWebMetadata=true"
            f"&variables=(profileUrn:{profile_urn_encoded})"
            f"&queryId=voyagerIdentityDashProfileCards.c5c6ae006152475b00720b4f9b83f6ff"
        )
        
        logger.info(f"[IDENTITY_CARDS] Request URL: {url}")
        
        try:
            data = await self._make_request(url, debug_endpoint_type="identity_cards")
            logger.info(f"[IDENTITY_CARDS] Raw response keys: {list(data.keys())}")
            
            if 'included' in data:
                logger.info(f"[IDENTITY_CARDS] 'included' array length: {len(data['included'])}")
            else:
                logger.warning(f"[IDENTITY_CARDS] No 'included' key in response!")
            
            identity_data = self._extract_identity_data(data, profile_id)
            
            logger.info(f"[IDENTITY_CARDS] ========================================")
            logger.info(f"[IDENTITY_CARDS] Extraction results:")
            logger.info(f"[IDENTITY_CARDS]   Vanity Name: {identity_data.get('vanity_name', 'N/A')}")
            logger.info(f"[IDENTITY_CARDS]   First Name: {identity_data.get('first_name', 'N/A')}")
            logger.info(f"[IDENTITY_CARDS]   Last Name: {identity_data.get('last_name', 'N/A')}")
            logger.info(f"[IDENTITY_CARDS]   Follower Count: {identity_data.get('follower_count', 0)}")
            logger.info(f"[IDENTITY_CARDS] ========================================")
            
            return identity_data
        except Exception as e:
            logger.error(f"[IDENTITY_CARDS] ✗ Error fetching identity cards: {str(e)}")
            logger.exception(e)
            return {
                'vanity_name': 'N/A',
                'first_name': 'N/A',
                'last_name': 'N/A',
                'follower_count': 0
            }
    
    def _extract_identity_data(self, json_data: Dict[str, Any], profile_id: str) -> Dict[str, Any]:
        """Extract identity data from LinkedIn API response."""
        identity_data = {
            'vanity_name': 'N/A',
            'first_name': 'N/A',
            'last_name': 'N/A',
            'follower_count': 0
        }
        
        try:
            included = json_data.get('included', [])
            logger.info(f"[IDENTITY_EXTRACT] Processing {len(included)} items, looking for profile ID: {profile_id}")
            
            if not included:
                logger.warning(f"[IDENTITY_EXTRACT] ✗ No 'included' array in response")
                return identity_data
            
            found_profile = False
            
            for idx, item in enumerate(included):
                item_type = item.get('$type', '')
                entity_urn = item.get('entityUrn', '')
                
                if 'Profile' in item_type and profile_id in entity_urn:
                    logger.info(f"[IDENTITY_EXTRACT] Found Profile object at index {idx} with matching entityUrn")
                    logger.info(f"[IDENTITY_EXTRACT]   - Type: {item_type}")
                    logger.info(f"[IDENTITY_EXTRACT]   - EntityUrn: {entity_urn}")
                    
                    if 'publicIdentifier' not in item:
                        logger.info(f"[IDENTITY_EXTRACT]   ⚠️  This profile object does NOT have publicIdentifier, continuing search...")
                        continue
                    
                    logger.info(f"[IDENTITY_EXTRACT] ✓ Found complete Profile object at index {idx}")
                    found_profile = True
                    
                    if 'firstName' in item:
                        identity_data['first_name'] = item.get('firstName', 'N/A')
                        logger.info(f"[IDENTITY_EXTRACT]   - First Name: {identity_data['first_name']}")
                    
                    if 'lastName' in item:
                        identity_data['last_name'] = item.get('lastName', 'N/A')
                        logger.info(f"[IDENTITY_EXTRACT]   - Last Name: {identity_data['last_name']}")
                    
                    if 'publicIdentifier' in item:
                        identity_data['vanity_name'] = item.get('publicIdentifier', 'N/A')
                        logger.info(f"[IDENTITY_EXTRACT]   - Public Identifier: {identity_data['vanity_name']}")
                
                # Extract follower count - be robust about the data type
                if 'followerCount' in item:
                    follower_count = item.get('followerCount')
                    # Handle various data types: int, str, None
                    if follower_count is not None:
                        try:
                            # Try to convert to int if it's a string
                            if isinstance(follower_count, str):
                                follower_count = int(follower_count.replace(',', '').replace('.', ''))
                            elif isinstance(follower_count, (int, float)):
                                follower_count = int(follower_count)
                            else:
                                follower_count = 0
                            
                            if identity_data['follower_count'] == 0:
                                identity_data['follower_count'] = follower_count
                                logger.info(f"[IDENTITY_EXTRACT] ✓ Found follower count at index {idx}: {identity_data['follower_count']}")
                        except (ValueError, AttributeError) as e:
                            logger.warning(f"[IDENTITY_EXTRACT] Could not parse follower count: {follower_count}, error: {e}")
                            identity_data['follower_count'] = 0
            
            if not found_profile:
                logger.warning(f"[IDENTITY_EXTRACT] ✗ No matching Profile object found for profile ID: {profile_id}")
                logger.info(f"[IDENTITY_EXTRACT] Checked {len(included)} items")
            
        except Exception as e:
            logger.error(f"[IDENTITY_EXTRACT] Error extracting identity data: {str(e)}")
            logger.exception(e)
        
        return identity_data
    
    async def get_headline_location_and_degree(self, vanity_name: str, profile_id: str = None) -> Dict[str, str]:
        """
        Fetch headline, location, and connection degree from the profile HTML page.
        
        URL: https://www.linkedin.com/in/{vanity_name}/
        
        Returns:
            Dictionary with 'headline', 'location', and 'con_degree'
        """
        logger.info(f"[HTML_EXTRACT] Fetching data for vanity_name: {vanity_name}")
        
        result = {
            'headline': 'N/A',
            'location': 'N/A',
            'con_degree': 'N/A'
        }
        
        if not vanity_name or vanity_name == 'N/A':
            logger.warning("[HTML_EXTRACT] No vanity name provided")
            return result
        
        url = f"https://www.linkedin.com/in/{vanity_name}/"
        
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers, cookies=self.linkedin_cookies)
                
                logger.info(f"[HTML_EXTRACT] Response status: {response.status_code}")
                
                if response.status_code != 200:
                    logger.warning(f"[HTML_EXTRACT] Non-200 status: {response.status_code}")
                    return result
                
                html_content = response.text
                logger.info(f"[HTML_EXTRACT] HTML length: {len(html_content)} chars")
                
                headline = None
                
                if profile_id:
                    logger.info(f"[HTML_EXTRACT] Searching for headline with profile_id: {profile_id}")
                    escaped_profile_id = re.escape(profile_id)
                    headline_pattern = rf'&quot;entityUrn&quot;:&quot;urn:li:fsd_profile:{escaped_profile_id}&quot;.*?&quot;headline&quot;:&quot;((?:[^&]|&(?!quot;))+?)&quot;'
                    headline_match = re.search(headline_pattern, html_content, re.DOTALL)
                    if headline_match:
                        headline = headline_match.group(1)
                        logger.info(f"[HTML_EXTRACT] Found headline via profile_id match")
                
                if not headline:
                    logger.info(f"[HTML_EXTRACT] Searching for headline with vanity_name: {vanity_name}")
                    escaped_vanity = re.escape(vanity_name)
                    headline_pattern = rf'&quot;publicIdentifier&quot;:&quot;{escaped_vanity}&quot;.*?&quot;headline&quot;:&quot;((?:[^&]|&(?!quot;))+?)&quot;'
                    headline_match = re.search(headline_pattern, html_content, re.DOTALL)
                    if headline_match:
                        headline = headline_match.group(1)
                        logger.info(f"[HTML_EXTRACT] Found headline via vanity_name match")
                
                if not headline:
                    headline_pattern = rf'&quot;publicIdentifier&quot;:&quot;{re.escape(vanity_name)}&quot;.*?&quot;multiLocaleHeadline&quot;:\[{{&quot;value&quot;:&quot;((?:[^&]|&(?!quot;))+?)&quot;'
                    headline_match = re.search(headline_pattern, html_content, re.DOTALL)
                    if headline_match:
                        headline = headline_match.group(1)
                        logger.info(f"[HTML_EXTRACT] Found headline via multiLocaleHeadline + vanity match")
                
                if headline:
                    headline = headline.replace('&#92;u', '\\u')
                    headline = headline.replace('&amp;', '&')
                    headline = headline.replace('&lt;', '<')
                    headline = headline.replace('&gt;', '>')
                    
                    try:
                        headline = headline.encode('latin1').decode('unicode-escape')
                        headline = headline.encode('utf-16', 'surrogatepass').decode('utf-16')
                    except Exception as e:
                        logger.warning(f"[HTML_EXTRACT] Unicode decode failed: {e}, keeping original")
                        headline = headline.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
                    
                    result['headline'] = headline
                    logger.info(f"[HTML_EXTRACT] ✓ Headline: {headline[:80]}...")
                else:
                    logger.warning(f"[HTML_EXTRACT] Could not find headline for vanity: {vanity_name}, profile_id: {profile_id}")
                
                # Extract location
                location_pattern = r'&quot;defaultLocalizedName&quot;:&quot;([^&]+(?:,|, )[^&]+)&quot;'
                location_match = re.search(location_pattern, html_content)
                
                if location_match:
                    location = location_match.group(1)
                    location = location.replace('&amp;', '&')
                    result['location'] = location
                    logger.info(f"[HTML_EXTRACT] ✓ Location: {location}")
                else:
                    location_pattern_simple = r'&quot;defaultLocalizedName&quot;:&quot;([^&]+)&quot;'
                    location_match = re.search(location_pattern_simple, html_content)
                    if location_match:
                        location = location_match.group(1)
                        location = location.replace('&amp;', '&')
                        result['location'] = location
                        logger.info(f"[HTML_EXTRACT] ✓ Location (simple): {location}")
                    else:
                        logger.warning("[HTML_EXTRACT] Could not find location")
                
                # Extract connection degree
                member_rel_pattern = r'&quot;\*memberRelationship&quot;:&quot;(urn:li:fsd_memberRelationship:[^&]+)&quot;'
                member_rel_match = re.search(member_rel_pattern, html_content)
                
                if member_rel_match:
                    member_rel_urn = member_rel_match.group(1)
                    logger.info(f"[HTML_EXTRACT] Found memberRelationship URN: {member_rel_urn}")
                    
                    if re.search(rf'{re.escape(member_rel_urn)}.*?&quot;\*connection&quot;:&quot;urn:li:fsd_connection:', html_content, re.DOTALL):
                        result['con_degree'] = '1st'
                        logger.info(f"[HTML_EXTRACT] ✓ Connection Degree: 1st")
                    else:
                        distance_pattern = rf'{re.escape(member_rel_urn)}.*?&quot;memberDistance&quot;:&quot;(DISTANCE_[23])&quot;'
                        distance_match = re.search(distance_pattern, html_content, re.DOTALL)
                        if distance_match:
                            distance = distance_match.group(1)
                            if distance == 'DISTANCE_2':
                                result['con_degree'] = '2nd'
                                logger.info(f"[HTML_EXTRACT] ✓ Connection Degree: 2nd")
                            elif distance == 'DISTANCE_3':
                                result['con_degree'] = '3rd'
                                logger.info(f"[HTML_EXTRACT] ✓ Connection Degree: 3rd")
                        else:
                            logger.warning("[HTML_EXTRACT] Could not determine connection degree")
                else:
                    logger.warning("[HTML_EXTRACT] Could not find memberRelationship")
                
        except Exception as e:
            logger.error(f"[HTML_EXTRACT] Error: {str(e)}")
            logger.exception(e)
        
        return result
    
    async def scrape_profile_identity(self, profile_id_or_url: str) -> Dict[str, Any]:
        """
        Scrape identity data for a LinkedIn profile.
        
        Returns identity cards data + HTML data (headline, location, con_degree)
        """
        logger.info(f"[PROFILE_IDENTITY] Starting identity scrape for: {profile_id_or_url}")
        
        profile_id = await extract_profile_id(
            profile_input=profile_id_or_url,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        logger.info(f"[PROFILE_IDENTITY] Using profile ID: {profile_id}")
        
        # Get identity cards data
        identity = await self.get_profile_identity_cards(profile_id)
        vanity_name = identity['vanity_name']
        
        # Get HTML data
        html_data = await self.get_headline_location_and_degree(vanity_name, profile_id)
        
        result = {
            'linkedin_id': profile_id,
            'vanity_name': identity['vanity_name'],
            'profile_url': f"https://www.linkedin.com/in/{identity['vanity_name']}",
            'first_name': identity['first_name'],
            'last_name': identity['last_name'],
            'name': f"{identity['first_name']} {identity['last_name']}".strip(),
            'headline': html_data['headline'],
            'location': html_data['location'],
            'con_degree': html_data['con_degree'],
            'follower_count': identity['follower_count']
        }
        
        logger.info(f"[PROFILE_IDENTITY] Identity scrape completed for {profile_id}")
        return result

