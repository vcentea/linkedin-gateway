"""
LinkedIn Direct Messaging API service.

Mirrors functionality from chrome-extension/src/services/profile_service.js
Provides server-side implementation of direct messaging operations.
"""
from typing import Dict, Any, Optional
from .base import LinkedInServiceBase
import json
import logging
import random
import string
import re
import uuid
import asyncio

logger = logging.getLogger(__name__)


def _randomize_uuid_tracking(uuid_str: str) -> str:
    """
    Randomize 1 character in a UUID string (like the browser does).
    EXACT copy from test_endpoint_2_conversation_details_js.py
    
    Args:
        uuid_str: UUID string to randomize
        
    Returns:
        UUID string with 1 character randomized
    """
    # Remove hyphens for easier manipulation
    uuid_clean = uuid_str.replace('-', '')
    
    # Pick a random position to change (0-31)
    pos = random.randint(0, len(uuid_clean) - 1)
    
    # Generate a random hex character
    new_char = random.choice('0123456789abcdef')
    
    # Replace the character at that position
    uuid_list = list(uuid_clean)
    uuid_list[pos] = new_char
    uuid_randomized = ''.join(uuid_list)
    
    # Re-insert hyphens at standard UUID positions
    return f"{uuid_randomized[:8]}-{uuid_randomized[8:12]}-{uuid_randomized[12:16]}-{uuid_randomized[16:20]}-{uuid_randomized[20:]}"


def _uuid_to_latin1_bytes(uuid_str: str) -> str:
    """
    Convert UUID to Latin-1 encoded bytes string (for trackingId).
    EXACT copy from test_endpoint_2_conversation_details_js.py
    
    Args:
        uuid_str: UUID string
        
    Returns:
        Latin-1 encoded string with "weird characters"
    """
    # Remove hyphens and convert to bytes
    uuid_clean = uuid_str.replace('-', '')
    uuid_bytes = bytes.fromhex(uuid_clean)
    # Decode as Latin-1 to get the "weird characters"
    return uuid_bytes.decode('latin-1')


