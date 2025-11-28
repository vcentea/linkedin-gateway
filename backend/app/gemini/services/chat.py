"""
Gemini Chat Service for content generation.

Provides functionality for:
- Generating content using Gemini models
- Streaming responses
- OpenAI-compatible request/response transformation

Based on geminicli2api (https://github.com/gzzhongqi/geminicli2api)
"""
import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import Optional, Dict, Any, List, AsyncGenerator

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.api_key import APIKey
from ..config import (
    CODE_ASSIST_ENDPOINT,
    CLOUD_RESOURCE_MANAGER_ENDPOINT,
    SERVICE_USAGE_ENDPOINT,
    SHARED_PROJECT_ID,
    DEFAULT_SAFETY_SETTINGS,
    get_base_model_name,
    is_search_model,
    get_thinking_budget,
    is_thinking_model,
    is_gemini_3_model
)
from ..auth import credentials_to_dict, refresh_credentials_if_needed
from ..helpers import get_user_agent, get_client_metadata

logger = logging.getLogger(__name__)

# Cloud AI Companion API service name for checking if enabled
CLOUD_AI_COMPANION_SERVICE = "cloudaicompanion.googleapis.com"

# Auto-provisioned project name prefix
AUTO_PROJECT_PREFIX = "lg-gemini-proxy"


