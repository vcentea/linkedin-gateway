"""
Configuration constants for Gemini AI integration.

Based on geminicli2api (https://github.com/gzzhongqi/geminicli2api)
These are the public Gemini CLI OAuth credentials that anyone can use
to authenticate with their personal Google account.
"""
import os
from typing import List, Dict, Any

# API Endpoints
CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com"
CLOUD_RESOURCE_MANAGER_ENDPOINT = "https://cloudresourcemanager.googleapis.com"
SERVICE_USAGE_ENDPOINT = "https://serviceusage.googleapis.com"

# Shared Project Configuration
# This is the fallback project ID used when user's project can't be discovered
# Users still use their own OAuth tokens, so quotas come from their account
SHARED_PROJECT_ID = os.environ.get("GEMINI_SHARED_PROJECT_ID", "linkedin-gateway")

# Client Configuration - Public Gemini CLI credentials
CLI_VERSION = "0.20.0"  # Match current gemini-cli version

# OAuth Configuration - PUBLIC credentials from Gemini CLI
# These are INTENTIONALLY PUBLIC - from https://github.com/gzzhongqi/geminicli2api
# Desktop OAuth apps require embedded credentials (Google's design)
# Users authenticate with their OWN Google account using these app credentials
# This ensures users get their own quota, not tied to our project
# nosec: B105 - These are intentionally public OAuth client credentials
GEMINI_CLIENT_ID = os.environ.get(
    "GEMINI_CLIENT_ID",
    "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"  # gitleaks:allow
)
GEMINI_CLIENT_SECRET = os.environ.get(
    "GEMINI_CLIENT_SECRET",
    "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"  # gitleaks:allow - Public Gemini CLI credential
)

# OAuth Scopes required for Gemini API access
GEMINI_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]

# Token endpoint for OAuth 2.0
TOKEN_URI = "https://oauth2.googleapis.com/token"

# Default Safety Settings for Gemini API (allow all content)
DEFAULT_SAFETY_SETTINGS: List[Dict[str, str]] = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
]

# Supported Gemini Models
SUPPORTED_MODELS: List[Dict[str, Any]] = [
    {
        "id": "gemini-2.5-pro",
        "name": "models/gemini-2.5-pro",
        "display_name": "Gemini 2.5 Pro",
        "description": "Advanced multimodal model with enhanced capabilities",
        "input_token_limit": 1048576,
        "output_token_limit": 65535,
    },
    {
        "id": "gemini-2.5-flash",
        "name": "models/gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "description": "Fast and efficient multimodal model",
        "input_token_limit": 1048576,
        "output_token_limit": 65535,
    },
    {
        "id": "gemini-2.5-pro-search",
        "name": "models/gemini-2.5-pro",
        "display_name": "Gemini 2.5 Pro with Google Search",
        "description": "Gemini 2.5 Pro with Google Search grounding enabled",
        "input_token_limit": 1048576,
        "output_token_limit": 65535,
        "features": ["google_search"],
    },
    {
        "id": "gemini-2.5-flash-search",
        "name": "models/gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash with Google Search",
        "description": "Gemini 2.5 Flash with Google Search grounding enabled",
        "input_token_limit": 1048576,
        "output_token_limit": 65535,
        "features": ["google_search"],
    },
    {
        "id": "gemini-2.5-flash-lite",
        "name": "models/gemini-2.5-flash-lite",
        "display_name": "Gemini 2.5 Flash Lite",
        "description": "Lightweight fast model for simple tasks",
        "input_token_limit": 1048576,
        "output_token_limit": 65535,
    },
    {
        "id": "gemini-2.0-flash",
        "name": "models/gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "description": "Previous generation fast model",
        "input_token_limit": 1048576,
        "output_token_limit": 8192,
    },
    {
        "id": "gemini-2.0-flash-preview-image-generation",
        "name": "models/gemini-2.0-flash-preview-image-generation",
        "display_name": "Gemini 2.0 Flash Preview Image Generation",
        "description": "Multimodal model with image generation capabilities",
        "input_token_limit": 1048576,
        "output_token_limit": 8192,
    },
    {
        "id": "gemini-3-pro-preview",
        "name": "models/gemini-3-pro-preview",
        "display_name": "Gemini 3 Pro Preview",
        "description": "Next-generation multimodal model with advanced reasoning capabilities",
        "input_token_limit": 1048576,
        "output_token_limit": 65536,
    },
    # Note: gemini-1.5-* models return 404 via Cloud Code API - not supported
]


def get_model_config(model_id: str) -> Dict[str, Any]:
    """
    Get configuration for a specific model.
    
    Args:
        model_id: Model identifier (e.g., 'gemini-2.5-pro')
        
    Returns:
        Model configuration dict or default config if not found
    """
    for model in SUPPORTED_MODELS:
        if model["id"] == model_id:
            return model
    
    # Default config for unknown models
    return {
        "id": model_id,
        "name": f"models/{model_id}",
        "display_name": model_id,
        "description": "Unknown model",
        "input_token_limit": 1048576,
        "output_token_limit": 65535,
    }


def get_base_model_name(model_id: str) -> str:
    """
    Get the base model name from a model ID.
    Removes suffixes like -search, -nothinking, -maxthinking.
    
    The Cloud Code API expects just the model name without 'models/' prefix
    (e.g., 'gemini-2.5-flash').
    
    Args:
        model_id: Model identifier (e.g., 'gemini-2.5-pro-search')
        
    Returns:
        Base model name (e.g., 'gemini-2.5-pro')
    """
    suffixes = ["-maxthinking", "-nothinking", "-search"]
    base_id = model_id
    
    # Remove models/ prefix if present
    if base_id.startswith("models/"):
        base_id = base_id[7:]
    
    # Remove suffixes
    for suffix in suffixes:
        if base_id.endswith(suffix):
            base_id = base_id[:-len(suffix)]
    
    return base_id


def is_search_model(model_id: str) -> bool:
    """Check if model should use Google Search grounding."""
    return "-search" in model_id


def is_thinking_model(model_id: str) -> bool:
    """Check if model supports thinking/reasoning."""
    return "gemini-2.5" in model_id or "gemini-3" in model_id


def is_gemini_3_model(model_id: str) -> bool:
    """Check if model is a Gemini 3 model (uses thinkingLevel instead of thinkingBudget)."""
    return "gemini-3" in model_id


def get_thinking_budget(model_id: str) -> int:
    """
    Get the thinking budget for a model.
    
    Returns:
        -1 for default, 0 for no thinking, positive number for specific budget
    """
    if "-nothinking" in model_id:
        return 0 if "flash" in model_id else 128
    elif "-maxthinking" in model_id:
        return 24576 if "flash" in model_id else 32768
    return -1  # Default

