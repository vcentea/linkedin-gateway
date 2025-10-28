"""
LinkedIn Profile About & Skills Service - About section and skills extraction.
"""
import logging
from typing import Dict, Any, List

from .base import LinkedInServiceBase
from ..utils.profile_id_extractor import extract_profile_id

logger = logging.getLogger(__name__)


class LinkedInProfileAboutSkillsService(LinkedInServiceBase):
    """Service for fetching LinkedIn profile about section and skills."""
    
    def _find_profile_card_by_urn_keyword(self, data: Dict[str, Any], keyword: str) -> Dict[str, Any]:
        """
        Find a profile card by searching for a keyword in the entityUrn.
        
        Args:
            data: The API response data
            keyword: Keyword to search for in entityUrn (e.g., 'EXPERIENCE', 'LANGUAGES', 'RECOMMENDATIONS')
            
        Returns:
            The profile card dict if found, otherwise empty dict
        """
        included = data.get('included', [])
        for item in included:
            if isinstance(item, dict):
                entity_urn = item.get('entityUrn', '')
                if keyword in entity_urn:
                    logger.info(f"[PROFILE_CARD] Found card with keyword '{keyword}': {entity_urn}")
                    return item
        
        logger.warning(f"[PROFILE_CARD] No card found with keyword '{keyword}'")
        return {}
    
    def _extract_experiences(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract experience entries from profile cards data.
        
        Returns:
            List of experience dictionaries
        """
        experiences = []
        
        try:
            # Find the EXPERIENCE card
            exp_card = self._find_profile_card_by_urn_keyword(data, 'EXPERIENCE')
            if not exp_card:
                return experiences
            
            # Navigate to fixedListComponent
            top_components = exp_card.get('topComponents', [])
            for top_comp in top_components:
                if isinstance(top_comp, dict):
                    components = top_comp.get('components', {})
                    if isinstance(components, dict):
                        fixed_list = components.get('fixedListComponent', {})
                        if isinstance(fixed_list, dict):
                            list_components = fixed_list.get('components', [])
                            
                            # Iterate through each experience entry
                            for list_item in list_components:
                                if isinstance(list_item, dict):
                                    item_comps = list_item.get('components', {})
                                    if isinstance(item_comps, dict):
                                        entity = item_comps.get('entityComponent', {})
                                        if isinstance(entity, dict) and entity.get('$type') == 'com.linkedin.voyager.dash.identity.profile.tetris.EntityComponent':
                                            
                                            # Extract job details
                                            experience = {
                                                'title': '',
                                                'company': '',
                                                'employment_type': '',
                                                'dates': '',
                                                'location': '',
                                                'description': ''
                                            }
                                            
                                            # Job Title
                                            title_v2 = entity.get('titleV2', {})
                                            if isinstance(title_v2, dict):
                                                title_text = title_v2.get('text', {})
                                                experience['title'] = title_text.get('text', '') if isinstance(title_text, dict) else title_text if isinstance(title_text, str) else ''
                                            
                                            # Company Name & Employment Type
                                            subtitle = entity.get('subtitle', {})
                                            if isinstance(subtitle, dict):
                                                subtitle_text = subtitle.get('text', '')
                                                experience['company'] = subtitle_text if isinstance(subtitle_text, str) else ''
                                            
                                            # Dates of Employment
                                            caption = entity.get('caption', {})
                                            if isinstance(caption, dict):
                                                caption_text = caption.get('text', '')
                                                experience['dates'] = caption_text if isinstance(caption_text, str) else ''
                                            
                                            # Location
                                            metadata = entity.get('metadata', {})
                                            if isinstance(metadata, dict):
                                                metadata_text = metadata.get('text', '')
                                                experience['location'] = metadata_text if isinstance(metadata_text, str) else ''
                                            
                                            # Description (from subComponents)
                                            sub_components = entity.get('subComponents', [])
                                            for sub_comp in sub_components:
                                                if isinstance(sub_comp, dict):
                                                    sub_comps = sub_comp.get('components', {})
                                                    if isinstance(sub_comps, dict):
                                                        text_comp = sub_comps.get('textComponent', {})
                                                        if isinstance(text_comp, dict):
                                                            text_obj = text_comp.get('text', {})
                                                            desc_text = text_obj.get('text', '') if isinstance(text_obj, dict) else text_obj if isinstance(text_obj, str) else ''
                                                            if desc_text:
                                                                experience['description'] = desc_text
                                                                break
                                            
                                            experiences.append(experience)
                                            logger.debug(f"[EXPERIENCES] Extracted: {experience['title']} at {experience['company']}")
            
            logger.info(f"[EXPERIENCES] ✓ Extracted {len(experiences)} experience entries")
        
        except Exception as e:
            logger.error(f"[EXPERIENCES] ✗ Error extracting experiences: {e}", exc_info=True)
        
        return experiences
    
    def _extract_recommendations(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract received recommendations from profile cards data.
        
        Returns:
            List of recommendation dictionaries
        """
        recommendations = []
        
        try:
            # Find the RECOMMENDATIONS card
            rec_card = self._find_profile_card_by_urn_keyword(data, 'RECOMMENDATIONS')
            if not rec_card:
                logger.info(f"[RECOMMENDATIONS] No recommendations card found in response")
                return recommendations
            
            # Navigate to fixedListComponent
            top_components = rec_card.get('topComponents', [])
            for top_comp in top_components:
                if isinstance(top_comp, dict):
                    components = top_comp.get('components', {})
                    if isinstance(components, dict):
                        fixed_list = components.get('fixedListComponent', {})
                        if isinstance(fixed_list, dict):
                            list_components = fixed_list.get('components', [])
                            
                            # Iterate through each recommendation entry
                            for list_item in list_components:
                                if isinstance(list_item, dict):
                                    item_comps = list_item.get('components', {})
                                    if isinstance(item_comps, dict):
                                        entity = item_comps.get('entityComponent', {})
                                        if isinstance(entity, dict):
                                            
                                            # Extract recommendation details
                                            recommendation = {
                                                'recommender_name': '',
                                                'recommender_title': '',
                                                'recommendation_text': ''
                                            }
                                            
                                            # Recommender's Name
                                            title_v2 = entity.get('titleV2', {})
                                            if isinstance(title_v2, dict):
                                                title_text = title_v2.get('text', {})
                                                recommendation['recommender_name'] = title_text.get('text', '') if isinstance(title_text, dict) else title_text if isinstance(title_text, str) else ''
                                            
                                            # Recommender's Title
                                            subtitle = entity.get('subtitle', {})
                                            if isinstance(subtitle, dict):
                                                subtitle_text = subtitle.get('text', '')
                                                recommendation['recommender_title'] = subtitle_text if isinstance(subtitle_text, str) else ''
                                            
                                            # Recommendation Text (from subComponents)
                                            sub_components = entity.get('subComponents', [])
                                            for sub_comp in sub_components:
                                                if isinstance(sub_comp, dict):
                                                    sub_comps = sub_comp.get('components', {})
                                                    if isinstance(sub_comps, dict):
                                                        text_comp = sub_comps.get('textComponent', {})
                                                        if isinstance(text_comp, dict):
                                                            text_obj = text_comp.get('text', {})
                                                            rec_text = text_obj.get('text', '') if isinstance(text_obj, dict) else text_obj if isinstance(text_obj, str) else ''
                                                            if rec_text:
                                                                recommendation['recommendation_text'] = rec_text
                                                                break
                                            
                                            recommendations.append(recommendation)
                                            logger.debug(f"[RECOMMENDATIONS] Extracted from: {recommendation['recommender_name']}")
            
            logger.info(f"[RECOMMENDATIONS] ✓ Extracted {len(recommendations)} recommendations")
        
        except Exception as e:
            logger.error(f"[RECOMMENDATIONS] ✗ Error extracting recommendations: {e}", exc_info=True)
        
        return recommendations
    
    def _extract_languages(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract languages and proficiency levels from profile cards data.
        
        Returns:
            List of language dictionaries with 'name' and 'proficiency'
        """
        languages = []
        
        try:
            # Find the LANGUAGES card
            lang_card = self._find_profile_card_by_urn_keyword(data, 'LANGUAGES')
            if not lang_card:
                return languages
            
            # Navigate to fixedListComponent
            top_components = lang_card.get('topComponents', [])
            for top_comp in top_components:
                if isinstance(top_comp, dict):
                    components = top_comp.get('components', {})
                    if isinstance(components, dict):
                        fixed_list = components.get('fixedListComponent', {})
                        if isinstance(fixed_list, dict):
                            list_components = fixed_list.get('components', [])
                            
                            # Iterate through each language entry
                            for list_item in list_components:
                                if isinstance(list_item, dict):
                                    item_comps = list_item.get('components', {})
                                    if isinstance(item_comps, dict):
                                        entity = item_comps.get('entityComponent', {})
                                        if isinstance(entity, dict) and entity.get('$type') == 'com.linkedin.voyager.dash.identity.profile.tetris.EntityComponent':
                                            
                                            # Extract language details
                                            language = {
                                                'name': '',
                                                'proficiency': ''
                                            }
                                            
                                            # Language Name
                                            title_v2 = entity.get('titleV2', {})
                                            if isinstance(title_v2, dict):
                                                title_text = title_v2.get('text', {})
                                                language['name'] = title_text.get('text', '') if isinstance(title_text, dict) else title_text if isinstance(title_text, str) else ''
                                            
                                            # Proficiency Level
                                            caption = entity.get('caption', {})
                                            if isinstance(caption, dict):
                                                caption_text = caption.get('text', '')
                                                language['proficiency'] = caption_text if isinstance(caption_text, str) else ''
                                            
                                            languages.append(language)
                                            logger.debug(f"[LANGUAGES] Extracted: {language['name']} - {language['proficiency']}")
            
            logger.info(f"[LANGUAGES] ✓ Extracted {len(languages)} languages")
        
        except Exception as e:
            logger.error(f"[LANGUAGES] ✗ Error extracting languages: {e}", exc_info=True)
        
        return languages
    
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
        
        Returns:
            Dictionary with 'about' (string) and 'top_skills' (list of strings)
        """
        logger.info(f"[ABOUT_SKILLS] ========================================")
        logger.info(f"[ABOUT_SKILLS] Fetching about and skills for profile {profile_id}")
        logger.info(f"[ABOUT_SKILLS] ========================================")
        
        url = f"{self.GRAPHQL_BASE_URL}?includeWebMetadata=true&variables=(profileUrn:urn%3Ali%3Afsd_profile%3A{profile_id})&queryId=voyagerIdentityDashProfileCards.f0415f0ff9d9968bab1cd89c0352f7c8"
        
        logger.info(f"[ABOUT_SKILLS] Request URL: {url}")
        
        result = {
            'about': 'N/A',
            'top_skills': [],
            'languages': []
        }
        
        try:
            data = await self._make_request(url, debug_endpoint_type="about_skills")
            
            logger.info(f"[ABOUT_SKILLS] Raw response keys: {list(data.keys())}")
            
            # Extract About section using recursive search for TextComponent
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            logger.info(f"[ABOUT_SKILLS] Searching for TextComponents recursively...")
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            
            try:
                # Search entire response for TextComponent objects
                text_components = self._find_text_components_recursive(data)
                logger.info(f"[ABOUT_SKILLS] Found {len(text_components)} TextComponent(s) with non-empty text")
                
                # Log all found text components
                for idx, comp in enumerate(text_components):
                    text_preview = comp['text'][:100] if len(comp['text']) > 100 else comp['text']
                    logger.info(f"[ABOUT_SKILLS] TextComponent {idx+1}: {len(comp['text'])} chars - '{text_preview}...'")
                
                # Use the first non-empty text component as the about section
                # (LinkedIn typically puts the about section first)
                if text_components:
                    result['about'] = text_components[0]['text']
                    logger.info(f"[ABOUT_SKILLS] ✓ Extracted about text ({len(result['about'])} chars)")
                else:
                    logger.warning(f"[ABOUT_SKILLS] ✗ No TextComponent found with non-empty text")
            
            except (KeyError, TypeError, AttributeError, IndexError) as e:
                logger.error(f"[ABOUT_SKILLS] ✗ Could not extract about section: {e}", exc_info=True)
            
            # Extract Top Skills (keep existing logic for now - skills are in a different structure)
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            logger.info(f"[ABOUT_SKILLS] Attempting to extract TOP SKILLS...")
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            
            try:
                # Search for skills in subtitle text (separated by •)
                included = data.get('included', [])
                for item in included:
                    if isinstance(item, dict):
                        # Look for subComponents with skills
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
            
            # Extract Languages
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            logger.info(f"[ABOUT_SKILLS] Attempting to extract LANGUAGES...")
            logger.info(f"[ABOUT_SKILLS] ----------------------------------------")
            result['languages'] = self._extract_languages(data)
            
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
    
    async def scrape_profile_about_skills(self, profile_id_or_url: str) -> Dict[str, Any]:
        """
        Scrape about section, skills, and languages for a LinkedIn profile.
        
        Returns:
            Dictionary with 'about', 'skills', 'languages'
        """
        logger.info(f"[PROFILE_ABOUT_SKILLS] Starting profile data scrape for: {profile_id_or_url}")
        
        profile_id = await extract_profile_id(
            profile_input=profile_id_or_url,
            headers=self.headers,
            timeout=self.TIMEOUT
        )
        logger.info(f"[PROFILE_ABOUT_SKILLS] Using profile ID: {profile_id}")
        
        data = await self.get_about_and_skills(profile_id)
        
        result = {
            'about': data.get('about', 'N/A'),
            'skills': data.get('top_skills', []),
            'languages': data.get('languages', [])
        }
        
        logger.info(f"[PROFILE_ABOUT_SKILLS] Profile data scrape completed for {profile_id}")
        return result

