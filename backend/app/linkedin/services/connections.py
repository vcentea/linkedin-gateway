"""
LinkedIn Connection Request API service.

Mirrors functionality from chrome-extension/src/services/profile_service.js
Provides server-side implementation of connection request operations.
"""
from typing import Dict, Any, Optional, List
import json
import re
from .base import LinkedInServiceBase
from ..utils.profile_id_extractor import extract_profile_id
import logging

logger = logging.getLogger(__name__)

class LinkedInConnectionService(LinkedInServiceBase):
    """Service for LinkedIn connection request operations."""
    
    @staticmethod
    def _convert_date_to_iso(date_str: str) -> Optional[str]:
        """
        Convert LinkedIn date format to ISO format (yyyy-mm-dd).
        
        Args:
            date_str: Date string in format "Connected on October 27, 2025" or "October 27, 2025"
            
        Returns:
            Date in format "2025-10-27" or None if parsing fails
        """
        try:
            from datetime import datetime
            
            # Remove "Connected on " prefix if present
            clean_date = date_str.replace("Connected on ", "").strip()
            
            # Parse the date (e.g., "October 27, 2025")
            date_obj = datetime.strptime(clean_date, "%B %d, %Y")
            
            # Return in yyyy-mm-dd format
            return date_obj.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Failed to convert date '{date_str}': {e}")
            return None
    
    async def send_simple_connection_request(self, profile_identifier: str) -> Dict[str, Any]:
        """
        Send a simple connection request without a message.
        
        Mirrors sendSimpleConnectionRequest from profile_service.js
        
        Args:
            profile_identifier: The LinkedIn profile ID or profile URL with vanity name.
            
        Returns:
            Dict containing the API response.
            
        Raises:
            ValueError: If profile_identifier is invalid.
            httpx.HTTPStatusError: If the API request fails.
        """
        if not profile_identifier:
            raise ValueError("profile_identifier is required")
        
        # Extract profile ID from URL or validate direct ID
        profile_id = await extract_profile_id(
            profile_input=profile_identifier,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        
        logger.info(f"Sending simple connection request to profile: {profile_id}")
        
        # Build the URL
        url = (
            f"{self.VOYAGER_BASE_URL}/voyagerRelationshipsDashMemberRelationships"
            f"?action=verifyQuotaAndCreateV2"
            f"&decorationId=com.linkedin.voyager.dash.deco.relationships.InvitationCreationResultWithInvitee-2"
        )
        
        # Build the payload
        payload = {
            "invitee": {
                "inviteeUnion": {
                    "memberProfile": f"urn:li:fsd_profile:{profile_id}"
                }
            }
        }
        
        # Add content-type header for POST request
        headers = {
            **self.headers,
            "Content-Type": "application/json",
        }
        
        # Make the request
        data = await self._make_request(
            url=url,
            method='POST',
            json=payload
        )
        
        logger.info(f"Successfully sent simple connection request to {profile_id}")
        return data
    
    async def send_connection_request_with_message(
        self, 
        profile_identifier: str, 
        message: str
    ) -> Dict[str, Any]:
        """
        Send a connection request with a custom message.
        
        Mirrors sendConnectionRequestWithMessage from profile_service.js
        
        Args:
            profile_identifier: The LinkedIn profile ID or profile URL with vanity name.
            message: The custom message to include with the connection request.
            
        Returns:
            Dict containing the API response.
            
        Raises:
            ValueError: If profile_identifier or message is invalid.
            httpx.HTTPStatusError: If the API request fails.
        """
        if not profile_identifier:
            raise ValueError("profile_identifier is required")
        
        if not message or not message.strip():
            raise ValueError("message is required and cannot be empty")
        
        # Extract profile ID from URL or validate direct ID
        profile_id = await extract_profile_id(
            profile_input=profile_identifier,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        
        logger.info(f"Sending connection request with message to profile: {profile_id}")
        
        # Build the URL
        url = (
            f"{self.VOYAGER_BASE_URL}/voyagerRelationshipsDashMemberRelationships"
            f"?action=verifyQuotaAndCreateV2"
            f"&decorationId=com.linkedin.voyager.dash.deco.relationships.InvitationCreationResultWithInvitee-2"
        )
        
        # Build the payload
        payload = {
            "invitee": {
                "inviteeUnion": {
                    "memberProfile": f"urn:li:fsd_profile:{profile_id}"
                }
            },
            "customMessage": message
        }
        
        # Add content-type header for POST request
        headers = {
            **self.headers,
            "Content-Type": "application/json",
        }
        
        # Make the request
        data = await self._make_request(
            url=url,
            method='POST',
            json=payload
        )
        
        logger.info(f"Successfully sent connection request with message to {profile_id}")
        return data
    
    def _build_connections_url(self, start_index: int) -> str:
        """
        Build URL for fetching connections list.
        
        Args:
            start_index: Starting index for pagination.
            
        Returns:
            str: The constructed URL.
        """
        url = (
            f"https://www.linkedin.com/flagship-web/rsc-action/actions/pagination"
            f"?sduiid=com.linkedin.sdui.pagers.mynetwork.connectionsList"
        )
        return url
    
    def _build_connections_payload(self, start_index: int) -> Dict[str, Any]:
        """
        Build payload for fetching connections list.
        
        Args:
            start_index: Starting index for pagination.
            
        Returns:
            Dict: The payload for the POST request.
        """
        payload = {
            "pagerId": "com.linkedin.sdui.pagers.mynetwork.connectionsList",
            "clientArguments": {
                "$type": "proto.sdui.actions.requests.RequestedArguments",
                "payload": {
                    "startIndex": start_index,
                    "sortByOptionBinding": {
                        "key": "connectionsListSortOption",
                        "namespace": "connectionsListSortOptionMenu"
                    }
                },
                "requestedStateKeys": [
                    {
                        "$type": "proto.sdui.StateKey",
                        "value": "connectionsListSortOption",
                        "key": {
                            "$type": "proto.sdui.Key",
                            "value": {
                                "$case": "id",
                                "id": "connectionsListSortOption"
                            }
                        },
                        "namespace": "connectionsListSortOptionMenu",
                        "isEncrypted": False
                    }
                ],
                "requestMetadata": {
                    "$type": "proto.sdui.common.RequestMetadata"
                },
                "states": [
                    {
                        "key": "connectionsListSortOption",
                        "namespace": "connectionsListSortOptionMenu",
                        "value": "sortByRecentlyAdded"
                    }
                ]
            },
            "paginationRequest": {
                "$type": "proto.sdui.actions.requests.PaginationRequest",
                "pagerId": "com.linkedin.sdui.pagers.mynetwork.connectionsList",
                "requestedArguments": {
                    "$type": "proto.sdui.actions.requests.RequestedArguments",
                    "payload": {
                        "startIndex": start_index,
                        "sortByOptionBinding": {
                            "key": "connectionsListSortOption",
                            "namespace": "connectionsListSortOptionMenu"
                        }
                    },
                    "requestedStateKeys": [
                        {
                            "$type": "proto.sdui.StateKey",
                            "value": "connectionsListSortOption",
                            "key": {
                                "$type": "proto.sdui.Key",
                                "value": {
                                    "$case": "id",
                                    "id": "connectionsListSortOption"
                                }
                            },
                            "namespace": "connectionsListSortOptionMenu",
                            "isEncrypted": False
                        }
                    ],
                    "requestMetadata": {
                        "$type": "proto.sdui.common.RequestMetadata"
                    }
                },
                "trigger": {
                    "$case": "itemDistanceTrigger",
                    "itemDistanceTrigger": {
                        "$type": "proto.sdui.actions.requests.ItemDistanceTrigger",
                        "preloadDistance": 3,
                        "preloadLength": 250
                    }
                },
                "retryCount": 2
            }
        }
        return payload
    
    def _extract_people_from_raw_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract connection details by parsing RSC line-by-line.
        
        Each connection's data is grouped in consecutive lines in the RSC format.
        This approach associates data by line proximity rather than character distance.
        
        Args:
            text: Raw RSC response text.
            
        Returns:
            List of connection dictionaries.
        """
        import urllib.parse
        
        # Split into lines (RSC format has one JSON block per line)
        lines = text.strip().split('\n')
        
        logger.info(f"Parsing {len(lines)} RSC lines...")
        
        # Parse each line and extract all profile data
        profile_data_by_line = []
        
        for line_num, line in enumerate(lines):
            if not line.strip():
                continue
            
            line_data = {
                'line_num': line_num,
                'profile_urls': [],
                'urns': [],
                'names': [],
                'headlines': [],
                'dates': [],
                'first_last_names': []
            }
            
            # Extract profile URLs
            for m in re.finditer(r'https://www\.linkedin\.com/in/([a-z0-9\-]+)/?', line):
                vanity = m.group(1)
                url = m.group(0)
                line_data['profile_urls'].append({'vanity': vanity, 'url': url})
            
            # Extract URNs
            for m in re.finditer(r'profileUrn=urn%3Ali%3Afsd_profile%3A([A-Za-z0-9_-]+)', line):
                urn_id = urllib.parse.unquote(m.group(1))
                line_data['urns'].append(urn_id)
            
            # Extract names from a11yText, aria-label, alt
            for pattern in [
                r'"a11yText":"([^"]+?)\'s profile picture"',
                r'"aria-label":"([^"]+?)\'s profile"',
            ]:
                for m in re.finditer(pattern, line):
                    name = m.group(1)
                    if name and name not in ['Message', 'Remove', 'Show more']:
                        line_data['names'].append(name)
            
            # Extract names from children arrays (capitalized with spaces)
            for m in re.finditer(r'"children":\s*\[\s*"([A-Z][^"]{2,80})"\s*\]', line):
                text_val = m.group(1)
                # Must have space or special char, and not be UI string
                if (' ' in text_val or any(ord(c) > 127 for c in text_val)):
                    if text_val not in ['Message', 'Remove connection', 'Show more actions', 'View profile']:
                        if not text_val.startswith(('Connected on', 'http')):
                            line_data['names'].append(text_val)
            
            # Extract firstName/lastName from payload
            payload_match = re.search(r'"firstName"\s*:\s*"([^"]+)"\s*,\s*"lastName"\s*:\s*"([^"]+)"', line)
            if payload_match:
                full_name = f"{payload_match.group(1)} {payload_match.group(2)}"
                line_data['first_last_names'].append(full_name)
            
            # Extract connection dates
            for m in re.finditer(r'Connected on ([A-Za-z]+ \d{1,2}, \d{4})', line):
                line_data['dates'].append(f"Connected on {m.group(1)}")
            
            # Extract headlines (longer text in children that's not a name or UI string)
            for m in re.finditer(r'"children":\s*\[\s*"([^"]{15,200})"\s*\]', line):
                text_val = m.group(1).strip()
                if text_val not in ['Message', 'Remove connection', 'Show more actions']:
                    if not text_val.startswith(('Connected on', 'http', 'View ', 'Message ')):
                        # Likely a headline if it's longer and not just a name
                        line_data['headlines'].append(text_val)
            
            profile_data_by_line.append(line_data)
        
        logger.info(f"Parsed all lines, now grouping by profile...")
        
        # Group data by profile URL (each profile's data spans a few consecutive lines)
        people = {}
        
        # First pass: collect all dates from all lines (they might be in the main line 0:)
        all_dates_in_order = []
        for line_data in profile_data_by_line:
            all_dates_in_order.extend(line_data['dates'])
        
        logger.info(f"Found {len(all_dates_in_order)} connection dates total")
        date_index = 0  # Track which date to assign to which profile
        
        for i, line_data in enumerate(profile_data_by_line):
            # If this line has profile URLs, start collecting data for each
            for profile_info in line_data['profile_urls']:
                vanity = profile_info['vanity']
                url = profile_info['url']
                
                if vanity not in people:
                    people[vanity] = {
                        'profile_id': vanity,  # Default to vanity, will update if URN found
                        'name': None,
                        'headline': None,
                        'profile_url': url,
                        'connected_date': None,
                        'urn': None
                    }
                    
                    # Look in THIS line and next 3 lines only (keep it tight to avoid mixing data)
                    for offset in range(0, 4):
                        if i + offset < len(profile_data_by_line):
                            nearby_line = profile_data_by_line[i + offset]
                            
                            # Get URN if available (but don't search too far)
                            if not people[vanity]['urn'] and nearby_line['urns']:
                                people[vanity]['urn'] = nearby_line['urns'][0]
                                people[vanity]['profile_id'] = nearby_line['urns'][0]
                                logger.debug(f"  Found URN for {vanity}: {people[vanity]['urn']}")
                            
                            # Get name (prefer firstName/lastName, then a11y, then children)
                            if not people[vanity]['name']:
                                if nearby_line['first_last_names']:
                                    people[vanity]['name'] = nearby_line['first_last_names'][0]
                                    logger.debug(f"  Found name from payload: {people[vanity]['name']}")
                                elif nearby_line['names']:
                                    people[vanity]['name'] = nearby_line['names'][0]
                                    logger.debug(f"  Found name: {people[vanity]['name']}")
                            
                            # Get headline (from headlines list, pick one that's different from name)
                            if not people[vanity]['headline'] and nearby_line['headlines']:
                                for hl in nearby_line['headlines']:
                                    # Make sure it's not the name
                                    if people[vanity]['name']:
                                        name_norm = re.sub(r'[^\w\s]', '', people[vanity]['name']).lower()
                                        hl_norm = re.sub(r'[^\w\s]', '', hl).lower()
                                        if name_norm != hl_norm:
                                            people[vanity]['headline'] = hl
                                            logger.debug(f"  Found headline: {hl[:50]}...")
                                            break
                    
                    # Assign connection date in order (dates appear in same order as profiles)
                    if date_index < len(all_dates_in_order):
                        raw_date = all_dates_in_order[date_index]
                        # Convert to ISO format (yyyy-mm-dd)
                        iso_date = self._convert_date_to_iso(raw_date)
                        people[vanity]['connected_date'] = iso_date
                        logger.debug(f"  Assigned date: {raw_date} -> {iso_date}")
                        date_index += 1
                    
                    # Fallback for name
                    if not people[vanity]['name']:
                        people[vanity]['name'] = vanity.replace('-', ' ').title()
                    
                    logger.info(f"✓ Extracted: {people[vanity]['name']} ({people[vanity]['profile_id']})")
        
        return list(people.values())
        
        def nearest_within_window(anchor: int, matches: List[Tuple[re.Match, int]], 
                                 max_dist: int = 3000, prefer_before: bool = True) -> Optional[re.Match]:
            """Find the nearest match within a distance window."""
            best = None
            best_dist = max_dist + 1
            
            for m, pos in matches:
                dist = abs(pos - anchor)
                if dist <= max_dist:
                    # If tie, prefer before or after based on flag
                    if dist < best_dist or (dist == best_dist and prefer_before and pos <= anchor):
                        best = m
                        best_dist = dist
            
            return best
        
        people: Dict[str, Dict[str, Any]] = {}
        
        # Pre-scan all matches for locality searches
        logger.info("Scanning for profile anchors and attributes...")
        all_a11y = find_all_positions(A11Y_NAME_RE, text)
        all_aria = find_all_positions(ARIA_LABEL_RE, text)
        all_alt = find_all_positions(ALT_TEXT_RE, text)
        all_dates = find_all_positions(CONNECTION_DATE_RE, text)
        all_urns = find_all_positions(URN_RE, text)
        all_vanities = find_all_positions(VANITY_RE, text)
        
        # Combine all name sources
        all_names = all_a11y + all_aria + all_alt
        
        logger.info(f"Found: {len(all_vanities)} profile URLs, {len(all_names)} names "
                   f"(a11y:{len(all_a11y)}, aria:{len(all_aria)}, alt:{len(all_alt)}), "
                   f"{len(all_urns)} URNs, {len(all_dates)} dates")
        
        # For each vanity URL (profile anchor), collect nearby attributes
        for m, pos in all_vanities:
            vanity = m.group('vanity')
            profile_url = m.group(0)
            
            # Skip if we already processed this vanity
            if vanity in people:
                continue
            
            logger.debug(f"Processing profile: {vanity} at position {pos}")
            
            person = {
                "vanity": vanity,
                "profile_url": profile_url,
                "profile_id": vanity,
                "name": None,
                "urn": None,
                "headline": None,
                "connected_date": None
            }
            
            # 1. Name: try multiple sources
            name_match = nearest_within_window(pos, all_names, max_dist=8000, prefer_before=False)
            if name_match:
                person["name"] = name_match.group('name')
                logger.debug(f"  Found name via attribute: {person['name']}")
            else:
                # Fallback: look for children:["Name"] in nearby window
                window = 3000
                chunk = text[max(0, pos - window): min(len(text), pos + window)]
                
                # UI strings to exclude
                ui_strings = [
                    'Message', 'Show more actions', 'Connected on', 'Remove connection',
                    'Remove Connection', 'View profile', 'View Profile', 'Send message',
                    'Follow', 'Unfollow', 'Connect', 'Pending'
                ]
                
                # Find all candidate names in the window
                # Try multiple patterns for finding names in children arrays
                name_candidates = []
                
                # Pattern 1: Direct children array: "children":["Name"]
                for m_text in re.finditer(r'"children":\s*\[\s*"([^"]{3,100})"\s*\]', chunk):
                    candidate = m_text.group(1).strip()
                    if candidate in ui_strings or candidate.startswith(('http', 'linkedin.com', 'Connected on')):
                        continue
                    if any(c.isupper() for c in candidate) and (' ' in candidate or any(ord(c) > 127 for c in candidate)):
                        name_candidates.append(candidate)
                        logger.debug(f"  Found name candidate (direct): {candidate}")
                
                # Pattern 2: Nested children: looks for any quoted string that might be a name
                for m_text in re.finditer(r'"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+(?:\s*[🌳-🔥])?)"', chunk):
                    candidate = m_text.group(1).strip()
                    if candidate in ui_strings:
                        continue
                    if len(candidate) >= 3 and len(candidate) <= 100:
                        name_candidates.append(candidate)
                        logger.debug(f"  Found name candidate (nested): {candidate}")
                
                # Pattern 3: firstName/lastName in payload
                payload_match = re.search(r'"firstName"\s*:\s*"([^"]+)"\s*,\s*"lastName"\s*:\s*"([^"]+)"', chunk)
                if payload_match:
                    full_name = f"{payload_match.group(1)} {payload_match.group(2)}"
                    name_candidates.insert(0, full_name)  # Prioritize this
                    logger.debug(f"  Found name from payload: {full_name}")
                
                # Use the first valid candidate
                if name_candidates:
                    person["name"] = name_candidates[0]
                    logger.debug(f"  Using name: {person['name']}")
                else:
                    # Last resort: use vanity name (capitalize it)
                    person["name"] = vanity.replace('-', ' ').title()
                    logger.debug(f"  Using vanity as name: {person['name']}")
            
            # 2. URN nearest this vanity
            urn_m = nearest_within_window(pos, all_urns, max_dist=8000, prefer_before=False)
            if urn_m:
                person["urn"] = "urn:li:fsd_profile:" + percent_decode(urn_m.group('urn'))
                # Use URN ID as profile_id if available
                person["profile_id"] = percent_decode(urn_m.group('urn'))
                logger.debug(f"  Found URN: {person['profile_id']}")
            
            # 3. Connection date nearest (usually before) this anchor
            date_m = nearest_within_window(pos, all_dates, max_dist=10000, prefer_before=True)
            if date_m:
                person["connected_date"] = f"Connected on {date_m.group('date')}"
                logger.debug(f"  Found date: {person['connected_date']}")
            
            # 4. Headline: scan a wider window for sensible text (RSC files are very dense)
            window = 5000
            chunk = text[max(0, pos - window): min(len(text), pos + window)]
            candidates = []
            
            # UI strings to exclude from headlines
            headline_ui_strings = [
                'Message', 'Show more actions', 'Connected on', 'Remove connection',
                'Remove Connection', 'View profile', 'View Profile', 'Send message',
                'Follow', 'Unfollow', 'Connect', 'Pending', 'Invite to connect'
            ]
            
            for hm in HEADLINE_RE.finditer(chunk):
                t = hm.group('headline').strip()
                
                # Skip dates, URLs, and UI strings
                if "Connected on" in t:
                    continue
                if t.startswith("http") or "linkedin.com" in t:
                    continue
                if t in headline_ui_strings:
                    continue
                
                # Skip if starts with common button/action words
                if t.startswith(('View ', 'Message ', 'Connect ', 'Follow ')):
                    continue
                    
                # Skip if it's just the person's name repeated
                if person.get("name"):
                    # Normalize both for comparison (remove emojis, extra spaces)
                    name_normalized = re.sub(r'[^\w\s]', '', person["name"]).strip().lower()
                    t_normalized = re.sub(r'[^\w\s]', '', t).strip().lower()
                    if t_normalized == name_normalized:
                        continue
                
                # Headlines usually have certain characteristics
                # - Contain job-related words, or
                # - Have certain punctuation patterns, or
                # - Are longer than just a name
                # Prioritize text that looks like a professional headline
                candidates.append(t)
                logger.debug(f"  Found headline candidate: {t[:60]}...")
            
            # Pick the shortest plausible candidate (headlines are typically concise)
            if candidates:
                person["headline"] = sorted(candidates, key=len)[0]
                logger.debug(f"  Found headline: {person['headline'][:50]}...")
            
            # Only add if we have at least name or profile_id
            if person["name"] or person["profile_id"]:
                people[vanity] = person
                logger.info(f"✓ Extracted: {person['name']} ({person['profile_id']})")
            else:
                logger.debug(f"  Skipping {vanity} - insufficient data")
        
        # Return as list, sorted by vanity for consistency
        return [people[k] for k in sorted(people.keys())]
    
    def _parse_rsc_line(self, line: str) -> tuple:
        """
        Parse a single RSC line into its ID and data.
        
        Args:
            line: A single line from the RSC response.
            
        Returns:
            Tuple of (line_id, parsed_data) or (None, None) if parsing fails.
        """
        if not line or ':' not in line:
            logger.debug(f"Line parse failed: no colon found in line")
            return None, None
        
        try:
            # Split on first colon to get ID and data
            line_id_str, data_str = line.split(':', 1)
            line_id = line_id_str.strip()
            
            logger.debug(f"Parsing line ID '{line_id}', data preview: {data_str[:100]}...")
            
            # Try to parse as JSON
            try:
                data = json.loads(data_str)
                logger.debug(f"Line ID '{line_id}': Successfully parsed as JSON ({type(data).__name__})")
                return line_id, data
            except json.JSONDecodeError as e:
                # Not valid JSON, return as string
                logger.debug(f"Line ID '{line_id}': Not valid JSON, returning as string. Error: {str(e)[:100]}")
                return line_id, data_str
        except Exception as e:
            logger.debug(f"Line parse exception: {str(e)[:100]}")
            return None, None
    
    def _hydrate_rsc_references(self, data: Any, lookup_map: Dict[str, Any]) -> Any:
        """
        Recursively hydrate RSC references in the data structure.
        References like "$L5", "$4", etc. are replaced with actual data from lookup_map.
        
        Args:
            data: The data structure to hydrate (can be dict, list, string, etc.).
            lookup_map: Map of reference IDs to their actual data.
            
        Returns:
            The hydrated data structure.
        """
        if isinstance(data, str):
            # Check if this is a reference (e.g., "$L5", "$4")
            if data.startswith('$'):
                ref_id = data[1:]  # Remove the '$' prefix
                if ref_id in lookup_map:
                    # Recursively hydrate the referenced data
                    return self._hydrate_rsc_references(lookup_map[ref_id], lookup_map)
                else:
                    # Reference not found, return as-is
                    return data
            else:
                return data
        elif isinstance(data, list):
            # Recursively hydrate each item in the list
            return [self._hydrate_rsc_references(item, lookup_map) for item in data]
        elif isinstance(data, dict):
            # Recursively hydrate each value in the dict
            return {key: self._hydrate_rsc_references(value, lookup_map) for key, value in data.items()}
        else:
            # Return primitive types as-is
            return data
    
    def _extract_connection_from_hydrated_data(self, component_data: Any) -> Optional[Dict[str, Any]]:
        """
        Extract connection information from a hydrated RSC component.
        
        Args:
            component_data: A hydrated component that may contain connection data.
            
        Returns:
            Dict with connection info or None if not a valid connection component.
        """
        try:
            # Connection components typically have profile URLs and names
            profile_url = None
            name = None
            headline = None
            connected_date = None
            profile_id = None
            
            found_items = {
                'urls': [],
                'urns': [],
                'names': [],
                'headlines': [],
                'dates': []
            }
            
            # Recursively search for connection data
            def search_dict(obj, depth=0):
                nonlocal profile_url, name, headline, connected_date, profile_id
                
                if depth > 20:  # Prevent infinite recursion
                    return
                
                if isinstance(obj, dict):
                    # Extract firstName/lastName from payload
                    if 'payload' in obj and isinstance(obj['payload'], dict):
                        payload = obj['payload']
                        if 'firstName' in payload and 'lastName' in payload:
                            full_name = f"{payload['firstName']} {payload['lastName']}"
                            if not name:
                                name = full_name
                            found_items['names'].append(full_name)
                            logger.debug(f"Found name from payload: {full_name}")
                        if 'vanityName' in payload:
                            logger.debug(f"Found vanity name in payload: {payload['vanityName']}")
                    
                    # Look for profile URL
                    if 'url' in obj and isinstance(obj['url'], str) and 'linkedin.com/in/' in obj['url']:
                        if not profile_url:
                            profile_url = obj['url']
                            found_items['urls'].append(obj['url'])
                            logger.debug(f"Found profile URL: {obj['url']}")
                    
                    # Look for URN with profile ID
                    for key, value in obj.items():
                        if isinstance(value, str):
                            if 'urn:li:fsd_profile:' in value:
                                match = re.search(r'urn:li:fsd_profile:([A-Za-z0-9_-]+)', value)
                                if match and not profile_id:
                                    profile_id = match.group(1)
                                    found_items['urns'].append(value)
                                    logger.debug(f"Found profile URN: {value}")
                            elif 'linkedin.com/in/' in value:
                                if not profile_url:
                                    profile_url = value
                                    found_items['urls'].append(value)
                                    logger.debug(f"Found profile URL in value: {value}")
                            elif 'Connected on' in value and not connected_date:
                                # Keep the full "Connected on..." text
                                connected_date = value
                                found_items['dates'].append(value)
                                logger.debug(f"Found connection date: {connected_date}")
                        
                        # Recursively search nested structures
                        search_dict(value, depth + 1)
                    
                    # Look for children arrays that might contain text
                    if 'children' in obj and isinstance(obj['children'], list):
                        for child in obj['children']:
                            if isinstance(child, str):
                                logger.debug(f"Found child text: {child[:100]}")
                                
                                # Skip common UI strings
                                if child in ['Message', 'Show more actions', '$undefined', 'null']:
                                    continue
                                
                                # Check if this looks like a name
                                # Names can have: capital letters, spaces, special characters (emojis, accents), numbers
                                # But must be between 2-100 chars and have at least one uppercase letter
                                if len(child) >= 2 and len(child) <= 100 and any(c.isupper() for c in child):
                                    # If it has spaces OR special Unicode characters, it's likely a name
                                    if ' ' in child or any(ord(c) > 127 for c in child):
                                        if not name:
                                            name = child
                                        found_items['names'].append(child)
                                        logger.debug(f"Identified as potential name: {child}")
                                    # Or if it's long enough, could be a headline
                                    elif len(child) > 20:
                                        if not headline:
                                            headline = child
                                        found_items['headlines'].append(child)
                                        logger.debug(f"Identified as potential headline: {child[:50]}...")
                
                elif isinstance(obj, list):
                    for item in obj:
                        search_dict(item, depth + 1)
            
            search_dict(component_data)
            
            # Log what was found
            if any(found_items.values()):
                logger.debug(f"Component scan results: URLs={len(found_items['urls'])}, URNs={len(found_items['urns'])}, Names={len(found_items['names'])}, Headlines={len(found_items['headlines'])}, Dates={len(found_items['dates'])}")
            
            # If we have at least a profile URL or name, create a connection entry
            if profile_url or name or found_items['names']:
                # Use the first name if we haven't assigned one yet
                if not name and found_items['names']:
                    name = found_items['names'][0]
                
                # If we have multiple names and no headline, the second might be the headline
                if not headline and len(found_items['names']) > 1:
                    # Check if second name is different from first
                    if found_items['names'][1] != name:
                        headline = found_items['names'][1]
                
                # Use first headline if available
                if not headline and found_items['headlines']:
                    headline = found_items['headlines'][0]
                
                # Extract vanity name from URL if we don't have profile_id
                if not profile_id and profile_url:
                    match = re.search(r'linkedin\.com/in/([^/]+)', profile_url)
                    if match:
                        profile_id = match.group(1)
                
                # Must have at least profile_id or name
                if not profile_id and not name:
                    logger.debug("No profile_id or name found, skipping")
                    return None
                
                connection = {
                    "profile_id": profile_id or "unknown",
                    "name": name or "Unknown",
                    "headline": headline,
                    "profile_url": profile_url,
                    "connected_date": connected_date
                }
                logger.info(f"✓ Created connection: {connection['name']} ({connection['profile_id']})")
                return connection
            else:
                logger.debug("No connection data found in component (no URL or name)")
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting connection from component: {e}")
            logger.exception("Full traceback:")
            return None
    
    def _parse_connections_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse LinkedIn connections response using regex-based locality algorithm.
        
        This is much more robust than trying to parse RSC structure.
        It finds profile anchors (vanity URLs) and then uses windowed locality
        to associate nearby attributes (name, headline, URN, date).
        
        Args:
            response_text: The RSC response text from LinkedIn.
            
        Returns:
            List[Dict]: List of connection details with profile_id, name, headline, profile_url, and connected_date.
        """
        connections = []
        
        try:
            # Save raw response to file for debugging
            import os
            from datetime import datetime
            from pathlib import Path
            
            # Use absolute path relative to project root
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            debug_dir = project_root / "logs_debug"
            debug_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_file = debug_dir / f"connections_rsc_response_{timestamp}.txt"
            
            try:
                with open(str(debug_file), 'w', encoding='utf-8') as f:
                    f.write(response_text)
                logger.info(f"Saved raw RSC response to: {debug_file}")
            except Exception as e:
                logger.error(f"Could not save debug file: {e}")
                logger.exception("Debug file save error:")
            
            logger.info("=" * 80)
            logger.info("STARTING RSC PARSING")
            logger.info(f"Response length: {len(response_text)} characters")
            logger.info(f"Response lines: {len(response_text.strip().split(chr(10)))}")
            logger.info("=" * 80)
            
            # Use robust regex-based locality extraction (no RSC parsing needed)
            connections = self._extract_people_from_raw_text(response_text)
            
            logger.info("=" * 80)
            logger.info(f"PARSING COMPLETE: {len(connections)} connections extracted")
            logger.info("=" * 80)
            
            if len(connections) == 0:
                logger.error("NO CONNECTIONS EXTRACTED!")
                logger.error("Check the debug file for the raw response format")
                logger.error(f"Debug file: {debug_file}")
            
            return connections
            
        except Exception as e:
            logger.error(f"Error parsing connections response: {e}")
            logger.exception("Full traceback:")
            raise
    
    async def fetch_connections_list(self, start_index: int = 0) -> List[Dict[str, Any]]:
        """
        Fetch list of LinkedIn connections with pagination.
        
        Args:
            start_index: Starting index for pagination (default: 0).
            
        Returns:
            List[Dict]: List of connection details.
            
        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        import httpx
        
        logger.info(f"Fetching connections list (start_index: {start_index})")
        
        # Build URL and payload
        url = self._build_connections_url(start_index)
        payload = self._build_connections_payload(start_index)
        
        # Add content-type header for POST request
        headers = {
            **self.headers,
            "Content-Type": "application/json",
        }
        
        # Make the request using httpx client (like base class _make_request)
        # Note: This endpoint returns text/plain RSC format, not JSON
        async with httpx.AsyncClient(
            timeout=self.TIMEOUT,
            follow_redirects=True
        ) as client:
            try:
                response = await client.request(
                    method='POST',
                    url=url,
                    json=payload,
                    headers=headers
                )
                
                logger.info(f"LinkedIn API response status: {response.status_code}")
                
                # Raise exception for HTTP errors
                response.raise_for_status()
                
                # Get text response (not JSON)
                response_text = response.text
                
                # Parse the RSC response
                connections = self._parse_connections_response(response_text)
                
                logger.info(f"Successfully fetched {len(connections)} connections")
                return connections
                
            except httpx.HTTPStatusError as e:
                logger.error(f"LinkedIn API HTTP error: {e.response.status_code} - {e.response.text[:200]}")
                raise
            except httpx.TimeoutException:
                logger.error(f"LinkedIn API request timed out after {self.TIMEOUT}s")
                raise
            except Exception as e:
                logger.error(f"LinkedIn API request failed: {str(e)}")
                raise

