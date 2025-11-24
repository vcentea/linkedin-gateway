"""
LinkedIn Profile Contact Service - Contact information extraction.
"""
import logging
from datetime import datetime
from typing import Dict, Any

from .base import LinkedInServiceBase
from ..utils.profile_id_extractor import extract_profile_id

logger = logging.getLogger(__name__)


class LinkedInProfileContactService(LinkedInServiceBase):
    """Service for fetching LinkedIn profile contact information."""
    
    async def get_contact_info(self, member_identity: str) -> Dict[str, Any]:
        """
        Fetch contact information for a profile.
        
        URL pattern:
        /graphql?includeWebMetadata=true&variables=(memberIdentity:{username})
        &queryId=voyagerIdentityDashProfiles.c7452e58fa37646d09dae4920fc5b4b9
        
        Note: Uses publicIdentifier (username like 'izzword') not profile ID
        
        Returns:
            Dictionary with contact info (email, phone, website, birthday, connected_date)
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
            data = await self._make_request(url, debug_endpoint_type="contact_info")
            
            logger.info(f"[CONTACT_INFO] Raw response keys: {list(data.keys())}")
            
            if 'included' in data:
                logger.info(f"[CONTACT_INFO] 'included' array length: {len(data['included'])}")
                
                for i, item in enumerate(data['included']):
                    item_type = item.get('$type', 'unknown')
                    logger.info(f"[CONTACT_INFO] included[{i}] type: {item_type}")
                    logger.info(f"[CONTACT_INFO] included[{i}] keys: {list(item.keys())[:20]}")
                    
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
            return {
                'email': 'N/A',
                'phone': 'N/A',
                'website': 'N/A',
                'birthday': 'N/A',
                'connected_date': 'N/A'
            }
    
    def _extract_contact_info(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract contact information from LinkedIn API response."""
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
            
            profile_obj = None
            connection_obj = None
            
            logger.info(f"[CONTACT_INFO_EXTRACT] Searching through all {len(included)} items...")
            for idx, item in enumerate(included):
                item_type = item.get('$type', '')
                logger.info(f"[CONTACT_INFO_EXTRACT] Item {idx}: type = {item_type}")
                
                if 'Profile' in item_type and profile_obj is None:
                    profile_obj = item
                    logger.info(f"[CONTACT_INFO_EXTRACT] ✓ Found Profile object at index {idx}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Keys: {list(item.keys())[:15]}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Has emailAddress: {'emailAddress' in item}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Has websites: {'websites' in item}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Has birthDateOn: {'birthDateOn' in item}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Has phoneNumbers: {'phoneNumbers' in item}")
                
                if ('Connection' in item_type or 'memberRelationship' in item_type) and connection_obj is None:
                    connection_obj = item
                    logger.info(f"[CONTACT_INFO_EXTRACT] ✓ Found Connection object at index {idx}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Keys: {list(item.keys())[:10]}")
                    logger.info(f"[CONTACT_INFO_EXTRACT]   - Has createdAt: {'createdAt' in item}")
            
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
            logger.info(f"[CONTACT_INFO_EXTRACT] Attempting to extract phone...")
            try:
                phone_numbers = profile_obj.get('phoneNumbers', [])
                if phone_numbers and len(phone_numbers) > 0:
                    logger.info(f"[CONTACT_INFO_EXTRACT] phoneNumbers array length: {len(phone_numbers)}")
                    logger.info(f"[CONTACT_INFO_EXTRACT] first phoneNumbers element: {phone_numbers[0]}")
                    
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
            
            # Extract connected date
            logger.info(f"[CONTACT_INFO_EXTRACT] Attempting to extract connected date...")
            if connection_obj:
                try:
                    created_at_ms = connection_obj.get('createdAt')
                    logger.info(f"[CONTACT_INFO_EXTRACT] createdAt value: {created_at_ms}")
                    if created_at_ms:
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
            logger.error(f"[CONTACT_INFO_EXTRACT] Error in _extract_contact_info: {str(e)}")
        
        return contact_info
    
    async def scrape_profile_contact(self, profile_id_or_url: str, vanity_name: str = None) -> Dict[str, Any]:
        """
        Scrape contact information for a LinkedIn profile.
        
        Args:
            profile_id_or_url: Profile ID or URL (used to extract vanity name if not provided)
            vanity_name: Optional vanity name if already known
        
        Returns:
            Dictionary with contact information
        """
        logger.info(f"[PROFILE_CONTACT] Starting contact scrape")
        
        # If vanity name not provided, extract it from profile ID
        if not vanity_name or vanity_name == 'N/A':
            # Need to import the identity service to get vanity name
            from .profile_identity import LinkedInProfileIdentityService
            identity_service = LinkedInProfileIdentityService(
                csrf_token=self.csrf_token,
                linkedin_cookies=self.linkedin_cookies
            )
            profile_id = await extract_profile_id(
                profile_input=profile_id_or_url,
                headers=self.headers,
                timeout=self.TIMEOUT
            )
            identity = await identity_service.get_profile_identity_cards(profile_id)
            vanity_name = identity['vanity_name']
        
        if not vanity_name or vanity_name == 'N/A':
            logger.warning("[PROFILE_CONTACT] No vanity name available")
            return {
                'email': 'N/A',
                'phone': 'N/A',
                'website': 'N/A',
                'birthday': 'N/A',
                'connected_date': 'N/A'
            }
        
        contact_info = await self.get_contact_info(vanity_name)
        
        logger.info(f"[PROFILE_CONTACT] Contact scrape completed")
        return contact_info

