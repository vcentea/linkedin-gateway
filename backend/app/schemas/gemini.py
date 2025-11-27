"""
Pydantic schemas for Gemini AI integration.

Includes:
- OAuth credential schemas for storing/updating Google credentials
- OpenAI-compatible chat completion schemas
- Native Gemini API schemas
"""
import json
from typing import Optional, Dict, List, Any, Union, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime


# ============================================================================
# Gemini OAuth Credentials Schemas
# ============================================================================

class GeminiCredentials(BaseModel):
    """
    Google OAuth 2.0 credentials for Gemini API access.
    Based on the format used by geminicli2api and Gemini CLI.
    """
    client_id: str = Field(..., description="Google OAuth client ID")
    client_secret: str = Field(..., description="Google OAuth client secret")
    token: Optional[str] = Field(None, description="Current access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token for obtaining new access tokens")
    scopes: List[str] = Field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ],
        description="OAuth scopes"
    )
    token_uri: str = Field(
        default="https://oauth2.googleapis.com/token",
        description="Token exchange endpoint"
    )
    expiry: Optional[str] = Field(None, description="Token expiry timestamp (ISO format)")
    project_id: Optional[str] = Field(None, description="Google Cloud project ID (optional)")


class GeminiCredentialsUpdate(BaseModel):
    """Schema for updating Gemini credentials via PATCH endpoint."""
    gemini_credentials: Dict[str, Any] = Field(
        ...,
        description="Gemini OAuth credentials object"
    )


# ============================================================================
# OpenAI-Compatible Chat Completion Schemas
# ============================================================================