class GeminiChatService:
    """
    Service class for interacting with the Gemini API.
    
    Handles content generation with automatic credential refresh.
    """
    
    def __init__(
        self,
        credentials: Credentials,
        api_key: APIKey,
        db: AsyncSession
    ):
        """
        Initialize the Gemini chat service.
        
        Args:
            credentials: Google OAuth credentials
            api_key: The API key model (for updating credentials after refresh)
            db: Database session
        """
        self.credentials = credentials
        self.api_key = api_key
        self.db = db
        self.project_id: Optional[str] = None
        self._suggested_project: Optional[str] = None  # For helpful error messages
        self._session_id: str = str(uuid.uuid4())  # Session ID for request tracking (like CLI)
        
        # Extract project_id from credentials if available
        if api_key.gemini_credentials:
            self.project_id = api_key.gemini_credentials.get("project_id")
            logger.info(f"[GEMINI CHAT] Initialized with project_id: {self.project_id}")
            logger.info(f"[GEMINI CHAT] User email: {api_key.gemini_credentials.get('user_email')}")
            logger.info(f"[GEMINI CHAT] Has access_token: {bool(api_key.gemini_credentials.get('access_token'))}")
            logger.info(f"[GEMINI CHAT] Has refresh_token: {bool(api_key.gemini_credentials.get('refresh_token'))}")
    
    async def _ensure_valid_credentials(self) -> bool:
        """
        Ensure credentials are valid, refreshing if necessary.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        if self.credentials.expired and self.credentials.refresh_token:
            try:
                logger.info("Refreshing expired Gemini credentials...")
                self.credentials.refresh(GoogleAuthRequest())
                
                # Update stored credentials
                new_creds = credentials_to_dict(self.credentials)
                if self.project_id:
                    new_creds["project_id"] = self.project_id
                    
                self.api_key.gemini_credentials = new_creds
                self.db.add(self.api_key)
                await self.db.flush()
                
                logger.info("Gemini credentials refreshed and saved")
                return True
                
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                return False
        
        return bool(self.credentials.token)
    
    def _get_headers(self, include_project: bool = True) -> Dict[str, str]:
        """
        Get request headers with current access token.
        
        Args:
            include_project: Whether to include X-Goog-User-Project header
        """
        headers = {
            "Authorization": f"Bearer {self.credentials.token}",
            "Content-Type": "application/json",
            "User-Agent": get_user_agent(),
        }
        
        # Add project header for quota attribution
        if include_project and self.project_id:
            headers["X-Goog-User-Project"] = self.project_id
        
        return headers
    
    async def _discover_project_id(self) -> Optional[str]:
        """
        Discover the user's project ID via multiple fallback methods.
        
        Discovery order:
        1. Return cached project ID if available
        2. Try loadCodeAssist (original geminicli2api approach)
        3. Try to discover user's projects via Cloud Resource Manager
        4. Try to auto-provision a new project with API enabled
        5. Fall back to first user project (with helpful error)
        
        Returns:
            Project ID string
        """
        if self.project_id:
            return self.project_id
        
        if not await self._ensure_valid_credentials():
            logger.warning("Cannot discover project ID: invalid credentials")
            return SHARED_PROJECT_ID
        
        # Method 1: Try loadCodeAssist (original approach)
        project_id = await self._try_load_code_assist()
        if project_id:
            return await self._save_project_id(project_id, "loadCodeAssist")
        
        # Method 2: Try Cloud Resource Manager discovery (finds project with API already enabled)
        project_id = await self._try_discover_from_cloud_resource_manager()
        if project_id:
            # Check if this project has API enabled (it might be first active without API)
            async with httpx.AsyncClient() as client:
                if await self._is_gemini_enabled(client, project_id):
                    return await self._save_project_id(project_id, "Cloud Resource Manager")
        
        # Method 3: Try to auto-provision a project
        provisioned_project = await self._try_auto_provision_project()
        if provisioned_project:
            return await self._save_project_id(provisioned_project, "auto-provisioned")
        
        # Method 4: Use first discovered project (user will need to enable API)
        if project_id:
            logger.warning(f"Using project without API enabled: {project_id}")
            return await self._save_project_id(project_id, "fallback (API not enabled)")
        
        # Method 5: Final fallback to shared project
        logger.info(f"Using shared project ID: {SHARED_PROJECT_ID}")
        self.project_id = SHARED_PROJECT_ID
        return self.project_id
    
    async def _try_load_code_assist(self) -> Optional[str]:
        """Try to get project ID from loadCodeAssist endpoint, with onboarding if needed."""
        try:
            async with httpx.AsyncClient() as client:
                # First try with shared project header
                headers = self._get_headers(include_project=False)
                headers["X-Goog-User-Project"] = SHARED_PROJECT_ID
                
                metadata = get_client_metadata()
                url = f"{CODE_ASSIST_ENDPOINT}/v1internal:loadCodeAssist"
                payload = {"metadata": metadata}
                
                logger.info(f"[LOAD_CODE_ASSIST] ========== loadCodeAssist Request ==========")
                logger.info(f"[LOAD_CODE_ASSIST] URL: {url}")
                logger.info(f"[LOAD_CODE_ASSIST] Headers: {json.dumps({k: v[:20] + '...' if k == 'Authorization' else v for k, v in headers.items()}, indent=2)}")
                logger.info(f"[LOAD_CODE_ASSIST] Payload: {json.dumps(payload, indent=2)}")
                
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                
                logger.info(f"[LOAD_CODE_ASSIST] Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"[LOAD_CODE_ASSIST] Response data: {json.dumps(data, indent=2)}")
                    
                    project_id = data.get("cloudaicompanionProject")
                    current_tier = data.get("currentTier")
                    allowed_tiers = data.get("allowedTiers", [])
                    ineligible_tiers = data.get("ineligibleTiers", [])
                    
                    logger.info(f"[LOAD_CODE_ASSIST] Extracted values:")
                    logger.info(f"[LOAD_CODE_ASSIST]   - cloudaicompanionProject: {project_id}")
                    logger.info(f"[LOAD_CODE_ASSIST]   - currentTier: {current_tier}")
                    logger.info(f"[LOAD_CODE_ASSIST]   - allowedTiers count: {len(allowed_tiers)}")
                    logger.info(f"[LOAD_CODE_ASSIST]   - ineligibleTiers count: {len(ineligible_tiers)}")
                    
                    for tier in allowed_tiers:
                        logger.info(f"[LOAD_CODE_ASSIST]   - Allowed tier: {tier.get('id')} (isDefault={tier.get('isDefault')})")
                    
                    if project_id:
                        logger.info(f"[LOAD_CODE_ASSIST] Got project from loadCodeAssist: {project_id}")
                        return project_id
                    
                    # No project - user needs onboarding
                    if not current_tier:
                        logger.info("[LOAD_CODE_ASSIST] User not onboarded - attempting onboarding...")
                        project_id = await self._try_onboard_user(client, headers, data)
                        if project_id:
                            return project_id
                else:
                    logger.warning(f"[LOAD_CODE_ASSIST] loadCodeAssist returned {response.status_code}")
                    logger.warning(f"[LOAD_CODE_ASSIST] Response body: {response.text[:500]}")
                    
        except Exception as e:
            logger.debug(f"loadCodeAssist failed: {e}")
        
        return None
    
    async def _try_onboard_user(
        self, 
        client: httpx.AsyncClient, 
        headers: Dict[str, str],
        lca_data: Dict[str, Any]
    ) -> Optional[str]:
        """Try to onboard user to Gemini, similar to official CLI."""
        try:
            # Find default tier
            allowed_tiers = lca_data.get("allowedTiers", [])
            tier_id = "free-tier"
            
            for tier in allowed_tiers:
                if tier.get("isDefault"):
                    tier_id = tier.get("id", tier_id)
                    break
            
            if not tier_id and allowed_tiers:
                tier_id = allowed_tiers[0].get("id", tier_id)
            
            logger.info(f"Attempting onboarding with tier: {tier_id}")
            
            onboard_payload = {
                "tierId": tier_id,
                "metadata": get_client_metadata()
            }
            
            # Poll until done
            max_attempts = 6
            for attempt in range(max_attempts):
                response = await client.post(
                    f"{CODE_ASSIST_ENDPOINT}/v1internal:onboardUser",
                    headers=headers,
                    json=onboard_payload,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("done"):
                        logger.info("Onboarding completed!")
                        break
                    else:
                        logger.info(f"Onboarding in progress (attempt {attempt + 1}/{max_attempts})...")
                        await asyncio.sleep(5)
                else:
                    logger.warning(f"Onboarding attempt failed: {response.status_code}")
                    break
            
            # Now try loadCodeAssist again
            await asyncio.sleep(2)
            response = await client.post(
                f"{CODE_ASSIST_ENDPOINT}/v1internal:loadCodeAssist",
                headers=headers,
                json={"metadata": get_client_metadata()},
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                project_id = data.get("cloudaicompanionProject")
                if project_id:
                    logger.info(f"Got project after onboarding: {project_id}")
                    return project_id
                    
        except Exception as e:
            logger.error(f"Onboarding failed: {e}")
        
        return None
    
    async def _verify_and_complete_onboarding(self, client: httpx.AsyncClient) -> bool:
        """
        Verify onboarding is complete and retry if needed.
        Called when we get SERVICE_DISABLED errors - the onboarding might not have fully propagated.
        """
        try:
            headers = self._get_headers(include_project=False)
            headers["X-Goog-User-Project"] = SHARED_PROJECT_ID
            
            # Check current status
            response = await client.post(
                f"{CODE_ASSIST_ENDPOINT}/v1internal:loadCodeAssist",
                headers=headers,
                json={"metadata": get_client_metadata()},
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.warning(f"loadCodeAssist failed: {response.status_code}")
                return False
            
            data = response.json()
            current_tier = data.get("currentTier")
            project_id = data.get("cloudaicompanionProject")
            
            logger.info(f"[SERVER ONBOARDING] Current state - project: {project_id}, tier: {current_tier}")
            
            # If not onboarded, try to onboard
            if not current_tier:
                logger.info("[SERVER ONBOARDING] User not onboarded, attempting onboarding...")
                new_project = await self._try_onboard_user(client, headers, data)
                if new_project:
                    self.project_id = new_project
                    return True
            else:
                # User is onboarded - the 403 might just need time to propagate
                logger.info(f"[SERVER ONBOARDING] User is onboarded to tier: {current_tier.get('id')}")
                
                # Try calling onboardUser anyway - this sometimes "refreshes" the setup
                allowed_tiers = data.get("allowedTiers", [])
                tier_id = current_tier.get("id", "free-tier")
                
                onboard_payload = {
                    "tierId": tier_id,
                    "metadata": get_client_metadata()
                }
                
                try:
                    onboard_response = await client.post(
                        f"{CODE_ASSIST_ENDPOINT}/v1internal:onboardUser",
                        headers=headers,
                        json=onboard_payload,
                        timeout=60.0
                    )
                    
                    if onboard_response.status_code == 200:
                        onboard_data = onboard_response.json()
                        logger.info(f"[SERVER ONBOARDING] Re-onboard response: done={onboard_data.get('done')}")
                except Exception as e:
                    logger.debug(f"Re-onboard attempt: {e}")
                
                return True
                
        except Exception as e:
            logger.error(f"[SERVER ONBOARDING] Error: {e}")
        
        return False
    
    async def _fetch_experiments(self) -> Dict[str, Any]:
        """
        Fetch experiments from the server to check for preview features.
        This mimics what the CLI does before making requests.
        
        Returns:
            Dictionary with experiment flags
        """
        if not self.project_id:
            return {}
        
        try:
            async with httpx.AsyncClient() as client:
                headers = self._get_headers(include_project=False)
                
                # Build request like CLI does
                metadata = get_client_metadata(self.project_id)
                payload = {
                    "project": self.project_id,
                    "metadata": {
                        **metadata,
                        "duetProject": self.project_id,
                    }
                }
                
                url = f"{CODE_ASSIST_ENDPOINT}/v1internal:listExperiments"
                
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    flags = data.get("flags", [])
                    experiment_ids = data.get("experimentIds", [])
                    
                    # Check for ENABLE_PREVIEW flag (ID: 45740196)
                    enable_preview = False
                    for flag in flags:
                        if flag.get("flagId") == 45740196:
                            enable_preview = flag.get("boolValue", False)
                            break
                    
                    return {
                        "flags": flags,
                        "experimentIds": experiment_ids,
                        "enablePreview": enable_preview
                    }
                else:
                    logger.warning(f"[EXPERIMENTS] listExperiments returned {response.status_code}")
                    
        except Exception as e:
            logger.error(f"[EXPERIMENTS] listExperiments failed: {e}")
            import traceback
            logger.error(f"[EXPERIMENTS] Traceback: {traceback.format_exc()}")
        
        return {}
    
    async def _try_discover_from_cloud_resource_manager(self) -> Optional[str]:
        """Try to discover user's project with Gemini enabled via Cloud Resource Manager."""
        try:
            async with httpx.AsyncClient() as client:
                # List user's projects
                response = await client.get(
                    f"{CLOUD_RESOURCE_MANAGER_ENDPOINT}/v1/projects",
                    headers=self._get_headers(include_project=False),
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logger.debug(f"Cloud Resource Manager returned {response.status_code}")
                    return None
                
                projects = response.json().get("projects", [])
                logger.info(f"Found {len(projects)} user projects")
                
                active_projects = []
                
                # Find active projects and check for Cloud AI Companion
                for project in projects:
                    if project.get("lifecycleState") != "ACTIVE":
                        continue
                    
                    project_id = project.get("projectId")
                    active_projects.append(project_id)
                    
                    is_enabled = await self._is_gemini_enabled(client, project_id)
                    logger.debug(f"Project {project_id}: Cloud AI Companion enabled = {is_enabled}")
                    
                    if is_enabled:
                        logger.info(f"Found user project with Gemini enabled: {project_id}")
                        return project_id
                
                # No project has API enabled - use first active project and let user know
                if active_projects:
                    first_project = active_projects[0]
                    logger.warning(
                        f"No projects with Cloud AI Companion API enabled. "
                        f"Using first active project: {first_project}. "
                        f"Enable API at: https://console.cloud.google.com/apis/library/cloudaicompanion.googleapis.com?project={first_project}"
                    )
                    # Store the suggestion for the error message
                    self._suggested_project = first_project
                    return first_project
                
                logger.debug("No active user projects found")
                
        except Exception as e:
            logger.debug(f"Cloud Resource Manager discovery failed: {e}")
        
        return None
    
    async def _is_gemini_enabled(self, client: httpx.AsyncClient, project_id: str) -> bool:
        """Check if Cloud AI Companion API is enabled for a project."""
        try:
            url = f"{SERVICE_USAGE_ENDPOINT}/v1/projects/{project_id}/services/{CLOUD_AI_COMPANION_SERVICE}"
            response = await client.get(
                url,
                headers=self._get_headers(include_project=False),
                timeout=15.0
            )
            
            if response.status_code == 200:
                service = response.json()
                return service.get("state") == "ENABLED"
                
        except Exception as e:
            logger.debug(f"Error checking Gemini status for {project_id}: {e}")
        
        return False
    
    async def _try_auto_provision_project(self) -> Optional[str]:
        """
        Try to auto-provision a Google Cloud project with Gemini API enabled.
        
        Steps:
        1. Check if our auto-provisioned project already exists
        2. If not, create it
        3. Enable Cloud AI Companion API
        
        Returns:
            Project ID if successful, None otherwise
        """
        # Get user email for unique project name
        user_email = None
        if self.api_key.gemini_credentials:
            user_email = self.api_key.gemini_credentials.get("user_email")
        
        if not user_email:
            logger.debug("Cannot auto-provision: no user email available")
            return None
        
        # Create a deterministic project ID from email
        # Project IDs must be 6-30 chars, lowercase, start with letter
        email_hash = hashlib.md5(user_email.encode()).hexdigest()[:8]
        project_id = f"{AUTO_PROJECT_PREFIX}-{email_hash}"
        
        logger.info(f"Attempting to auto-provision project: {project_id}")
        
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Check if project exists
                existing = await self._get_project(client, project_id)
                
                if existing:
                    logger.info(f"Auto-provisioned project already exists: {project_id}")
                    # Check if API is enabled
                    if await self._is_gemini_enabled(client, project_id):
                        return project_id
                    # Try to enable it
                    if await self._enable_gemini_api(client, project_id):
                        return project_id
                    logger.warning(f"Could not enable API on existing project {project_id}")
                    return None
                
                # Step 2: Create the project
                created = await self._create_project(client, project_id, user_email)
                if not created:
                    return None
                
                # Step 3: Wait a bit for project to be ready
                await asyncio.sleep(3)
                
                # Step 4: Enable Cloud AI Companion API
                if await self._enable_gemini_api(client, project_id):
                    logger.info(f"Successfully auto-provisioned project: {project_id}")
                    return project_id
                
                logger.warning(f"Created project {project_id} but could not enable API")
                return None
                
        except Exception as e:
            logger.error(f"Auto-provisioning failed: {e}")
            return None
    
    async def _get_project(self, client: httpx.AsyncClient, project_id: str) -> Optional[dict]:
        """Check if a project exists."""
        try:
            response = await client.get(
                f"{CLOUD_RESOURCE_MANAGER_ENDPOINT}/v1/projects/{project_id}",
                headers=self._get_headers(include_project=False),
                timeout=15.0
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug(f"Error checking project {project_id}: {e}")
        return None
    
    async def _create_project(
        self, 
        client: httpx.AsyncClient, 
        project_id: str, 
        user_email: str
    ) -> bool:
        """Create a new Google Cloud project."""
        try:
            payload = {
                "projectId": project_id,
                "name": f"LinkedIn Gateway Gemini - {user_email.split('@')[0]}"
            }
            
            response = await client.post(
                f"{CLOUD_RESOURCE_MANAGER_ENDPOINT}/v1/projects",
                headers=self._get_headers(include_project=False),
                json=payload,
                timeout=30.0
            )
            
            if response.status_code in (200, 201):
                logger.info(f"Created project: {project_id}")
                return True
            elif response.status_code == 409:
                # Project already exists (race condition)
                logger.info(f"Project already exists: {project_id}")
                return True
            else:
                logger.warning(f"Failed to create project: {response.status_code} - {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return False
    
    async def _enable_gemini_api(self, client: httpx.AsyncClient, project_id: str) -> bool:
        """Enable Cloud AI Companion API for a project."""
        try:
            url = f"{SERVICE_USAGE_ENDPOINT}/v1/projects/{project_id}/services/{CLOUD_AI_COMPANION_SERVICE}:enable"
            
            response = await client.post(
                url,
                headers=self._get_headers(include_project=False),
                json={},
                timeout=60.0
            )
            
            if response.status_code == 200:
                logger.info(f"Enabled Cloud AI Companion API for project: {project_id}")
                # Wait for propagation
                await asyncio.sleep(5)
                return True
            else:
                logger.warning(f"Failed to enable API: {response.status_code} - {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"Error enabling API: {e}")
            return False
    
    async def _save_project_id(self, project_id: str, source: str) -> str:
        """Save discovered project ID to credentials and return it."""
        self.project_id = project_id
        logger.info(f"Discovered project ID via {source}: {project_id}")
        
        try:
            if self.api_key.gemini_credentials:
                creds = self.api_key.gemini_credentials.copy()
                creds["project_id"] = project_id
                self.api_key.gemini_credentials = creds
                self.db.add(self.api_key)
                await self.db.flush()
        except Exception as e:
            logger.warning(f"Failed to save project_id to credentials: {e}")
        
        return project_id
    
    def _build_request_payload(
        self,
        model: str,
        contents: List[Dict[str, Any]],
        system_instruction: Optional[Dict[str, Any]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Build the request payload for Gemini API.
        
        Args:
            model: Model ID (e.g., 'gemini-2.5-pro')
            contents: List of content objects
            system_instruction: Optional system instruction
            generation_config: Optional generation configuration
            tools: Optional list of tools
            
        Returns:
            Request payload dictionary
        """
        logger.info(f"[BUILD_PAYLOAD] Building payload for model: {model}")
        logger.info(f"[BUILD_PAYLOAD] Input model ID: {model}")
        logger.info(f"[BUILD_PAYLOAD] Base model name (after processing): {get_base_model_name(model)}")
        logger.info(f"[BUILD_PAYLOAD] Is thinking model: {is_thinking_model(model)}")
        logger.info(f"[BUILD_PAYLOAD] Is Gemini 3 model: {is_gemini_3_model(model)}")
        logger.info(f"[BUILD_PAYLOAD] Is search model: {is_search_model(model)}")
        
        # Build the request portion
        request_data: Dict[str, Any] = {
            "contents": contents,
            "safetySettings": DEFAULT_SAFETY_SETTINGS,
        }
        
        if system_instruction:
            request_data["systemInstruction"] = system_instruction
        
        # Handle generation config
        gen_config = generation_config or {}
        
        # Add thinking config for thinking-capable models
        if is_thinking_model(model):
            # Check if thinkingConfig is already provided by user (via native API body)
            if "thinkingConfig" in gen_config:
                # Pass through user-provided config exactly as received
                logger.info(f"[BUILD_PAYLOAD] Using user-provided thinkingConfig: {json.dumps(gen_config['thinkingConfig'])}")
            else:
                # Default behavior: 
                # - includeThoughts=False (don't return thoughts in response)
                # - NO thinkingBudget set (let model dynamically decide how much to think)
                # This allows the model to think as needed while keeping response clean
                logger.info(f"[BUILD_PAYLOAD] Applying default thinkingConfig: includeThoughts=False, thinkingBudget=dynamic (not set)")
                gen_config["thinkingConfig"] = {
                    "includeThoughts": False
                    # thinkingBudget intentionally omitted - model decides dynamically
                }
        
        if gen_config:
            request_data["generationConfig"] = gen_config
        
        # Add Google Search tool for search models
        request_tools = tools or []
        if is_search_model(model):
            if not any(tool.get("googleSearch") for tool in request_tools):
                request_tools.append({"googleSearch": {}})
        
        if request_tools:
            request_data["tools"] = request_tools
        
        # Add session_id like the CLI does (optional but might help with session tracking)
        if self._session_id:
            request_data["session_id"] = self._session_id
        
        return {
            "model": get_base_model_name(model),
            "project": self.project_id,
            "user_prompt_id": str(uuid.uuid4()),  # Required by Cloud Code API
            "request": request_data
        }
    
    async def generate_content(
        self,
        model: str,
        contents: List[Dict[str, Any]],
        system_instruction: Optional[Dict[str, Any]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate content using the Gemini API (non-streaming).
        
        Args:
            model: Model ID
            contents: List of content objects
            system_instruction: Optional system instruction
            generation_config: Optional generation configuration
            tools: Optional list of tools
            
        Returns:
            Response from Gemini API
            
        Raises:
            Exception: If API call fails
        """
        if not await self._ensure_valid_credentials():
            raise Exception("Invalid or expired credentials")
        
        # Discover project ID if not set (always succeeds due to fallback)
        if not self.project_id:
            await self._discover_project_id()
        
        # Fetch experiments to check for preview features (like CLI does)
        # This helps ensure the server recognizes our session for preview models
        experiments = await self._fetch_experiments()
        if experiments.get("enablePreview"):
            logger.info(f"[GEMINI CHAT] Preview features enabled for this user")
        
        payload = self._build_request_payload(
            model=model,
            contents=contents,
            system_instruction=system_instruction,
            generation_config=generation_config,
            tools=tools
        )
        
        url = f"{CODE_ASSIST_ENDPOINT}/v1internal:generateContent"
        # IMPORTANT: Do NOT include X-Goog-User-Project header for generateContent
        # The project is specified in the payload body. Including it in header causes
        # 403 SERVICE_DISABLED errors because it tries to bill the user's project
        # which may not have the Cloud Code Private API enabled.
        # The test script (which works) also doesn't include this header.
        headers = self._get_headers(include_project=False)
        
        # ====== COMPREHENSIVE LOGGING: REQUEST TO GEMINI ======
        logger.info(f"[GEMINI->API] ========== REQUEST TO GEMINI API ==========")
        logger.info(f"[GEMINI->API] URL: {url}")
        logger.info(f"[GEMINI->API] Headers: {json.dumps({k: v[:20] + '...' if k == 'Authorization' else v for k, v in headers.items()}, indent=2)}")
        
        # Log full raw payload (this is what we send to Gemini)
        raw_payload_json = json.dumps(payload, indent=2, ensure_ascii=False)
        logger.info(f"[GEMINI->API] RAW PAYLOAD TO GEMINI ({len(raw_payload_json)} chars):")
        # Log in chunks if too long
        if len(raw_payload_json) > 5000:
            logger.info(f"[GEMINI->API] (Payload truncated, showing first 5000 chars)")
            logger.info(f"[GEMINI->API] {raw_payload_json[:5000]}...")
        else:
            logger.info(f"[GEMINI->API] {raw_payload_json}")
        
        # Log summary for quick reference
        request_data = payload.get("request", {})
        logger.info(f"[GEMINI->API] --- Summary ---")
        logger.info(f"[GEMINI->API]   model: {payload.get('model')}")
        logger.info(f"[GEMINI->API]   project: {payload.get('project')}")
        logger.info(f"[GEMINI->API]   contents count: {len(request_data.get('contents', []))}")
        logger.info(f"[GEMINI->API]   has systemInstruction: {bool(request_data.get('systemInstruction'))}")
        logger.info(f"[GEMINI->API]   has generationConfig: {bool(request_data.get('generationConfig'))}")
        if request_data.get('generationConfig'):
            logger.info(f"[GEMINI->API]   generationConfig: {json.dumps(request_data.get('generationConfig'), indent=2)}")
        logger.info(f"[GEMINI->API]   has tools: {bool(request_data.get('tools'))}")
        logger.info(f"[GEMINI->API] ================================================")
        
        # Retry logic for SERVICE_DISABLED errors (API may need time to propagate after onboarding)
        max_retries = 3
        retry_delay = 5  # seconds
        
        try:
            async with httpx.AsyncClient() as client:
                for attempt in range(max_retries):
                    response = await client.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=120.0
                    )
                    
                    # Check if it's a SERVICE_DISABLED error that might resolve with retry
                    if response.status_code == 403:
                        try:
                            error_data = response.json()
                            error_details = error_data.get("error", {}).get("details", [])
                            is_service_disabled = any(
                                d.get("reason") == "SERVICE_DISABLED" 
                                for d in error_details 
                                if d.get("@type", "").endswith("ErrorInfo")
                            )
                            
                            if is_service_disabled and attempt < max_retries - 1:
                                logger.warning(f"[GEMINI CHAT] SERVICE_DISABLED error - API may be propagating. Retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                                
                                # Try to trigger onboarding on the server side
                                if attempt == 0:
                                    logger.info("[GEMINI CHAT] Attempting server-side onboarding verification...")
                                    await self._verify_and_complete_onboarding(client)
                                
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                                continue
                        except Exception:
                            pass
                    
                    break  # Exit retry loop if not a SERVICE_DISABLED error or success
                
                # ====== COMPREHENSIVE LOGGING: RESPONSE FROM GEMINI ======
                logger.info(f"[API->GEMINI] ========== RESPONSE FROM GEMINI API ==========")
                logger.info(f"[API->GEMINI] Status: {response.status_code}")
                logger.info(f"[API->GEMINI] Headers: {json.dumps(dict(response.headers), indent=2)}")
                
                # Get raw response text
                raw_response_text = response.text
                
                if response.status_code != 200:
                    logger.error(f"[API->GEMINI] ERROR - Status {response.status_code}")
                    logger.error(f"[API->GEMINI] RAW ERROR RESPONSE ({len(raw_response_text)} chars):")
                    logger.error(f"[API->GEMINI] {raw_response_text}")
                    
                    # Try to parse error details
                    try:
                        error_json = json.loads(raw_response_text)
                        logger.error(f"[API->GEMINI] Parsed error: {json.dumps(error_json, indent=2)}")
                    except:
                        pass
                    
                    # Build helpful enable URL
                    enable_url = f"https://console.cloud.google.com/apis/library/cloudaicompanion.googleapis.com?project={self.project_id}"
                    
                    # Provide more helpful error message
                    if response.status_code == 400:
                        raise Exception(
                            f"Gemini API rejected the request. "
                            f"Enable 'Gemini for Google Cloud API' at: {enable_url}"
                        )
                    elif response.status_code == 403:
                        raise Exception(
                            f"Permission denied for project '{self.project_id}'. "
                            f"Enable 'Gemini for Google Cloud API' at: {enable_url}"
                        )
                    elif response.status_code == 404:
                        raise Exception(
                            f"Model not found (404). The model '{payload.get('model')}' may not be available for your account. "
                            f"This could mean preview features are not enabled for your account."
                        )
                    else:
                        raise Exception(f"Gemini API error: {response.status_code}")
                
                # Log full raw response from Gemini
                logger.info(f"[API->GEMINI] RAW RESPONSE FROM GEMINI ({len(raw_response_text)} chars):")
                if len(raw_response_text) > 10000:
                    logger.info(f"[API->GEMINI] (Response truncated, showing first 10000 chars)")
                    logger.info(f"[API->GEMINI] {raw_response_text[:10000]}...")
                else:
                    logger.info(f"[API->GEMINI] {raw_response_text}")
                
                # Parse response
                response_text = raw_response_text
                if response_text.startswith("data: "):
                    response_text = response_text[6:]
                
                data = json.loads(response_text)
                
                # Log detailed response analysis
                logger.info(f"[API->GEMINI] --- Response Analysis ---")
                if "response" in data:
                    resp = data["response"]
                    candidates = resp.get("candidates", [])
                    logger.info(f"[API->GEMINI]   candidates count: {len(candidates)}")
                    
                    for c_idx, candidate in enumerate(candidates):
                        content = candidate.get("content", {})
                        parts = content.get("parts", [])
                        logger.info(f"[API->GEMINI]   Candidate {c_idx}: {len(parts)} parts, finishReason={candidate.get('finishReason')}")
                        
                        # Analyze each part
                        for p_idx, part in enumerate(parts):
                            is_thought = part.get("thought", False)
                            text_len = len(part.get("text", "")) if "text" in part else 0
                            logger.info(f"[API->GEMINI]     Part {p_idx}: thought={is_thought}, text_len={text_len}")
                            if text_len > 0 and text_len <= 200:
                                logger.info(f"[API->GEMINI]     Part {p_idx} text: {part.get('text')}")
                            elif text_len > 200:
                                logger.info(f"[API->GEMINI]     Part {p_idx} text preview: {part.get('text')[:200]}...")
                    
                    usage = resp.get("usageMetadata", {})
                    logger.info(f"[API->GEMINI]   usage: promptTokens={usage.get('promptTokenCount')}, candidatesTokens={usage.get('candidatesTokenCount')}, thoughtsTokens={usage.get('thoughtsTokenCount')}")
                else:
                    logger.warning(f"[API->GEMINI]   No 'response' key in data, keys: {list(data.keys())}")
                
                logger.info(f"[API->GEMINI] ================================================")
                
                # Extract the actual response
                return data.get("response", data)
                
        except httpx.TimeoutException:
            raise Exception("Request to Gemini API timed out")
        except Exception as e:
            logger.exception(f"Error calling Gemini API: {e}")
            raise
    
    async def stream_generate_content(
        self,
        model: str,
        contents: List[Dict[str, Any]],
        system_instruction: Optional[Dict[str, Any]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate content using the Gemini API (streaming).
        
        Args:
            model: Model ID
            contents: List of content objects
            system_instruction: Optional system instruction
            generation_config: Optional generation configuration
            tools: Optional list of tools
            
        Yields:
            Response chunks from Gemini API
        """
        if not await self._ensure_valid_credentials():
            raise Exception("Invalid or expired credentials")
        
        # Discover project ID if not set (always succeeds due to fallback)
        if not self.project_id:
            await self._discover_project_id()
        
        payload = self._build_request_payload(
            model=model,
            contents=contents,
            system_instruction=system_instruction,
            generation_config=generation_config,
            tools=tools
        )
        
        url = f"{CODE_ASSIST_ENDPOINT}/v1internal:streamGenerateContent?alt=sse"
        # IMPORTANT: Do NOT include X-Goog-User-Project header - project is in payload
        headers = self._get_headers(include_project=False)
        
        # ====== COMPREHENSIVE LOGGING: STREAMING REQUEST TO GEMINI ======
        logger.info(f"[GEMINI->API] ========== STREAMING REQUEST TO GEMINI API ==========")
        logger.info(f"[GEMINI->API] URL: {url}")
        logger.info(f"[GEMINI->API] Headers: {json.dumps({k: v[:20] + '...' if k == 'Authorization' else v for k, v in headers.items()}, indent=2)}")
        
        # Log full raw payload (this is what we send to Gemini)
        raw_payload_json = json.dumps(payload, indent=2, ensure_ascii=False)
        logger.info(f"[GEMINI->API] RAW PAYLOAD TO GEMINI ({len(raw_payload_json)} chars):")
        if len(raw_payload_json) > 5000:
            logger.info(f"[GEMINI->API] (Payload truncated, showing first 5000 chars)")
            logger.info(f"[GEMINI->API] {raw_payload_json[:5000]}...")
        else:
            logger.info(f"[GEMINI->API] {raw_payload_json}")
        
        logger.info(f"[GEMINI->API] ================================================")
        
        chunk_count = 0
        total_text_len = 0
        total_thought_len = 0
        
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=headers,
                    json=payload,
                    timeout=300.0
                ) as response:
                    logger.info(f"[API->GEMINI] ========== STREAMING RESPONSE FROM GEMINI ==========")
                    logger.info(f"[API->GEMINI] Status: {response.status_code}")
                    
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_str = error_text.decode() if isinstance(error_text, bytes) else str(error_text)
                        logger.error(f"[API->GEMINI] ERROR - Status {response.status_code}")
                        logger.error(f"[API->GEMINI] RAW ERROR: {error_str}")
                        
                        # Build helpful enable URL
                        enable_url = f"https://console.cloud.google.com/apis/library/cloudaicompanion.googleapis.com?project={self.project_id}"
                        
                        # Provide more helpful error message
                        if response.status_code == 400:
                            raise Exception(
                                f"Gemini API rejected the request. "
                                f"Enable 'Gemini for Google Cloud API' at: {enable_url}"
                            )
                        elif response.status_code == 403:
                            raise Exception(
                                f"Permission denied for project '{self.project_id}'. "
                                f"Enable 'Gemini for Google Cloud API' at: {enable_url}"
                            )
                        else:
                            raise Exception(f"Gemini API error: {response.status_code}")
                    
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        raw_line = line
                        if line.startswith("data: "):
                            line = line[6:]
                        
                        try:
                            data = json.loads(line)
                            chunk_count += 1
                            
                            # Extract the actual response chunk
                            chunk = data.get("response", data)
                            
                            # Analyze chunk for logging
                            for candidate in chunk.get("candidates", []):
                                content = candidate.get("content", {})
                                for part in content.get("parts", []):
                                    text = part.get("text", "")
                                    is_thought = part.get("thought", False)
                                    if is_thought:
                                        total_thought_len += len(text)
                                    else:
                                        total_text_len += len(text)
                            
                            # Log every 10th chunk or first 3 chunks
                            if chunk_count <= 3 or chunk_count % 10 == 0:
                                logger.info(f"[API->GEMINI] Chunk #{chunk_count}: {len(raw_line)} chars")
                                if len(raw_line) <= 500:
                                    logger.info(f"[API->GEMINI] Raw chunk: {raw_line}")
                            
                            yield chunk
                                
                        except json.JSONDecodeError:
                            logger.warning(f"[API->GEMINI] Failed to parse chunk: {line[:200]}")
                            continue
                    
                    logger.info(f"[API->GEMINI] --- Stream Complete ---")
                    logger.info(f"[API->GEMINI]   Total chunks: {chunk_count}")
                    logger.info(f"[API->GEMINI]   Total text content: {total_text_len} chars")
                    logger.info(f"[API->GEMINI]   Total thought content: {total_thought_len} chars")
                    logger.info(f"[API->GEMINI] ================================================")
                            
        except httpx.TimeoutException:
            raise Exception("Streaming request to Gemini API timed out")
        except Exception as e:
            logger.exception(f"Error streaming from Gemini API: {e}")
            raise


# ============================================================================
# OpenAI format conversion helpers
# ============================================================================

def convert_openai_messages_to_gemini(messages: List[Dict[str, Any]]) -> tuple:
    """
    Convert OpenAI-format messages to Gemini format.
    
    Args:
        messages: List of OpenAI-format messages
        
    Returns:
        Tuple of (contents, system_instruction)
    """
    contents = []
    system_instruction = None
    
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        if role == "system":
            # System message becomes systemInstruction
            system_instruction = {
                "parts": [{"text": content}]
            }
        else:
            # Map OpenAI roles to Gemini roles
            gemini_role = "model" if role == "assistant" else "user"
            
            # Handle multimodal content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if part.get("type") == "text":
                        parts.append({"text": part.get("text", "")})
                    elif part.get("type") == "image_url":
                        # Handle image content (base64 or URL)
                        image_url = part.get("image_url", {}).get("url", "")
                        if image_url.startswith("data:"):
                            # Base64 image
                            mime_type, base64_data = image_url.split(",", 1)
                            mime_type = mime_type.split(":")[1].split(";")[0]
                            parts.append({
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": base64_data
                                }
                            })
            else:
                parts = [{"text": content}]
            
            contents.append({
                "role": gemini_role,
                "parts": parts
            })
    
    return contents, system_instruction


def convert_gemini_response_to_openai(
    gemini_response: Dict[str, Any],
    model: str,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convert Gemini response to OpenAI format.
    
    Args:
        gemini_response: Response from Gemini API
        model: Model ID used
        request_id: Optional request ID
        
    Returns:
        OpenAI-format response
    """
    request_id = request_id or f"chatcmpl-{uuid.uuid4().hex[:12]}"
    
    choices = []
    
    candidates = gemini_response.get("candidates", [])
    for idx, candidate in enumerate(candidates):
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        
        # Extract text content - separate thinking from actual response
        text_content = ""
        reasoning_content = ""
        
        for part in parts:
            if "text" in part:
                # Check if this is a thinking/reasoning part
                if part.get("thought"):
                    reasoning_content += part["text"]
                    logger.debug(f"[CONVERT] Found thinking part: {len(part['text'])} chars")
                else:
                    text_content += part["text"]
                    logger.debug(f"[CONVERT] Found text part: {len(part['text'])} chars")
        
        logger.info(f"[CONVERT] Candidate {idx}: text={len(text_content)} chars, reasoning={len(reasoning_content)} chars")
        
        # Build message with optional reasoning_content for thinking models
        message: Dict[str, Any] = {
            "role": "assistant",
            "content": text_content
        }
        
        # Include reasoning_content if present (for clients that support it)
        if reasoning_content:
            message["reasoning_content"] = reasoning_content
        
        choices.append({
            "index": idx,
            "message": message,
            "finish_reason": _map_finish_reason(candidate.get("finishReason"))
        })
    
    # Extract usage info
    usage_metadata = gemini_response.get("usageMetadata", {})
    usage = {
        "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
        "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
        "total_tokens": usage_metadata.get("totalTokenCount", 0)
    }
    
    return {
        "id": request_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": choices,
        "usage": usage
    }


def convert_gemini_chunk_to_openai(
    gemini_chunk: Dict[str, Any],
    model: str,
    request_id: str,
    chunk_index: int = 0
) -> Dict[str, Any]:
    """
    Convert a Gemini streaming chunk to OpenAI format.
    
    Args:
        gemini_chunk: Streaming chunk from Gemini
        model: Model ID
        request_id: Request ID
        chunk_index: Index of the chunk
        
    Returns:
        OpenAI-format streaming chunk
    """
    candidates = gemini_chunk.get("candidates", [])
    
    choices = []
    for idx, candidate in enumerate(candidates):
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        
        # Extract text delta
        text_delta = ""
        reasoning_delta = None
        
        for part in parts:
            if "text" in part:
                # Check if this is reasoning/thinking content
                if part.get("thought"):
                    reasoning_delta = part["text"]
                else:
                    text_delta += part["text"]
        
        delta: Dict[str, Any] = {}
        if chunk_index == 0:
            delta["role"] = "assistant"
        if text_delta:
            delta["content"] = text_delta
        if reasoning_delta:
            delta["reasoning_content"] = reasoning_delta
        
        choices.append({
            "index": idx,
            "delta": delta,
            "finish_reason": _map_finish_reason(candidate.get("finishReason"))
        })
    
    return {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": choices
    }


def _map_finish_reason(gemini_reason: Optional[str]) -> Optional[str]:
    """Map Gemini finish reason to OpenAI format."""
    if not gemini_reason:
        return None
    
    mapping = {
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
        "OTHER": "stop",
    }
    
    return mapping.get(gemini_reason, "stop")

