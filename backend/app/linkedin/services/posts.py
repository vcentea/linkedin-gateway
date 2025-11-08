"""
LinkedIn Posts API service.

Provides server-side implementation of post operations including text extraction from HTML.
"""
from typing import Optional, Dict, Any
import logging
import json
import re
import html as html_module

from .base import LinkedInServiceBase

logger = logging.getLogger(__name__)

class LinkedInPostsService(LinkedInServiceBase):
    """Service for LinkedIn post operations."""
    
    def extract_post_text_from_html(self, html_content: str) -> Optional[str]:
        """
        Extract post text from LinkedIn HTML response.
        
        LinkedIn embeds JSON data in <code> tags with IDs like 'bpr-guid-XXXXX'.
        The post text is typically in objects with types:
        - com.linkedin.voyager.dash.feed.Update
        - com.linkedin.voyager.dash.feed.ShareUpdate
        
        The text is located at:
        - commentary.text.text (nested format)
        - commentary.text (direct string format)
        
        Args:
            html_content: Raw HTML content from LinkedIn post page
            
        Returns:
            Post text string if found, None otherwise
        """
        if not html_content:
            logger.warning("[EXTRACT_POST_TEXT] Empty HTML content provided")
            return None
        
        logger.info(f"[EXTRACT_POST_TEXT] Processing HTML content ({len(html_content)} bytes)")
        
        # Find all <code> tags that typically contain JSON data
        # Pattern: <code style="display: none" id="bpr-guid-XXXXX">JSON_DATA</code>
        code_pattern = r'<code[^>]*id="bpr-guid-\d+"[^>]*>(.*?)</code>'
        code_blocks = re.findall(code_pattern, html_content, re.DOTALL)
        
        logger.info(f"[EXTRACT_POST_TEXT] Found {len(code_blocks)} code blocks to analyze")
        
        for idx, code_block in enumerate(code_blocks):
            try:
                # Decode HTML entities (e.g., &quot; -> ")
                decoded_content = html_module.unescape(code_block)
                
                # Try to parse as JSON
                try:
                    data = json.loads(decoded_content)
                except json.JSONDecodeError:
                    # Not valid JSON, skip
                    continue
                
                # Look for post text in the 'included' array
                included = data.get('included', [])
                if not isinstance(included, list):
                    continue
                
                for item in included:
                    if not isinstance(item, dict):
                        continue
                    
                    # Check if this is a post Update object
                    item_type = item.get('$type', '')
                    if item_type not in [
                        'com.linkedin.voyager.dash.feed.Update',
                        'com.linkedin.voyager.dash.feed.ShareUpdate'
                    ]:
                        continue
                    
                    # Try to extract commentary text
                    commentary = item.get('commentary', {})
                    if not isinstance(commentary, dict):
                        continue
                    
                    # Handle nested format: commentary.text.text
                    text_field = commentary.get('text')
                    if isinstance(text_field, dict):
                        post_text = text_field.get('text')
                        if post_text and isinstance(post_text, str):
                            logger.info(f"[EXTRACT_POST_TEXT] ✓ Found post text (nested format) in block {idx}: {post_text[:100]}...")
                            return post_text
                    
                    # Handle direct string format: commentary.text
                    elif isinstance(text_field, str):
                        logger.info(f"[EXTRACT_POST_TEXT] ✓ Found post text (direct format) in block {idx}: {text_field[:100]}...")
                        return text_field
                
            except Exception as e:
                logger.debug(f"[EXTRACT_POST_TEXT] Error processing code block {idx}: {e}")
                continue
        
        logger.warning("[EXTRACT_POST_TEXT] Post text not found in any code block")
        return None
    
    async def fetch_post_html(self, post_url: str) -> str:
        """
        Fetch the HTML content of a LinkedIn post page.
        
        Args:
            post_url: Full URL of the LinkedIn post
            
        Returns:
            HTML content as string
            
        Raises:
            httpx.HTTPStatusError: If the API request fails
        """
        import httpx
        
        logger.info(f"[FETCH_POST_HTML] Fetching HTML for URL: {post_url}")
        
        # Make GET request to the post URL
        # LinkedIn returns HTML with embedded JSON data
        async with httpx.AsyncClient(
            timeout=self.TIMEOUT,
            follow_redirects=True
        ) as client:
            try:
                response = await client.request(
                    method='GET',
                    url=post_url,
                    headers=self.headers
                )
                
                logger.info(f"[FETCH_POST_HTML] Response status: {response.status_code}")
                response.raise_for_status()
                
                html_content = response.text
                logger.info(f"[FETCH_POST_HTML] Received HTML response ({len(html_content)} bytes)")
                
                return html_content
                
            except httpx.HTTPStatusError as e:
                logger.error(f"[FETCH_POST_HTML] HTTP error: {e.response.status_code}")
                raise
            except httpx.TimeoutException:
                logger.error(f"[FETCH_POST_HTML] Request timed out after {self.TIMEOUT}s")
                raise
            except Exception as e:
                logger.error(f"[FETCH_POST_HTML] Request failed: {str(e)}")
                raise