class LinkedInMessageService(LinkedInServiceBase):
    """Service for LinkedIn direct messaging operations."""
    
    def _build_headers(self) -> Dict[str, str]:
        """
        Override to use golden recipe headers for messaging.
        Uses the proven header pattern that works with LinkedIn API.
        """
        # Get base headers from parent (golden recipe)
        headers = super()._build_headers()
        
        # For messaging, override the accept header to use */* (works better for messaging endpoints)
        headers['accept'] = '*/*'
        
        # For messaging, we need Content-Type for POST requests
        # Based on working browser requests: text/plain;charset=UTF-8
        headers['content-type'] = 'text/plain;charset=UTF-8'
        
        logger.debug(f"Built messaging headers with golden recipe + messaging-specific headers")
        return headers
    
    def _randomize_edges_hex(self, input_string: str) -> str:
        """
        Randomize the first and last 3 characters using HEX ONLY for UUID format.
        Used for originToken to maintain valid UUID format.
        
        Args:
            input_string: The UUID string to randomize.
            
        Returns:
            String with randomized first and last 3 characters using hex digits only.
        """
        if len(input_string) < 7:
            logger.warning('String too short to randomize edges, returning as is')
            return input_string
        
        # Generate random hex characters only (0-9, a-f) for UUID format
        def random_hex_char():
            return random.choice('0123456789abcdef')
        
        # Randomize first three and last three characters with hex only
        randomized = ''
        for _ in range(3):
            randomized += random_hex_char()
        
        randomized += input_string[3:-3]  # Middle part stays the same
        
        for _ in range(3):
            randomized += random_hex_char()
        
        return randomized
    
    def _randomize_edges_raw(self, input_string: str) -> str:
        """
        Find normal printable ASCII characters in the string and randomize only 1 of them.
        Used for trackingId to preserve raw binary format with minimal changes.
        
        Args:
            input_string: The raw string to randomize.
            
        Returns:
            String with 1 printable ASCII character randomized.
        """
        if len(input_string) < 1:
            logger.warning('String too short to randomize, returning as is')
            return input_string
        
        # Find all printable ASCII characters (32-126) in the string
        printable_positions = []
        for i, char in enumerate(input_string):
            if 32 <= ord(char) <= 126:  # Printable ASCII range
                printable_positions.append(i)
        
        if not printable_positions:
            logger.warning('No printable ASCII characters found, returning as is')
            return input_string
        
        # Choose one random position to modify
        position_to_change = random.choice(printable_positions)
        
        # Generate a random printable ASCII character
        def random_printable_char():
            return chr(random.randint(32, 126))  # Printable ASCII 32 to 126
        
        # Convert string to list for modification
        chars = list(input_string)
        chars[position_to_change] = random_printable_char()
        
        result = ''.join(chars)
        logger.debug(f'Randomized position {position_to_change}: {repr(input_string[position_to_change])} -> {repr(chars[position_to_change])}')
        
        return result
    
    
    def _extract_mailbox_urn(self, sdk_entity_urn: str) -> Optional[str]:
        """
        Extract mailbox URN from SDK entity URN.
        
        Mirrors extractMailboxUrn from profile_service.js
        
        Args:
            sdk_entity_urn: The SDK entity URN string.
            
        Returns:
            Extracted mailbox URN or None if not found.
        """
        match = re.search(r'urn:li:msg_conversation:\(([^,]+),', sdk_entity_urn)
        return match.group(1) if match else None
    
    async def _get_compose_options(self, profile_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        Get conversation URN and li_mc cookie from compose options endpoint.
        EXACT 1:1 copy from test_endpoint_2_conversation_details_js.py (lines 157-236)
        
        Args:
            profile_id: The LinkedIn profile ID.
            
        Returns:
            Tuple of (conversation_urn, li_mc_cookie)
            - conversation_urn: URN if existing conversation, None for new conversation
            - li_mc_cookie: Messaging context cookie from LinkedIn (if provided)
        """
        # Build the compose options URL with the profile ID
        url = f"{self.VOYAGER_BASE_URL}/voyagerMessagingDashComposeOptions/urn%3Ali%3Afsd_composeOption%3A({profile_id}%2CNONE%2CEMPTY_CONTEXT_ENTITY_URN)"
        
        logger.info(f"[MESSAGE SERVICE] Getting compose options for profile: {profile_id}")
        
        try:
            # EXACT headers from test script (lines 179-193)
            # Uses the messaging service's _build_headers which already has accept: '*/*'
            headers = self._build_headers()
            
            # For GET requests, remove content-type (not needed)
            if 'content-type' in headers:
                del headers['content-type']
            
            logger.info(f"[MESSAGE SERVICE] Compose options headers: accept={headers.get('accept')}")
            
            # Make the request using base class method
            data = await self._make_request(
                url=url,
                method='GET',
                headers=headers
            )
            
            # Log response summary (not full data to avoid huge logs)
            logger.info(f"[MESSAGE SERVICE] Received compose options response")
            logger.info(f"[MESSAGE SERVICE] Response type: {type(data)}")
            logger.info(f"[MESSAGE SERVICE] Response keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
            
            # Extract li_mc cookie from response (if provided by LinkedIn)
            # Note: _make_request returns parsed JSON, not response object with cookies
            # We'll need to handle li_mc differently if needed
            li_mc_cookie = None
            
            # Extract conversation URN from the response
            # EXACT parsing from test script (line 217)
            # Note: Response has NO 'data' wrapper - it's directly at the root level
            conversation_urn = data.get('composeNavigationContext', {}).get('existingConversationUrn')
            compose_option_type = data.get('composeOptionType', 'UNKNOWN')
            
            if conversation_urn:
                logger.info(f"[MESSAGE SERVICE] Got existing conversation URN: {conversation_urn}")
                logger.info(f"[MESSAGE SERVICE] composeOptionType: {compose_option_type}")
            else:
                logger.info(f"[MESSAGE SERVICE] No existing conversation URN (new contact)")
                logger.info(f"[MESSAGE SERVICE] composeOptionType: {compose_option_type}")
            
            return conversation_urn, li_mc_cookie
            
        except Exception as e:
            logger.error(f"[MESSAGE SERVICE] Error getting compose options: {e}")
            import traceback
            logger.error(f"[MESSAGE SERVICE] Traceback: {traceback.format_exc()}")
            return None, None
    
    async def prepare_send_message_request(
        self,
        target_profile_id: str,
        message_text: str,
        my_profile_id: str,
    ) -> tuple[str, Dict[str, Any], Optional[str]]:
        """
        Prepare the URL and payload for sending a direct message.
        EXACT implementation from test_endpoint_2_conversation_details_js.py

        This method builds the request but doesn't execute it.
        Used by both server_call and proxy modes.

        Args:
            target_profile_id: REQUIRED. The target LinkedIn profile ID (already extracted).
                              Use /utils/extract-profile-id logic to extract it before calling this method.
            message_text: The message text to send.
            my_profile_id: REQUIRED. The sender's LinkedIn profile ID.
                          Use get_my_profile_id_with_fallbacks() utility to fetch it before calling this method.

        Returns:
            Tuple of (url, payload_json, li_mc_cookie) ready for execution.
            - url: The API endpoint URL
            - payload_json: The message payload
            - li_mc_cookie: Messaging context cookie from LinkedIn (if provided)

        Raises:
            ValueError: If target_profile_id, message_text, or my_profile_id is invalid.
        """
        if not target_profile_id:
            raise ValueError("target_profile_id is required")

        if not message_text or not message_text.strip():
            raise ValueError("message_text is required and cannot be empty")

        if not my_profile_id:
            raise ValueError(
                "my_profile_id is required. "
                "Use get_my_profile_id_with_fallbacks() utility from app.linkedin.utils.my_profile_id "
                "to fetch it before calling this method."
            )

        # Profile ID is already extracted by the caller using the robust /utils/extract-profile-id logic
        profile_id = target_profile_id

        logger.info(f"[MESSAGE SERVICE] Preparing message request for profile: {profile_id}")

        # Step 1: Get conversation URN and li_mc cookie from compose options endpoint
        # This is the PROVEN approach from our working test script
        conversation_urn, li_mc_cookie = await self._get_compose_options(profile_id)

        # Step 2: Generate fresh tokens with 1 character randomization (like the browser)
        origin_token = _randomize_uuid_tracking(str(uuid.uuid4()))
        tracking_id_latin1 = _uuid_to_latin1_bytes(_randomize_uuid_tracking(str(uuid.uuid4())))

        logger.info(f"[MESSAGE SERVICE] Generated fresh tokens:")
        logger.info(f"[MESSAGE SERVICE]   originToken: {origin_token}")
        logger.info(f"[MESSAGE SERVICE]   trackingId (Latin-1): {repr(tracking_id_latin1)}")

        # Step 3: Build message payload - EXACT format from working request
        # Two cases: existing conversation vs. new conversation

        # my_profile_id is now always provided as a required parameter
        
        my_profile_urn = f"urn:li:fsd_profile:{my_profile_id}"
        recipient_profile_urn = f"urn:li:fsd_profile:{profile_id}"
        
        if conversation_urn:
            # CASE 1: EXISTING CONVERSATION (REPLY)
            # Convert conversation URN to msg_conversation format
            # Browser format: urn:li:msg_conversation:(urn:li:fsd_profile:SENDER_ID,CONVERSATION_ID)
            # We receive: urn:li:fsd_conversation:CONVERSATION_ID
            
            conversation_id = conversation_urn.replace("urn:li:fsd_conversation:", "")
            msg_conversation_urn = f"urn:li:msg_conversation:({my_profile_urn},{conversation_id})"
            
            logger.info(f"[MESSAGE SERVICE] EXISTING CONVERSATION - Converted URN:")
            logger.info(f"[MESSAGE SERVICE]   From: {conversation_urn}")
            logger.info(f"[MESSAGE SERVICE]   To:   {msg_conversation_urn}")
            
            payload = {
                "message": {
                    "body": {
                        "attributes": [],
                        "text": message_text
                    },
                    "renderContentUnions": [],
                    "conversationUrn": msg_conversation_urn,
                    "originToken": origin_token
                },
                "mailboxUrn": my_profile_urn,
                "trackingId": tracking_id_latin1,
                "dedupeByClientGeneratedToken": False
            }
        else:
            # CASE 2: NEW CONVERSATION (CONNECTION_MESSAGE)
            # No conversationUrn, use hostRecipientUrns instead
            # mailboxUrn is the SENDER (me), hostRecipientUrns is the RECIPIENT
            
            logger.info(f"[MESSAGE SERVICE] NEW CONVERSATION - First message to contact")
            logger.info(f"[MESSAGE SERVICE]   Sender (mailboxUrn): {my_profile_urn}")
            logger.info(f"[MESSAGE SERVICE]   Recipient (hostRecipientUrns): {recipient_profile_urn}")
            
            payload = {
                "message": {
                    "body": {
                        "attributes": [],
                        "text": message_text
                    },
                    "originToken": origin_token,
                    "renderContentUnions": []
                },
                "mailboxUrn": my_profile_urn,  # SENDER (me)
                "trackingId": tracking_id_latin1,
                "dedupeByClientGeneratedToken": False,
                "hostRecipientUrns": [recipient_profile_urn]  # RECIPIENT (them)
            }
        
        url = f"{self.VOYAGER_BASE_URL}/voyagerMessagingDashMessengerMessages?action=createMessage"
        
        return url, payload, li_mc_cookie

    async def send_direct_message(
        self, 
        profile_identifier: str, 
        message_text: str
    ) -> Dict[str, Any]:
        """
        Send a direct message to a LinkedIn profile.
        EXACT implementation from test_endpoint_2_conversation_details_js.py
        
        Args:
            profile_identifier: The LinkedIn profile ID or profile URL with vanity name.
            message_text: The message text to send.
            
        Returns:
            Dict containing the API response.
            
        Raises:
            ValueError: If profile_identifier or message_text is invalid.
            httpx.HTTPStatusError: If the API request fails.
        """
        # Use the new prepare method and then execute
        url, payload, li_mc_cookie = await self.prepare_send_message_request(profile_identifier, message_text)
        
        # Make the request with text/plain content-type
        # Convert payload to JSON string (compact, no spaces - matching browser behavior)
        payload_str = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        
        # Encode as UTF-8 bytes (CRITICAL - matches working request exactly)
        payload_bytes = payload_str.encode('utf-8')
        
        logger.info(f"[MESSAGE SERVICE] Sending message to LinkedIn")
        logger.info(f"[MESSAGE SERVICE] URL: {url}")
        logger.info(f"[MESSAGE SERVICE] Payload length: {len(payload_bytes)} bytes")
        
        data = await self._make_request(
            url=url,
            method='POST',
            content=payload_bytes  # Send as bytes, not string!
        )
        
        logger.info(f"[MESSAGE SERVICE] Successfully sent message via service")
        return data

