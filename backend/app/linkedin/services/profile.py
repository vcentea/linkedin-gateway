"""
LinkedIn Profile Service for profile data scraping.

Replicates the exact API calls and data extraction from the old project's
profile_service.js file.
"""
import logging
import re
import json
import httpx
from typing import Dict, Any, Optional, List

from .base import LinkedInServiceBase
from ..utils.profile_id_extractor import extract_profile_id

logger = logging.getLogger(__name__)


class LinkedInProfileService(LinkedInServiceBase):
    """
    Service for fetching LinkedIn profile data.
    
    Replicates the exact logic from old project's:
    - getProfileCards
    - getProfileData
    - formatLinkedInData
    - extractRecommendations
    - fetchProfilePosts (reuses posts service logic)
    """
    
    async def get_profile_experiences(self, profile_id: str) -> List[Dict[str, Any]]:
        """
        Fetch work experiences for a profile.
        
        URL pattern from user:
        /graphql?variables=(profileUrn:urn%3Ali%3Afsd_profile%3A{profileID},sectionType:experience,locale:en_US)
        &queryId=voyagerIdentityDashProfileComponents.c5d4db426a0f8247b8ab7bc1d660775a
        
        Returns:
            List of experience dictionaries with company, role, time, duration, description
        """
        logger.info(f"[PROFILE] Fetching work experiences for profile {profile_id}")
        
        # Encode the profileUrn parameter
        profile_urn_encoded = f"urn%3Ali%3Afsd_profile%3A{profile_id}"
        url = (
            f"{self.GRAPHQL_BASE_URL}?"
            f"variables=(profileUrn:{profile_urn_encoded},sectionType:experience,locale:en_US)"
            f"&queryId=voyagerIdentityDashProfileComponents.c5d4db426a0f8247b8ab7bc1d660775a"
        )
        
        logger.info(f"[PROFILE] Experience request URL: {url[:150]}...")
        
        try:
            data = await self._make_request(url, debug_endpoint_type="experiences")
            experiences = self._extract_experiences(data)
            logger.info(f"[PROFILE] Extracted {len(experiences)} work experiences")
            return experiences
        except Exception as e:
            logger.error(f"[PROFILE] Error fetching experiences: {str(e)}")
            raise
    
    def _get_safe(self, data: Dict[str, Any], path: List[Any], default: Optional[Any] = None) -> Optional[Any]:
        """
        Safely retrieves a value from a nested dictionary.
        
        Args:
            data: The dictionary to search within
            path: A list of keys representing the path to the value (can include integers for list indices)
            default: The value to return if the path is not found
            
        Returns:
            The retrieved value or the default
        """
        current = data
        for key in path:
            if isinstance(current, dict):
                if key not in current:
                    return default
                current = current[key]
            elif isinstance(current, list):
                if not isinstance(key, int) or key >= len(current):
                    return default
                current = current[key]
            else:
                return default
        return current
    
    def _extract_experiences(self, json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract work experiences using robust two-pass strategy:
        
        Pass 1: Build a complete map of all components by their URN
        Pass 2: Find the anchor (EXPERIENCE_VIEW_DETAILS) and traverse the graph
        
        This ensures we don't miss any experiences, including nested grouped roles.
        """
        experiences: List[Dict[str, Any]] = []

        try:
            included = json_data.get('included', [])
            if not included:
                logger.warning("[PROFILE] No 'included' array found")
                return experiences

            # ===== PASS 1: Build component map by URN =====
            logger.info(f"[PROFILE] Pass 1: Building component map from {len(included)} items")
            component_map = {}
            for item in included:
                urn = item.get('entityUrn')
                if urn:
                    component_map[urn] = item
            
            logger.info(f"[PROFILE] Pass 1: Indexed {len(component_map)} components by URN")

            # ===== PASS 2: Find anchor and traverse =====
            # Step 1: Find the main experience list URN
            main_experience_urn = None
            for urn in component_map.keys():
                if 'EXPERIENCE_VIEW_DETAILS' in urn and 'fsd_profile:' in urn:
                    main_experience_urn = urn
                    logger.info(f"[PROFILE] Pass 2: Found main experience anchor: {urn}")
                    break
            
            if not main_experience_urn:
                logger.warning("[PROFILE] Pass 2: No experience anchor found")
                return experiences
            
            # Step 2: Get the main experience list from our map
            main_list = component_map.get(main_experience_urn)
            if not main_list:
                logger.error(f"[PROFILE] Pass 2: Anchor URN not in map (shouldn't happen)")
                return experiences
            
            # Step 3: Get elements array
            elements = main_list.get('elements', [])
            if not elements:
                # Try alternate path
                elements = main_list.get('components', {}).get('elements', [])
            
            logger.info(f"[PROFILE] Pass 2: Found {len(elements)} experience blocks")
            
            # Check pagination
            paging = main_list.get('paging') or main_list.get('components', {}).get('paging')
            if paging:
                total = paging.get('total', 'unknown')
                count = paging.get('count', 'unknown')
                start = paging.get('start', 0)
                logger.warning(f"[PROFILE] PAGINATION: {count} of {total} experiences (start: {start})")
            
            if not elements:
                logger.warning("[PROFILE] Pass 2: No elements in main list")
                return experiences
            
            # Step 4: Process each experience block
            for idx, elem in enumerate(elements):
                try:
                    if not isinstance(elem, dict):
                        continue
                    
                    # Get entityComponent
                    components = elem.get('components', {})
                    entity = components.get('entityComponent')
                    
                    if not isinstance(entity, dict):
                        logger.debug(f"[PROFILE] Element {idx}: No entityComponent")
                        continue
                    
                    # Check for grouped entry (company with multiple roles)
                    # Path: subComponents.components[0].components[*]pagedListComponent
                    # The key is often '*pagedListComponent' (with asterisk prefix)
                    nested_urn = None
                    
                    # Safe navigation to subComponents.components
                    sub_comps_wrapper = entity.get('subComponents')
                    if isinstance(sub_comps_wrapper, dict):
                        sub_components = sub_comps_wrapper.get('components', [])
                        if isinstance(sub_components, list) and len(sub_components) > 0:
                            first_sub = sub_components[0]
                            if isinstance(first_sub, dict):
                                sub_comps = first_sub.get('components', {})
                                if isinstance(sub_comps, dict):
                                    # Check for pagedListComponent with various possible key names
                                    # Common patterns: 'pagedListComponent', '*pagedListComponent'
                                    for key in ['*pagedListComponent', 'pagedListComponent']:
                                        value = sub_comps.get(key)
                                        if value:
                                            # Value is either a string URN or an object with entityUrn
                                            nested_urn = value if isinstance(value, str) else (value.get('entityUrn') if isinstance(value, dict) else None)
                                            if nested_urn:
                                                logger.debug(f"[PROFILE] Element {idx}: Found grouped entry pointer via key '{key}'")
                                                break
                                    
                                    # Fallback: search all keys
                                    if not nested_urn:
                                        for key, value in sub_comps.items():
                                            if 'pagedlistcomponent' in key.lower() and value:
                                                nested_urn = value if isinstance(value, str) else (value.get('entityUrn') if isinstance(value, dict) else None)
                                                if nested_urn:
                                                    logger.debug(f"[PROFILE] Element {idx}: Found grouped entry pointer via fallback key '{key}'")
                                                    break
                    
                    if nested_urn:
                        # GROUPED ENTRY: Company with multiple roles
                        # For grouped entries, the parent block contains:
                        # - titleV2.text.text = Company Name (e.g., "SportsVisio, Inc.")
                        # - subtitle.text.text = Total Duration (e.g., "2 yrs 9 mos")
                        # We DON'T extract the parent itself as an experience.
                        # We ONLY extract the nested child roles.
                        
                        # Extract company name from titleV2
                        company_name = ''
                        titleV2 = entity.get('titleV2')
                        if isinstance(titleV2, dict):
                            text_obj = titleV2.get('text')
                            if isinstance(text_obj, dict):
                                company_name = text_obj.get('text', '')
                            elif isinstance(text_obj, str):
                                company_name = text_obj
                        
                        # Extract total duration from subtitle (for logging only)
                        total_duration = ''
                        subtitle = entity.get('subtitle')
                        if isinstance(subtitle, dict):
                            text_obj = subtitle.get('text')
                            if isinstance(text_obj, dict):
                                total_duration = text_obj.get('text', '')
                            elif isinstance(text_obj, str):
                                total_duration = text_obj
                        
                        logger.info(f"[PROFILE] Element {idx}: Grouped company '{company_name}' ({total_duration}) - extracting nested roles")
                        
                        # Look up nested list in our component map
                        nested_list = component_map.get(nested_urn)
                        if nested_list:
                            nested_elements = nested_list.get('elements', [])
                            if not nested_elements:
                                nested_elements = nested_list.get('components', {}).get('elements', [])
                            
                            logger.info(f"[PROFILE] Found {len(nested_elements)} roles for '{company_name}'")
                            
                            # Extract ONLY the nested child roles (not the parent)
                            for role_idx, role_elem in enumerate(nested_elements):
                                if isinstance(role_elem, dict):
                                    role_comps = role_elem.get('components', {})
                                    role_entity = role_comps.get('entityComponent')
                                    if isinstance(role_entity, dict):
                                        exp = self._extract_one_experience(role_entity, company_override=company_name)
                                        if exp:
                                            logger.debug(f"[PROFILE] Extracted role {role_idx + 1}/{len(nested_elements)}: {exp.get('role')} at {company_name}")
                                            experiences.append(exp)
                        else:
                            logger.warning(f"[PROFILE] Nested URN not found in map: {nested_urn}")
                        
                        # Important: Continue to next element without extracting the parent
                        continue
                    
                    # SINGLE ENTRY: Standalone experience
                    # Before processing as single entry, do a final sanity check:
                    # If titleV2 exists but caption (dates) doesn't, this might be a parent block we missed
                    titleV2 = entity.get('titleV2')
                    caption = entity.get('caption')
                    
                    if titleV2 and not caption:
                        # This looks like a parent block without individual role dates
                        logger.warning(f"[PROFILE] Element {idx}: Skipping potential parent block (has title but no dates)")
                        continue
                    
                    exp = self._extract_one_experience(entity)
                    if exp:
                        experiences.append(exp)
                
                except Exception as e:
                    logger.warning(f"[PROFILE] Error on element {idx}: {e}", exc_info=True)
                    continue
            
            logger.info(f"[PROFILE] Successfully extracted {len(experiences)} total experiences")
        
        except Exception as e:
            logger.error(f"[PROFILE] Fatal error: {e}", exc_info=True)
        
        return experiences
    
    def _extract_one_experience(self, entity: Dict, company_override: str = None) -> Optional[Dict]:
        """Extract a single experience from entityComponent."""
        if not entity or not isinstance(entity, dict):
            return None
        
        # Helper to safely navigate nested dicts that might return None
        def safe_get_text(obj, *keys):
            """Safely navigate nested dicts, handling None returns."""
            current = obj
            for key in keys:
                if not isinstance(current, dict):
                    return ''
                current = current.get(key)
                if current is None:
                    return ''
            return current if isinstance(current, str) else ''
        
        # Title (required)
        title = safe_get_text(entity, 'titleV2', 'text', 'text')
        if not title:
            logger.debug("[PROFILE] No title found in entity")
            return None
        
        # Company - subtitle.text is the string value
        company = company_override
        if not company:
            subtitle = entity.get('subtitle')
            if isinstance(subtitle, dict):
                company = subtitle.get('text', '')
                if isinstance(company, dict):
                    # Sometimes it's nested further
                    company = company.get('text', '')
        
        logger.debug(f"[PROFILE] Extracted company: '{company}'")
        
        # Dates - caption.text is the string value
        dates = ''
        caption = entity.get('caption')
        if isinstance(caption, dict):
            dates = caption.get('text', '')
            if isinstance(dates, dict):
                dates = dates.get('text', '')
        
        # Location - metadata.text is the string value
        location = ''
        metadata = entity.get('metadata')
        if isinstance(metadata, dict):
            location = metadata.get('text', '')
            if isinstance(location, dict):
                location = location.get('text', '')
        
        # Description
        description = ''
        try:
            subcomps = entity.get('subComponents')
            if isinstance(subcomps, dict):
                components = subcomps.get('components', [])
                if isinstance(components, list):
                    for sc in components:
                        if not isinstance(sc, dict):
                            continue
                        sc_comps = sc.get('components')
                        if not isinstance(sc_comps, dict):
                            continue
                        fixed = sc_comps.get('fixedListComponent')
                        if isinstance(fixed, dict):
                            fixed_comps = fixed.get('components', [])
                            if isinstance(fixed_comps, list):
                                for fc in fixed_comps:
                                    if not isinstance(fc, dict):
                                        continue
                                    fc_comps = fc.get('components')
                                    if isinstance(fc_comps, dict):
                                        txt_comp = fc_comps.get('textComponent')
                                        if isinstance(txt_comp, dict):
                                            txt = safe_get_text(txt_comp, 'text', 'text')
                                            if txt:
                                                description = txt
                                                break
                        if description:
                            break
        except Exception as e:
            logger.debug(f"[PROFILE] Error extracting description: {e}")
        
        result = {
            'role': title,
            'company': company or 'N/A',
            'time_duration': dates or '',
            'location': location or '',
            'description': description or 'N/A'
        }
        
        # Parse dates
        if dates and '·' in dates:
            parts = dates.split('·')
            result['time_period'] = parts[0].strip()
            if len(parts) > 1:
                result['duration'] = parts[1].strip()
        
        logger.info(f"[PROFILE] ✓ {title} at {company or 'N/A'}")
        return result
    
    async def get_profile_identity_cards(self, profile_id: str) -> Dict[str, Any]:
        """
        Fetch profile identity cards data (vanity name, first/last name, follower counts).
        
        URL pattern from user:
        /graphql?includeWebMetadata=true&variables=(profileUrn:urn%3Ali%3Afsd_profile%3A{profile_id})
        &queryId=voyagerIdentityDashProfileCards.c5c6ae006152475b00720b4f9b83f6ff
        
        This endpoint is specifically used to extract:
        - Vanity name (publicIdentifier) from LinkedIn URLs (3 possible locations)
        - First name
        - Last name
        - Follower counts
        
        Returns:
            Dictionary with identity data (vanity_name, first_name, last_name, follower_count)
        """
        logger.info(f"[IDENTITY_CARDS] ========================================")
        logger.info(f"[IDENTITY_CARDS] Fetching identity cards for: {profile_id}")
        logger.info(f"[IDENTITY_CARDS] ========================================")
        
        # Encode the profileUrn parameter
        profile_urn_encoded = f"urn%3Ali%3Afsd_profile%3A{profile_id}"
        url = (
            f"{self.GRAPHQL_BASE_URL}?"
            f"includeWebMetadata=true"
            f"&variables=(profileUrn:{profile_urn_encoded})"
            f"&queryId=voyagerIdentityDashProfileCards.c5c6ae006152475b00720b4f9b83f6ff"
        )
        
        logger.info(f"[IDENTITY_CARDS] Request URL: {url}")
        
        try:
            data = await self._make_request(url, debug_endpoint_type="identity_cards_legacy")
            
            # Log the raw response structure
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
            # Return empty identity data on error
            return {
                'vanity_name': 'N/A',
                'first_name': 'N/A',
                'last_name': 'N/A',
                'follower_count': 0
            }
    
    def _extract_identity_data(self, json_data: Dict[str, Any], profile_id: str) -> Dict[str, Any]:
        """
        Extract identity data from LinkedIn API response.
        
        Finds the Profile object with matching entityUrn containing the profile_id,
        then extracts firstName, lastName, publicIdentifier, and followerCount directly.
        
        Args:
            json_data: The LinkedIn API response
            profile_id: The profile ID we're looking for (e.g., "ACoAAE6NWVkBs_w9UHFzV8oRIt_9bFJxdXlAEVM")
        
        Returns:
            Dictionary with vanity_name, first_name, last_name, follower_count
        """
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
            
            # Search through ALL items to collect data (don't break early)
            # Data might be spread across multiple objects in the included array
            found_profile = False
            
            for idx, item in enumerate(included):
                item_type = item.get('$type', '')
                entity_urn = item.get('entityUrn', '')
                
                # Check if this is a Profile object with matching entityUrn
                if 'Profile' in item_type and profile_id in entity_urn:
                    logger.info(f"[IDENTITY_EXTRACT] Found Profile object at index {idx} with matching entityUrn")
                    logger.info(f"[IDENTITY_EXTRACT]   - Type: {item_type}")
                    logger.info(f"[IDENTITY_EXTRACT]   - EntityUrn: {entity_urn}")
                    
                    # Check if this profile has publicIdentifier (the key field we need)
                    if 'publicIdentifier' not in item:
                        logger.info(f"[IDENTITY_EXTRACT]   ⚠️  This profile object does NOT have publicIdentifier, continuing search...")
                        continue
                    
                    # This profile has publicIdentifier, extract name fields
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
                    
                    # Don't break - continue searching for followerCount and headline in other items
                
                # Check for follower count in ANY item (might be in a different object) - be robust
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
            
            # Log if we didn't find the profile
            if not found_profile:
                logger.warning(f"[IDENTITY_EXTRACT] ✗ No matching Profile object found for profile ID: {profile_id}")
                logger.info(f"[IDENTITY_EXTRACT] Checked {len(included)} items")
            
        except Exception as e:
            logger.error(f"[IDENTITY_EXTRACT] Error extracting identity data: {str(e)}")
            logger.exception(e)
        
        return identity_data
    
    async def get_contact_info(self, member_identity: str) -> Dict[str, Any]:
        """
        Fetch contact information for a profile.
        
        URL pattern from user:
        /graphql?includeWebMetadata=true&variables=(memberIdentity:{username})
        &queryId=voyagerIdentityDashProfiles.c7452e58fa37646d09dae4920fc5b4b9
        
        Note: Uses publicIdentifier (username like 'izzword') not profile ID
        
        Returns:
            Dictionary with contact info (email, phone, website, birthday, connected date)
        """
        logger.info(f"[CONTACT_INFO] ========================================")
        logger.info(f"[CONTACT_INFO] Fetching contact info for: {member_identity}")
        logger.info(f"[CONTACT_INFO] ========================================")
        
        url = (
            f"{self.GRAPHQL_BASE_URL}?"
            f"includeWebMetadata=true"
            f"&variables=(memberIdentity:{member_identity})"
            f"&queryId=voyagerIdentityDashProfiles.c7452e58fa37646d09dae4920fc5b4b9"
        )
        
        logger.info(f"[CONTACT_INFO] Request URL: {url}")
        
        try:
            data = await self._make_request(url, debug_endpoint_type="contact_info_legacy")
            
            # Log the raw response structure
            logger.info(f"[CONTACT_INFO] Raw response keys: {list(data.keys())}")
            
            if 'included' in data:
                logger.info(f"[CONTACT_INFO] 'included' array length: {len(data['included'])}")
                
                # Log each item in included array
                for i, item in enumerate(data['included']):
                    item_type = item.get('$type', 'unknown')
                    logger.info(f"[CONTACT_INFO] included[{i}] type: {item_type}")
                    logger.info(f"[CONTACT_INFO] included[{i}] keys: {list(item.keys())[:20]}")  # First 20 keys
                    
                    # If this is the Profile object (included[1]), log key fields
                    if item_type == 'com.linkedin.voyager.dash.identity.profile.Profile':
                        logger.info(f"[CONTACT_INFO] ✓ Found Profile object at index {i}")
                        logger.info(f"[CONTACT_INFO]   - firstName: {item.get('firstName', 'N/A')}")
                        logger.info(f"[CONTACT_INFO]   - lastName: {item.get('lastName', 'N/A')}")
                        logger.info(f"[CONTACT_INFO]   - publicIdentifier: {item.get('publicIdentifier', 'N/A')}")
                        logger.info(f"[CONTACT_INFO]   - has emailAddress: {'emailAddress' in item}")
                        logger.info(f"[CONTACT_INFO]   - has websites: {'websites' in item and len(item.get('websites', [])) > 0}")
                        logger.info(f"[CONTACT_INFO]   - has birthDateOn: {'birthDateOn' in item}")
                        logger.info(f"[CONTACT_INFO]   - has headline: {'headline' in item}")
            else:
                logger.warning(f"[CONTACT_INFO] No 'included' key in response!")
            
            contact_info = self._extract_contact_info(data)
            
            logger.info(f"[CONTACT_INFO] ========================================")
            logger.info(f"[CONTACT_INFO] Extraction results:")
            logger.info(f"[CONTACT_INFO]   Email: {contact_info.get('email', 'N/A')}")
            logger.info(f"[CONTACT_INFO]   Phone: {contact_info.get('phone', 'N/A')}")
            logger.info(f"[CONTACT_INFO]   Website: {contact_info.get('website', 'N/A')}")
            logger.info(f"[CONTACT_INFO]   Birthday: {contact_info.get('birthday', 'N/A')}")
            logger.info(f"[CONTACT_INFO]   Connected: {contact_info.get('connected_date', 'N/A')}")
            logger.info(f"[CONTACT_INFO] ========================================")
            
            return contact_info
        except Exception as e:
            logger.error(f"[CONTACT_INFO] ✗ Error fetching contact info: {str(e)}")
            logger.exception(e)
            # Return empty contact info on error (not all profiles may have this data)
            return {
                'email': 'N/A',
                'phone': 'N/A',
                'website': 'N/A',
                'birthday': 'N/A',
                'connected_date': 'N/A'
            }
    
    def _extract_contact_info(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract contact information from LinkedIn API response.
        
        Searches through ALL items in 'included' array to find the data,
        regardless of order or position.
        
        Looking for:
        - Profile object ($type contains 'Profile'): emailAddress, websites, birthDateOn, phone numbers
        - Connection object ($type contains 'Connection'): createdAt (connected date)
        """
        contact_info = {
            'email': 'N/A',
            'phone': 'N/A',
            'website': 'N/A',
            'birthday': 'N/A',
            'connected_date': 'N/A'
        }
        
        try:
            included = json_data.get('included', [])
            logger.info(f"[CONTACT_INFO_EXTRACT] included array length: {len(included)}")
            
            if not included:
                logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ No 'included' array in response")
                return contact_info
            
            # Search through ALL items to find Profile and Connection objects
            profile_obj = None
            connection_obj = None
            
            logger.info(f"[CONTACT_INFO_EXTRACT] Searching through all {len(included)} items...")
            for idx, item in enumerate(included):
                item_type = item.get('$type', '')
                logger.info(f"[CONTACT_INFO_EXTRACT] Item {idx}: type = {item_type}")
                
                # Look for Profile object (contains contact info)
                if 'Profile' in item_type and profile_obj is None:
                    profile_obj = item
                    logger.info(f"[CONTACT_INFO_EXTRACT] ✓ Found Profile object at index {idx}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Keys: {list(item.keys())[:15]}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Has emailAddress: {'emailAddress' in item}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Has websites: {'websites' in item}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Has birthDateOn: {'birthDateOn' in item}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Has phoneNumbers: {'phoneNumbers' in item}")
                
                # Look for Connection object (contains connected date)
                if ('Connection' in item_type or 'memberRelationship' in item_type) and connection_obj is None:
                    connection_obj = item
                    logger.info(f"[CONTACT_INFO_EXTRACT] ✓ Found Connection object at index {idx}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Keys: {list(item.keys())[:10]}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Has createdAt: {'createdAt' in item}")
            
            # If no Profile object found, can't extract contact info
            if profile_obj is None:
                logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ No Profile object found in included array")
                return contact_info
            
            logger.info(f"[CONTACT_INFO_EXTRACT] ========================================")
            logger.info(f"[CONTACT_INFO_EXTRACT] Extracting from Profile object...")
            
            # Extract email
            logger.info(f"[CONTACT_INFO_EXTRACT] Attempting to extract email...")
            try:
                email_obj = profile_obj.get('emailAddress', {})
                if email_obj:
                    logger.info(f"[CONTACT_INFO_EXTRACT] emailAddress object: {email_obj}")
                    email = email_obj.get('emailAddress', 'N/A')
                    if email and email != 'N/A':
                        contact_info['email'] = email
                        logger.info(f"[CONTACT_INFO_EXTRACT] ✓ Found email: {email}")
                    else:
                        logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ emailAddress object exists but no email value")
                else:
                    logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ No emailAddress object in profile")
            except (KeyError, TypeError, AttributeError) as e:
                logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ Error extracting email: {e}")
            
            # Extract phone
            # Path: included -> [Profile Object] -> phoneNumbers -> [0] -> phoneNumber -> number
            logger.info(f"[CONTACT_INFO_EXTRACT] Attempting to extract phone...")
            try:
                phone_numbers = profile_obj.get('phoneNumbers', [])
                if phone_numbers and len(phone_numbers) > 0:
                    logger.info(f"[CONTACT_INFO_EXTRACT] phoneNumbers array length: {len(phone_numbers)}")
                    logger.info(f"[CONTACT_INFO_EXTRACT] first phoneNumbers element: {phone_numbers[0]}")
                    
                    # Navigate: phoneNumbers[0] -> phoneNumber -> number
                    phone_number_obj = phone_numbers[0].get('phoneNumber', {})
                    if phone_number_obj:
                        logger.info(f"[CONTACT_INFO_EXTRACT] phoneNumber object: {phone_number_obj}")
                        phone_number = phone_number_obj.get('number', 'N/A')
                        if phone_number and phone_number != 'N/A':
                            contact_info['phone'] = phone_number
                            logger.info(f"[CONTACT_INFO_EXTRACT] ✓ Found phone: {phone_number}")
                        else:
                            logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ phoneNumber object exists but no number value")
                    else:
                        logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ No phoneNumber object in first element")
                else:
                    logger.info(f"[CONTACT_INFO_EXTRACT] ℹ No phone numbers in array")
            except (KeyError, TypeError, AttributeError, IndexError) as e:
                logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ Error extracting phone: {e}")
            
            # Extract website
            logger.info(f"[CONTACT_INFO_EXTRACT] Attempting to extract website...")
            try:
                websites = profile_obj.get('websites', [])
                if websites and len(websites) > 0:
                    logger.info(f"[CONTACT_INFO_EXTRACT] websites array length: {len(websites)}")
                    logger.info(f"[CONTACT_INFO_EXTRACT] first website: {websites[0]}")
                    website_url = websites[0].get('url', 'N/A')
                    if website_url and website_url != 'N/A':
                        contact_info['website'] = website_url
                        logger.info(f"[CONTACT_INFO_EXTRACT] ✓ Found website: {website_url}")
                else:
                    logger.info(f"[CONTACT_INFO_EXTRACT] ℹ No websites in array")
            except (KeyError, TypeError, AttributeError, IndexError) as e:
                logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ Error extracting website: {e}")
            
            # Extract birthday
            logger.info(f"[CONTACT_INFO_EXTRACT] Attempting to extract birthday...")
            try:
                birth_date = profile_obj.get('birthDateOn', {})
                if birth_date:
                    logger.info(f"[CONTACT_INFO_EXTRACT] birthDateOn object: {birth_date}")
                    month = birth_date.get('month')
                    day = birth_date.get('day')
                    if month and day:
                        # Convert month number to name
                        month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                                       'July', 'August', 'September', 'October', 'November', 'December']
                        month_name = month_names[month] if 1 <= month <= 12 else str(month)
                        birthday_str = f"{month_name} {day}"
                        contact_info['birthday'] = birthday_str
                        logger.info(f"[CONTACT_INFO_EXTRACT] ✓ Found birthday: {birthday_str}")
                    else:
                        logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ Missing month or day in birthDateOn")
                else:
                    logger.info(f"[CONTACT_INFO_EXTRACT] ℹ No birthDateOn object in profile")
            except (KeyError, TypeError, AttributeError, IndexError) as e:
                logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ Error extracting birthday: {e}")
            
            # Extract connected date from Connection object (if found)
            logger.info(f"[CONTACT_INFO_EXTRACT] Attempting to extract connected date...")
            if connection_obj:
                try:
                    created_at_ms = connection_obj.get('createdAt')
                    logger.info(f"[CONTACT_INFO_EXTRACT] createdAt value: {created_at_ms}")
                    if created_at_ms:
                        # Convert Unix timestamp in milliseconds to readable date
                        from datetime import datetime
                        connected_date = datetime.fromtimestamp(created_at_ms / 1000)
                        connected_date_str = connected_date.strftime("%b %d, %Y")
                        contact_info['connected_date'] = connected_date_str
                        logger.info(f"[CONTACT_INFO_EXTRACT] ✓ Found connected date: {connected_date_str}")
                    else:
                        logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ Connection object exists but no createdAt")
                except (KeyError, TypeError, AttributeError, ValueError) as e:
                    logger.warning(f"[CONTACT_INFO_EXTRACT] ✗ Error extracting connected date: {e}")
            else:
                logger.info(f"[CONTACT_INFO_EXTRACT] ℹ No Connection object found (this is normal if not connected)")
            
            logger.info(f"[CONTACT_INFO_EXTRACT] ========================================")
            logger.info(f"[CONTACT_INFO_EXTRACT] Final extracted data: {contact_info}")
            
        except Exception as e:
            logger.error(f"[PROFILE] Error in _extract_contact_info: {str(e)}")
        
        return contact_info
    
    def _find_text_components_recursive(self, obj: Any, results: list = None) -> list:
        """
        Recursively search for TextComponent objects in the response.
        
        Args:
            obj: The object to search (dict, list, or primitive)
            results: List to accumulate found text components
            
        Returns:
            List of text components found
        """
        if results is None:
            results = []
        
        if isinstance(obj, dict):
            # Check if this is a TextComponent
            if obj.get('$type') == 'com.linkedin.voyager.dash.identity.profile.tetris.TextComponent':
                text_content = obj.get('text', {})
                if isinstance(text_content, dict):
                    text = text_content.get('text', '')
                elif isinstance(text_content, str):
                    text = text_content
                else:
                    text = ''
                
                if text and text.strip():
                    results.append({
                        'text': text,
                        'type': obj.get('$type'),
                        'component': obj
                    })
                    logger.debug(f"[ABOUT_SKILLS] Found TextComponent with {len(text)} chars")
            
            # Recursively search all values
            for value in obj.values():
                self._find_text_components_recursive(value, results)
        
        elif isinstance(obj, list):
            # Recursively search all items
            for item in obj:
                self._find_text_components_recursive(item, results)
        
        return results
    
    async def get_about_and_skills(self, profile_id: str) -> Dict[str, Any]:
        """
        Fetch About section and Top Skills from LinkedIn profile cards.
        
        URL: /graphql?includeWebMetadata=true&variables=(profileUrn:urn%3Ali%3Afsd_profile%3A{profileID})
             &queryId=voyagerIdentityDashProfileCards.f0415f0ff9d9968bab1cd89c0352f7c8
        
        Paths:
        - About: ['included'][1]['topComponents'][1]['components']['textComponent']['text']['text']
        - Top Skills: ['included'][1]['subComponents'][0]['components']['fixedListComponent']
                      ['components'][0]['components']['entityComponent']['subtitle']['text']
        
        Returns:
            Dictionary with 'about' (string) and 'top_skills' (list of strings)
        """
        logger.info(f"[ABOUT_SKILLS] ========================================")
        logger.info(f"[ABOUT_SKILLS] Fetching about and skills for profile {profile_id}")
        logger.info(f"[ABOUT_SKILLS] ========================================")
        
        # URL with the correct queryId for About and Skills
        url = f"{self.GRAPHQL_BASE_URL}?includeWebMetadata=true&variables=(profileUrn:urn%3Ali%3Afsd_profile%3A{profile_id})&queryId=voyagerIdentityDashProfileCards.f0415f0ff9d9968bab1cd89c0352f7c8"
        
        logger.info(f"[ABOUT_SKILLS] Request URL: {url}")
        
        result = {
            'about': 'N/A',
            'top_skills': [],
            'languages': []
        }
        
        try:
            data = await self._make_request(url, debug_endpoint_type="about_skills_legacy")
            
            # Extract About section using recursive search for TextComponent
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            logger.info(f"[ABOUT_SKILLS] Searching for TextComponents recursively...")
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            
            try:
                # Search entire response for TextComponent objects
                text_components = self._find_text_components_recursive(data)
                logger.info(f"[ABOUT_SKILLS] Found {len(text_components)} TextComponent(s) with non-empty text")
                
                # Use the first non-empty text component as the about section
                if text_components:
                    result['about'] = text_components[0]['text']
                    logger.info(f"[ABOUT_SKILLS] ✓ Extracted about text ({len(result['about'])} chars)")
                else:
                    logger.warning(f"[ABOUT_SKILLS] ✗ No TextComponent found with non-empty text")
            
            except (KeyError, TypeError, AttributeError, IndexError) as e:
                logger.error(f"[ABOUT_SKILLS] ✗ Could not extract about section: {e}", exc_info=True)
            
            included = data.get('included', [])
            logger.info(f"[ABOUT_SKILLS] 'included' array length: {len(included)}")
            
            
            # Extract Top Skills
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            logger.info(f"[ABOUT_SKILLS] Attempting to extract TOP SKILLS...")
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            
            try:
                # Search for skills in subtitle text (separated by •)
                for item in included:
                    if isinstance(item, dict):
                        sub_components = item.get('subComponents', [])
                        if sub_components:
                            for sub_comp in sub_components:
                                if isinstance(sub_comp, dict):
                                    components = sub_comp.get('components', {})
                                    if isinstance(components, dict):
                                        fixed_list = components.get('fixedListComponent', {})
                                        if isinstance(fixed_list, dict):
                                            list_components = fixed_list.get('components', [])
                                            if list_components:
                                                for list_item in list_components:
                                                    if isinstance(list_item, dict):
                                                        item_comps = list_item.get('components', {})
                                                        if isinstance(item_comps, dict):
                                                            entity = item_comps.get('entityComponent', {})
                                                            if isinstance(entity, dict):
                                                                subtitle = entity.get('subtitle', {})
                                                                skills_text = subtitle.get('text', '') if isinstance(subtitle, dict) else subtitle if isinstance(subtitle, str) else ''
                                                                
                                                                if skills_text and '•' in skills_text:
                                                                    skills_list = [skill.strip() for skill in skills_text.split('•') if skill.strip()]
                                                                    result['top_skills'] = skills_list
                                                                    logger.info(f"[ABOUT_SKILLS] ✓ Extracted {len(skills_list)} top skills: {skills_list}")
                                                                    break
                                    if result['top_skills']:
                                        break
                        if result['top_skills']:
                            break
                
                if not result['top_skills']:
                    logger.warning(f"[ABOUT_SKILLS] ✗ No skills found")
                    
            except (KeyError, TypeError, AttributeError, IndexError) as e:
                logger.error(f"[ABOUT_SKILLS] ✗ Could not extract top skills: {e}", exc_info=True)
            
            # Extract Languages - reuse from profile_about_skills service
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            logger.info(f"[ABOUT_SKILLS] Attempting to extract LANGUAGES...")
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            
            # Import and use the dedicated service for languages extraction
            from .profile_about_skills import LinkedInProfileAboutSkillsService
            about_skills_service = LinkedInProfileAboutSkillsService(
                headers=self.headers,
                csrf_token=self.csrf_token,
                cookies=self.cookies
            )
            result['languages'] = about_skills_service._extract_languages(data)
            
            logger.info(f"[ABOUT_SKILLS] ========================================")
            logger.info(f"[ABOUT_SKILLS] Final result:")
            logger.info(f"[ABOUT_SKILLS]   About: {result['about'][:100] if result['about'] != 'N/A' else 'N/A'}...")
            logger.info(f"[ABOUT_SKILLS]   Skills: {result['top_skills']}")
            logger.info(f"[ABOUT_SKILLS]   Languages: {len(result['languages'])} entries")
            logger.info(f"[ABOUT_SKILLS] ========================================")
            
            return result
        except Exception as e:
            logger.error(f"[ABOUT_SKILLS] ✗ Error fetching about and skills: {str(e)}", exc_info=True)
            return result
    
    async def get_profile_cards(self, profile_id: str) -> List[str]:
        """
        Fetch profile recommendations from LinkedIn.
        
        Exact replication of getProfileCards from profile_service.js line 536.
        
        Returns:
            List of recommendation strings
        """
        logger.info(f"Fetching profile cards/recommendations for profile {profile_id}")
        
        # Exact URL from old project line 540
        url = f"{self.GRAPHQL_BASE_URL}?includeWebMetadata=true&variables=(profileUrn:urn%3Ali%3Afsd_profile%3A{profile_id})&queryId=voyagerIdentityDashProfileCards.ddf85b42590c29d8ca29c09533f87160"
        
        try:
            data = await self._make_request(url, debug_endpoint_type="recommendations")
            recommendations = self._extract_recommendations(data)
            logger.info(f"Extracted {len(recommendations)} recommendations")
            return recommendations
        except Exception as e:
            logger.error(f"Error fetching profile cards: {str(e)}")
            return []  # Return empty list on error, don't fail the whole process
    
    def _extract_recommendations(self, json_data: Dict[str, Any]) -> List[str]:
        """
        Extract recommendations from profile cards response.
        
        Exact replication of extractRecommendations from profile_service.js line 685.
        
        Returns:
            List of recommendation text strings
        """
        recommendations = set()
        
        # Find the element in included array that contains 'RECOMMENDATIONS' in its entityUrn
        included = json_data.get('included', [])
        recommendations_element = next(
            (element for element in included 
             if element.get('entityUrn') and 'RECOMMENDATIONS' in element.get('entityUrn', '')),
            None
        )
        
        if not recommendations_element:
            logger.info('No recommendations element found')
            return list(recommendations)
        
        # Recursive function to find and extract recommendation texts
        def find_recommendations(components):
            if not components:
                return
            
            # Check for textComponent containing recommendation text
            if isinstance(components, dict):
                text_component = components.get('textComponent')
                if text_component and text_component.get('text'):
                    recommendation_text = text_component['text'].get('text')
                    if recommendation_text and recommendation_text not in recommendations:
                        logger.debug(f"Found recommendation: {recommendation_text}")
                        recommendations.add(recommendation_text)
                
                # Recursively search through sub-components
                for key, value in components.items():
                    if value and isinstance(value, (dict, list)):
                        find_recommendations(value)
            
            # Handle arrays of components
            elif isinstance(components, list):
                for component in components:
                    find_recommendations(component)
        
        # Start the search from topComponents array
        top_components = recommendations_element.get('topComponents', [])
        if isinstance(top_components, list):
            for component in top_components:
                if component.get('components'):
                    find_recommendations(component['components'])
        
        return list(recommendations)
    
    # OLD FUNCTION - DELETED - Replaced by get_profile_identity_cards
    
    async def get_headline_location_and_degree(self, vanity_name: str, profile_id: str = None) -> Dict[str, str]:
        """
        Fetch headline, location, and connection degree from the profile HTML page.
        
        Uses structured JSON extraction from <code> tags instead of regex.
        This is more reliable as it parses the actual data structures LinkedIn uses.
        
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
            # Fetch HTML page
            async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers, cookies=self.linkedin_cookies)
                
                logger.info(f"[HTML_EXTRACT] Response status: {response.status_code}")
                
                if response.status_code != 200:
                    logger.warning(f"[HTML_EXTRACT] Non-200 status: {response.status_code}")
                    return result
                
                html_content = response.text
                logger.info(f"[HTML_EXTRACT] HTML length: {len(html_content)} chars")
                
                # Extract headline using regex on HTML-encoded JSON
                # CRITICAL: Match headline for the TARGET profile, not the logged-in user
                # Strategy 1: If we have profile_id, match entityUrn with that specific ID
                # Strategy 2: Match publicIdentifier with our vanity_name
                # Strategy 3: Fallback to multiLocaleHeadline near the vanity name
                
                headline = None
                
                if profile_id:
                    # Strategy 1: Look for headline in the Profile object with EXACT profile ID
                    logger.info(f"[HTML_EXTRACT] Searching for headline with profile_id: {profile_id}")
                    escaped_profile_id = re.escape(profile_id)
                    headline_pattern = rf'&quot;entityUrn&quot;:&quot;urn:li:fsd_profile:{escaped_profile_id}&quot;.*?&quot;headline&quot;:&quot;((?:[^&]|&(?!quot;))+?)&quot;'
                    headline_match = re.search(headline_pattern, html_content, re.DOTALL)
                    if headline_match:
                        headline = headline_match.group(1)
                        logger.info(f"[HTML_EXTRACT] Found headline via profile_id match")
                
                if not headline:
                    # Strategy 2: Look for headline near publicIdentifier matching our vanity_name
                    logger.info(f"[HTML_EXTRACT] Searching for headline with vanity_name: {vanity_name}")
                    escaped_vanity = re.escape(vanity_name)
                    headline_pattern = rf'&quot;publicIdentifier&quot;:&quot;{escaped_vanity}&quot;.*?&quot;headline&quot;:&quot;((?:[^&]|&(?!quot;))+?)&quot;'
                    headline_match = re.search(headline_pattern, html_content, re.DOTALL)
                    if headline_match:
                        headline = headline_match.group(1)
                        logger.info(f"[HTML_EXTRACT] Found headline via vanity_name match")
                
                if not headline:
                    # Strategy 3: Look for multiLocaleHeadline near publicIdentifier
                    headline_pattern = rf'&quot;publicIdentifier&quot;:&quot;{re.escape(vanity_name)}&quot;.*?&quot;multiLocaleHeadline&quot;:\[{{&quot;value&quot;:&quot;((?:[^&]|&(?!quot;))+?)&quot;'
                    headline_match = re.search(headline_pattern, html_content, re.DOTALL)
                    if headline_match:
                        headline = headline_match.group(1)
                        logger.info(f"[HTML_EXTRACT] Found headline via multiLocaleHeadline + vanity match")
                
                if headline:
                    # Decode HTML entities and unicode escapes
                    headline = headline.replace('&#92;u', '\\u')  # Unicode escapes like &#92;uD83E
                    headline = headline.replace('&amp;', '&')
                    headline = headline.replace('&lt;', '<')
                    headline = headline.replace('&gt;', '>')
                    
                    # Handle Unicode escapes and surrogate pairs (for emojis)
                    try:
                        # JavaScript/JSON uses UTF-16 surrogate pairs for emojis
                        # Python needs them converted properly
                        headline = headline.encode('latin1').decode('unicode-escape')
                        # Now encode/decode to handle any remaining issues
                        headline = headline.encode('utf-16', 'surrogatepass').decode('utf-16')
                    except Exception as e:
                        logger.warning(f"[HTML_EXTRACT] Unicode decode failed: {e}, keeping original")
                        # Fallback: remove any problematic unicode sequences
                        headline = headline.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
                    
                    result['headline'] = headline
                    logger.info(f"[HTML_EXTRACT] ✓ Headline: {headline[:80]}...")
                else:
                    logger.warning(f"[HTML_EXTRACT] Could not find headline for vanity: {vanity_name}, profile_id: {profile_id}")
                
                # Extract location using regex on HTML-encoded JSON
                # Look for defaultLocalizedName that contains a comma (more specific location)
                location_pattern = r'&quot;defaultLocalizedName&quot;:&quot;([^&]+(?:,|, )[^&]+)&quot;'
                location_match = re.search(location_pattern, html_content)
                
                if location_match:
                    location = location_match.group(1)
                    location = location.replace('&amp;', '&')
                    result['location'] = location
                    logger.info(f"[HTML_EXTRACT] ✓ Location: {location}")
                else:
                    # Fallback: just get any defaultLocalizedName
                    location_pattern_simple = r'&quot;defaultLocalizedName&quot;:&quot;([^&]+)&quot;'
                    location_match = re.search(location_pattern_simple, html_content)
                    if location_match:
                        location = location_match.group(1)
                        location = location.replace('&amp;', '&')
                        result['location'] = location
                        logger.info(f"[HTML_EXTRACT] ✓ Location (simple): {location}")
                    else:
                        logger.warning("[HTML_EXTRACT] Could not find location")
                
                # Extract connection degree using regex
                # Look for memberRelationship and connection/distance patterns
                member_rel_pattern = r'&quot;\*memberRelationship&quot;:&quot;(urn:li:fsd_memberRelationship:[^&]+)&quot;'
                member_rel_match = re.search(member_rel_pattern, html_content)
                
                if member_rel_match:
                    member_rel_urn = member_rel_match.group(1)
                    logger.info(f"[HTML_EXTRACT] Found memberRelationship URN: {member_rel_urn}")
                    
                    # Search for this URN and check connection type
                    # Pattern for 1st degree: has connection field
                    if re.search(rf'{re.escape(member_rel_urn)}.*?&quot;\*connection&quot;:&quot;urn:li:fsd_connection:', html_content, re.DOTALL):
                        result['con_degree'] = '1st'
                        logger.info(f"[HTML_EXTRACT] ✓ Connection Degree: 1st")
                    else:
                        # Check for DISTANCE_2 or DISTANCE_3
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
    
    # OLD FUNCTION - DELETED - Replaced by get_profile_identity_cards → _extract_identity_data
    
    # ============================================================
    # CLEAN FOCUSED FUNCTIONS FOR EACH DATA SOURCE
    # ============================================================
    
    async def _fetch_identity_cards(self, profile_id: str) -> Dict[str, Any]:
        """
        Fetch identity data from LinkedIn Identity Cards GraphQL endpoint.
        
        Input: profile_id (e.g., "ACoAACyAmSQBDSKSp_2bLHpuYtCpNXcJgfbwiq8")
        Output: {vanity_name, firstName, lastName, follower_count}
        """
        data = await self.get_profile_identity_cards(profile_id)
        return {
            'vanity_name': data.get('vanity_name', 'N/A'),
            'firstName': data.get('first_name', 'N/A'),
            'lastName': data.get('last_name', 'N/A'),
            'follower_count': data.get('follower_count', 0)
        }
    
    async def _fetch_contact_info(self, vanity_name: str) -> Dict[str, Any]:
        """
        Fetch contact info from LinkedIn Contact Info GraphQL endpoint.
        
        Input: vanity_name (e.g., "izzword")
        Output: {email, phone, website, birthday, connected_date}
        """
        if not vanity_name or vanity_name == 'N/A':
            return {
                'email': 'N/A',
                'phone': 'N/A',
                'website': 'N/A',
                'birthday': 'N/A',
                'connected_date': 'N/A'
            }
        
        return await self.get_contact_info(vanity_name)
    
    async def _fetch_html_data(self, vanity_name: str, profile_id: str = None) -> Dict[str, Any]:
        """
        Fetch headline, location, and connection degree from profile HTML page.
        
        Input: vanity_name (e.g., "izzword"), profile_id (optional, for targeting)
        Output: {headline, location, con_degree}
        """
        if not vanity_name or vanity_name == 'N/A':
            return {
                'headline': 'N/A',
                'location': 'N/A',
                'con_degree': 'N/A'
            }
        
        return await self.get_headline_location_and_degree(vanity_name, profile_id)
    
    async def _fetch_about_and_skills(self, profile_id: str) -> Dict[str, Any]:
        """
        Fetch about section and top skills from LinkedIn GraphQL endpoint.
        
        Input: profile_id (e.g., "ACoAACyAmSQBDSKSp_2bLHpuYtCpNXcJgfbwiq8")
        Output: {about, skills[]}
        """
        data = await self.get_about_and_skills(profile_id)
        return {
            'about': data.get('about', 'N/A'),
            'skills': data.get('top_skills', [])
        }
    
    # ============================================================
    # END CLEAN FOCUSED FUNCTIONS
    # ============================================================
    
    # OLD FUNCTION - DELETED - Replaced by get_headline_location_and_degree (HTML scraping)
    
    async def scrape_profile(
        self,
        profile_id_or_url: str
    ) -> Dict[str, Any]:
        """
        Scrape basic LinkedIn profile info.
        
        Clean structure with focused functions for each data source:
        1. Extract profile ID from URL/ID
        2. Identity Cards (GraphQL) → vanity_name, firstName, lastName, follower_count
        3. Contact Info (GraphQL) → email, phone, website, birthday, connected_date
        4. HTML Page → headline, location, con_degree
        5. About & Skills (GraphQL) → about, skills
        
        Args:
            profile_id_or_url: LinkedIn profile ID or URL
            
        Returns:
            Clean formatted profile dictionary
        """
        logger.info(f"=" * 80)
        logger.info(f"[PROFILE_SCRAPE] Starting profile scrape")
        logger.info(f"=" * 80)
        
        # ============================================================
        # STEP 1: Extract Profile ID
        # ============================================================
        profile_id = await extract_profile_id(
            profile_input=profile_id_or_url,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        logger.info(f"[STEP 1] Profile ID: {profile_id}")
        
        # ============================================================
        # STEP 2: Identity Cards (GraphQL) 
        # URL: /graphql?variables=(profileUrn:...)&queryId=voyagerIdentityDashProfileCards.c5c6ae...
        # Returns: vanity_name, firstName, lastName, follower_count
        # ============================================================
        identity = await self._fetch_identity_cards(profile_id)
        logger.info(f"[STEP 2] Identity Cards → vanity_name={identity['vanity_name']}, follower_count={identity['follower_count']}")
        
        vanity_name = identity['vanity_name']
        
        # ============================================================
        # STEP 3: Contact Info (GraphQL)
        # URL: /graphql?variables=(memberIdentity:{vanity_name})&queryId=voyagerIdentityDashProfiles.c7452e...
        # Returns: email, phone, website, birthday, connected_date
        # ============================================================
        contact = await self._fetch_contact_info(vanity_name)
        logger.info(f"[STEP 3] Contact Info → email={contact['email']}, website={contact['website']}")
        
        # ============================================================
        # STEP 4: HTML Page Scraping
        # URL: /in/{vanity_name}/
        # Returns: headline, location, con_degree
        # ============================================================
        html_data = await self._fetch_html_data(vanity_name, profile_id)
        logger.info(f"[STEP 4] HTML Data → headline={html_data['headline'][:50] if html_data['headline'] != 'N/A' else 'N/A'}..., con_degree={html_data['con_degree']}")
        
        # ============================================================
        # STEP 5: About & Skills (GraphQL)
        # URL: /graphql?variables=(profileUrn:...)&queryId=voyagerIdentityDashProfileCards.f0415f0...
        # Returns: about, skills[]
        # ============================================================
        about_skills = await self._fetch_about_and_skills(profile_id)
        logger.info(f"[STEP 5] About & Skills → about_length={len(about_skills['about'])}, skills_count={len(about_skills['skills'])}")
        
        # ============================================================
        # BUILD FINAL RESPONSE
        # ============================================================
        result = {
            'linkedin_id': profile_id,
            'vanity_name': identity['vanity_name'],
            'profile_url': f"https://www.linkedin.com/in/{identity['vanity_name']}",
            'name': f"{identity['firstName']} {identity['lastName']}".strip(),
            'firstName': identity['firstName'],
            'lastName': identity['lastName'],
            'headline': html_data['headline'],
            'about': about_skills['about'],
            'con_degree': html_data['con_degree'],
            'location': html_data['location'],
            'skills': about_skills['skills'],
            'email': contact['email'],
            'phone': contact['phone'],
            'website': contact['website'],
            'birthday': contact['birthday'],
            'connected_date': contact['connected_date'],
            'follower_count': identity['follower_count']
        }
        
        logger.info(f"=" * 80)
        logger.info(f"[PROFILE_SCRAPE] ✓ Completed successfully")
        logger.info(f"=" * 80)
        
        return result
    
    async def scrape_profile_experiences(
        self,
        profile_id_or_url: str
    ) -> List[Dict[str, Any]]:
        """
        Scrape work experiences for a LinkedIn profile.
        
        Args:
            profile_id_or_url: LinkedIn profile ID or URL
            
        Returns:
            List of experience dictionaries
        """
        logger.info(f"[PROFILE] Starting experience scrape for: {profile_id_or_url}")
        
        # Extract profile ID using shared utility
        profile_id = await extract_profile_id(
            profile_input=profile_id_or_url,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        logger.info(f"[PROFILE] Using profile ID: {profile_id}")
        
        # Get work experiences
        experiences = await self.get_profile_experiences(profile_id)
        
        logger.info(f"[PROFILE] Experience scrape completed for {profile_id}, found {len(experiences)} experiences")
        return experiences
    
    async def scrape_profile_recommendations(
        self,
        profile_id_or_url: str
    ) -> List[str]:
        """
        Scrape recommendations for a LinkedIn profile.
        
        Args:
            profile_id_or_url: LinkedIn profile ID or URL
            
        Returns:
            List of recommendation strings
        """
        logger.info(f"[PROFILE] Starting recommendations scrape for: {profile_id_or_url}")
        
        # Extract profile ID using shared utility
        profile_id = await extract_profile_id(
            profile_input=profile_id_or_url,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        logger.info(f"[PROFILE] Using profile ID: {profile_id}")
        
        # Get recommendations (profile cards)
        recommendations = await self.get_profile_cards(profile_id)
        
        logger.info(f"[PROFILE] Recommendations scrape completed for {profile_id}, found {len(recommendations)} recommendations")
        return recommendations
    
    # OLD FUNCTION - DELETED - Replaced by direct dict building in scrape_profile