class ChatMessage(BaseModel):
    """OpenAI-compatible chat message."""
    role: Literal["system", "user", "assistant"] = Field(..., description="Message role")
    content: Union[str, List[Dict[str, Any]]] = Field(..., description="Message content (text or multimodal)")


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""
    model: str = Field(..., description="Model to use (e.g., 'gemini-2.5-pro', 'gemini-2.5-flash')")
    messages: List[ChatMessage] = Field(..., description="List of messages in the conversation")
    temperature: Optional[float] = Field(1.0, ge=0, le=2, description="Sampling temperature")
    top_p: Optional[float] = Field(0.95, ge=0, le=1, description="Nucleus sampling parameter")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")
    stream: Optional[bool] = Field(False, description="Whether to stream the response")
    stop: Optional[Union[str, List[str]]] = Field(None, description="Stop sequences")
    # API key can be provided in body or header
    api_key: Optional[str] = Field(None, description="API key (alternative to X-API-Key header)")
    
    @field_validator('messages', mode='before')
    @classmethod
    def parse_messages_string(cls, v):
        """Parse messages if provided as a JSON string (from API tester)."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v.strip())
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return v
    
    @field_validator('temperature', 'top_p', mode='before')
    @classmethod
    def parse_float_string(cls, v):
        """Parse float values if provided as strings."""
        if isinstance(v, str):
            try:
                return float(v.strip())
            except ValueError:
                pass
        return v
    
    @field_validator('max_tokens', mode='before')
    @classmethod
    def parse_int_string(cls, v):
        """Parse int values if provided as strings."""
        if v is None or v == '':
            return None
        if isinstance(v, str):
            try:
                return int(v.strip())
            except ValueError:
                pass
        return v
    
    @field_validator('stream', mode='before')
    @classmethod
    def parse_bool_string(cls, v):
        """Parse boolean values if provided as strings."""
        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in ('true', '1', 'yes'):
                return True
            elif v_lower in ('false', '0', 'no', ''):
                return False
        return v


class ChatCompletionChoice(BaseModel):
    """OpenAI-compatible chat completion choice."""
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionUsage(BaseModel):
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""
    id: str = Field(..., description="Unique response ID")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model used")
    choices: List[ChatCompletionChoice] = Field(..., description="Generated completions")
    usage: Optional[ChatCompletionUsage] = None


class ChatCompletionChunkDelta(BaseModel):
    """Delta content for streaming responses."""
    role: Optional[str] = None
    content: Optional[str] = None
    reasoning_content: Optional[str] = Field(None, description="Reasoning/thinking content (for thinking models)")


class ChatCompletionChunkChoice(BaseModel):
    """Choice in a streaming chunk."""
    index: int
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """Streaming chunk for chat completions."""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionChunkChoice]


# ============================================================================
# OpenAI-Compatible Models Schemas
# ============================================================================

class ModelInfo(BaseModel):
    """OpenAI-compatible model information."""
    id: str = Field(..., description="Model ID")
    object: str = Field(default="model", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    owned_by: str = Field(default="google", description="Model owner")


class ModelsListResponse(BaseModel):
    """OpenAI-compatible models list response."""
    object: str = Field(default="list", description="Object type")
    data: List[ModelInfo] = Field(..., description="List of available models")


# ============================================================================
# Native Gemini API Schemas
# ============================================================================

class GeminiPart(BaseModel):
    """Content part for Gemini API."""
    text: Optional[str] = None
    inline_data: Optional[Dict[str, Any]] = Field(None, alias="inlineData")


class GeminiContent(BaseModel):
    """Content object for Gemini API."""
    role: Optional[str] = None
    parts: List[GeminiPart]


class GeminiSafetySettings(BaseModel):
    """Safety settings for Gemini API."""
    category: str
    threshold: str = "BLOCK_NONE"


class GeminiThinkingConfig(BaseModel):
    """Thinking configuration for Gemini 2.5 models."""
    thinking_budget: Optional[int] = Field(None, alias="thinkingBudget")
    include_thoughts: Optional[bool] = Field(True, alias="includeThoughts")


class GeminiGenerationConfig(BaseModel):
    """Generation configuration for Gemini API."""
    temperature: Optional[float] = None
    top_p: Optional[float] = Field(None, alias="topP")
    top_k: Optional[int] = Field(None, alias="topK")
    max_output_tokens: Optional[int] = Field(None, alias="maxOutputTokens")
    stop_sequences: Optional[List[str]] = Field(None, alias="stopSequences")
    thinking_config: Optional[GeminiThinkingConfig] = Field(None, alias="thinkingConfig")


class GeminiGenerateContentRequest(BaseModel):
    """Native Gemini generateContent request."""
    contents: List[GeminiContent] = Field(..., description="Conversation contents")
    system_instruction: Optional[GeminiContent] = Field(None, alias="systemInstruction")
    generation_config: Optional[GeminiGenerationConfig] = Field(None, alias="generationConfig")
    safety_settings: Optional[List[GeminiSafetySettings]] = Field(None, alias="safetySettings")
    tools: Optional[List[Dict[str, Any]]] = None
    # API key can be provided in body or header
    api_key: Optional[str] = Field(None, description="API key (alternative to X-API-Key header)")


class GeminiCandidate(BaseModel):
    """Response candidate from Gemini."""
    content: GeminiContent
    finish_reason: Optional[str] = Field(None, alias="finishReason")
    safety_ratings: Optional[List[Dict[str, Any]]] = Field(None, alias="safetyRatings")


class GeminiUsageMetadata(BaseModel):
    """Usage metadata from Gemini."""
    prompt_token_count: Optional[int] = Field(None, alias="promptTokenCount")
    candidates_token_count: Optional[int] = Field(None, alias="candidatesTokenCount")
    total_token_count: Optional[int] = Field(None, alias="totalTokenCount")


class GeminiGenerateContentResponse(BaseModel):
    """Native Gemini generateContent response."""
    candidates: List[GeminiCandidate]
    usage_metadata: Optional[GeminiUsageMetadata] = Field(None, alias="usageMetadata")
    model_version: Optional[str] = Field(None, alias="modelVersion")


# ============================================================================
# Native Gemini Models Schemas
# ============================================================================

class GeminiModelInfo(BaseModel):
    """Native Gemini model information."""
    name: str
    version: Optional[str] = None
    display_name: Optional[str] = Field(None, alias="displayName")
    description: Optional[str] = None
    input_token_limit: Optional[int] = Field(None, alias="inputTokenLimit")
    output_token_limit: Optional[int] = Field(None, alias="outputTokenLimit")
    supported_generation_methods: Optional[List[str]] = Field(None, alias="supportedGenerationMethods")


class GeminiModelsListResponse(BaseModel):
    """Native Gemini models list response."""
    models: List[GeminiModelInfo]

