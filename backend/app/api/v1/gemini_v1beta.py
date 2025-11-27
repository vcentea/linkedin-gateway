"""
[Gemini] Native v1beta API endpoints.

These endpoints return supported Gemini models in Google's native format
for compatibility with tools like n8n, LangChain, and other Gemini API clients.

Authentication: Via `key` query parameter (Google-style) or headers.
"""
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.api_key import APIKey
from app.auth.dependencies import (
    validate_gemini_api_key,
    gemini_api_key_header_scheme,
    api_key_header_scheme
)
from app.gemini.services.chat import GeminiChatService
from app.gemini.auth import load_credentials_from_dict

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/gemini/v1beta",
    tags=["gemini-v1beta"],
)

# Supported models in Google's native format (names without models/ prefix per CLI standard)
SUPPORTED_MODELS_NATIVE = [
    {
        "name": "gemini-2.5-flash",
        "version": "2.5",
        "displayName": "Gemini 2.5 Flash",
        "description": "Fast and efficient multimodal model optimized for speed",
        "inputTokenLimit": 1048576,
        "outputTokenLimit": 65536,
        "supportedGenerationMethods": ["generateContent", "countTokens"],
        "temperature": 1.0,
        "maxTemperature": 2.0,
        "topP": 0.95,
        "topK": 40
    },
    {
        "name": "gemini-2.5-pro",
        "version": "2.5",
        "displayName": "Gemini 2.5 Pro",
        "description": "Advanced multimodal model with enhanced capabilities",
        "inputTokenLimit": 1048576,
        "outputTokenLimit": 65536,
        "supportedGenerationMethods": ["generateContent", "countTokens"],
        "temperature": 1.0,
        "maxTemperature": 2.0,
        "topP": 0.95,
        "topK": 40
    },
    {
        "name": "gemini-2.0-flash-preview-image-generation",
        "version": "2.0",
        "displayName": "Gemini 2.0 Flash Preview Image Generation",
        "description": "Multimodal model with image generation capabilities",
        "inputTokenLimit": 1048576,
        "outputTokenLimit": 8192,
        "supportedGenerationMethods": ["generateContent", "countTokens"],
        "temperature": 1.0,
        "maxTemperature": 2.0,
        "topP": 0.95,
        "topK": 40
    },
    {
        "name": "gemini-3-pro-preview",
        "version": "3.0",
        "displayName": "Gemini 3 Pro Preview",
        "description": "Next-generation multimodal model with advanced reasoning capabilities",
        "inputTokenLimit": 1048576,
        "outputTokenLimit": 65536,
        "supportedGenerationMethods": ["generateContent", "countTokens"],
        "temperature": 1.0,
        "maxTemperature": 2.0,
        "topP": 0.95,
        "topK": 40
    },
]


async def _get_api_key_from_query_or_header(
    key: Optional[str] = Query(None, description="Optional. Copy of the API key sent in the header (Google-style)."),
    api_key: Optional[str] = Query(None, description="Optional. Alternative query param name for API key."),
    gemini_api_key_header: Optional[str] = Depends(gemini_api_key_header_scheme),
    standard_api_key_header: Optional[str] = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db)
) -> APIKey:
    """
    Dependency that extracts API key from query param or headers.
    
    Accepts (in order of precedence):
    1. `key` query parameter (Google-style)
    2. `api_key` query parameter (alternative)
    3. x-goog-api-key header
    4. X-API-Key header
    """
    # Use key first, then api_key as fallback for query params
    query_param_key = key or api_key
    
    return await validate_gemini_api_key(
        api_key_from_body=query_param_key,
        gemini_api_key_header=gemini_api_key_header,
        standard_api_key_header=standard_api_key_header,
        db=db
    )


@router.get("/models", summary="[Gemini] List v1beta Models")
async def list_models(
    key: Optional[str] = Query(None, include_in_schema=False),
    api_key_param: Optional[str] = Query(None, alias="api_key", include_in_schema=False),
    gemini_api_key_header: Optional[str] = Depends(gemini_api_key_header_scheme),
    standard_api_key_header: Optional[str] = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns supported Gemini models (gemini-2.5-flash, gemini-2.5-pro)
    in Google's native format for compatibility with n8n and other tools.
    
    **Authentication:**
    - Via `key` query parameter (Google-style, for n8n compatibility)
    - Via `x-goog-api-key` header (Google-style)
    - Via `X-API-Key` header
    
    **Response:**
    ```json
    {
        "models": [
            {
                "name": "gemini-2.5-flash",
                "displayName": "Gemini 2.5 Flash",
                ...
            }
        ]
    }
    ```
    """
    # Accept key from query param (for n8n) or headers
    query_key = key or api_key_param
    
    api_key = await validate_gemini_api_key(
        api_key_from_body=query_key,
        gemini_api_key_header=gemini_api_key_header,
        standard_api_key_header=standard_api_key_header,
        db=db
    )
    
    logger.info(f"[GEMINI v1beta] Models list request from API key: {api_key.prefix}")
    
    return {"models": SUPPORTED_MODELS_NATIVE}


# @router.get("/models/{model_name:path}", summary="[Gemini] Get v1beta Model Details")
# async def get_model(
#     model_name: str,
#     db: AsyncSession = Depends(get_db),
#     api_key: APIKey = Depends(_get_api_key_from_query_or_header)
# ):
#     """
#     Get details for a specific Gemini model.
#     
#     **Path Parameter:**
#     - `model_name`: Model name (e.g., "gemini-2.5-flash")
#     
#     **Authentication:**
#     - Via `key` query parameter (Google-style)
#     - Via `x-goog-api-key` header
#     - Via `X-API-Key` header
#     """
#     logger.info(f"[GEMINI v1beta] Model details request for: {model_name}")
#     
#     # Normalize model name (remove models/ prefix if present)
#     search_name = model_name
#     if search_name.startswith("models/"):
#         search_name = search_name[7:]
#     
#     # Find the model
#     for model in SUPPORTED_MODELS_NATIVE:
#         if model["name"] == search_name:
#             return model
#     
#     # Model not found
#     raise HTTPException(
#         status_code=status.HTTP_404_NOT_FOUND,
#         detail=f"Model '{model_name}' not found. Supported models: gemini-2.5-flash, gemini-2.5-pro"
#     )


def _extract_model_from_path(model_path: str) -> str:
    """Extract clean model name from path like 'gemini-2.5-flash:generateContent'."""
    # Remove :generateContent or :streamGenerateContent suffix
    model_name = model_path.split(":")[0]
    # Remove models/ prefix if present
    if model_name.startswith("models/"):
        model_name = model_name[7:]
    return model_name


@router.post("/models/{model_path}:generateContent", summary="[Gemini] Generate Content")
async def generate_content(
    model_path: str,
    request: Request,
    key: Optional[str] = Query(None, description="API key (Google-style query param)"),
    gemini_api_key_header: Optional[str] = Depends(gemini_api_key_header_scheme),
    standard_api_key_header: Optional[str] = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate content using a Gemini model (Google's native API format).
    
    This endpoint is 100% compatible with Google's Gemini API format.
    
    **Path:** `/v1beta/models/{model}:generateContent`
    
    **Authentication (in order of precedence):**
    - Via `x-goog-api-key` header (Google-style, recommended)
    - Via `X-API-Key` header (LinkedIn Gateway style)
    - Via `key` query parameter (Google-style): `?key=your_api_key`
    
    **Request Body (Google native format):**
    ```json
    {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Hello, how are you?"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024
        },
        "systemInstruction": {
            "parts": [{"text": "You are a helpful assistant."}]
        }
    }
    ```
    """
    model_name = _extract_model_from_path(model_path)
    logger.info(f"[GEMINI v1beta] generateContent request for model: {model_name}")
    
    # Parse request body first to extract potential api_key
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON body: {str(e)}"
        )
    
    # Extract api_key from body if present (for compatibility)
    api_key_from_body = body.get("api_key") or body.get("key")
    
    # Use query param first, then body
    api_key_value = key or api_key_from_body
    
    # Validate API key from headers or body/query param
    api_key = await validate_gemini_api_key(
        api_key_from_body=api_key_value,
        gemini_api_key_header=gemini_api_key_header,
        standard_api_key_header=standard_api_key_header,
        db=db
    )
    
    # Check credentials
    if not api_key.gemini_credentials:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Gemini credentials not configured. Please connect your Google account."
        )
    
    credentials = load_credentials_from_dict(api_key.gemini_credentials)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load Gemini credentials"
        )
    
    # Extract parameters in Google's native format
    contents = body.get("contents", [])
    generation_config = body.get("generationConfig", {})
    system_instruction = body.get("systemInstruction")
    safety_settings = body.get("safetySettings")
    tools = body.get("tools")
    
    # Initialize service and generate
    service = GeminiChatService(credentials, api_key, db)
    
    try:
        response = await service.generate_content(
            model=model_name,
            contents=contents,
            system_instruction=system_instruction,
            generation_config=generation_config,
            tools=tools
        )
        return response
    except Exception as e:
        logger.error(f"[GEMINI v1beta] generateContent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}"
        )


@router.post("/models/{model_path}:streamGenerateContent", summary="[Gemini] Stream Generate Content")
async def stream_generate_content(
    model_path: str,
    request: Request,
    key: Optional[str] = Query(None, description="API key (Google-style query param)"),
    gemini_api_key_header: Optional[str] = Depends(gemini_api_key_header_scheme),
    standard_api_key_header: Optional[str] = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    Stream generate content using a Gemini model (Google's native API format).
    
    This endpoint is 100% compatible with Google's Gemini API format.
    
    **Path:** `/v1beta/models/{model}:streamGenerateContent`
    
    **Authentication (in order of precedence):**
    - Via `x-goog-api-key` header (Google-style, recommended)
    - Via `X-API-Key` header (LinkedIn Gateway style)
    - Via `key` query parameter (Google-style): `?key=your_api_key`
    
    **Request Body:** Same as generateContent
    
    **Response:** Server-sent events stream
    """
    model_name = _extract_model_from_path(model_path)
    logger.info(f"[GEMINI v1beta] streamGenerateContent request for model: {model_name}")
    
    # Parse request body first to extract potential api_key
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON body: {str(e)}"
        )
    
    # Extract api_key from body if present (for compatibility)
    api_key_from_body = body.get("api_key") or body.get("key")
    
    # Use query param first, then body
    api_key_value = key or api_key_from_body
    
    # Validate API key from headers or body/query param
    api_key = await validate_gemini_api_key(
        api_key_from_body=api_key_value,
        gemini_api_key_header=gemini_api_key_header,
        standard_api_key_header=standard_api_key_header,
        db=db
    )
    
    # Check credentials
    if not api_key.gemini_credentials:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Gemini credentials not configured. Please connect your Google account."
        )
    
    credentials = load_credentials_from_dict(api_key.gemini_credentials)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load Gemini credentials"
        )
    
    # Extract parameters in Google's native format
    contents = body.get("contents", [])
    generation_config = body.get("generationConfig", {})
    system_instruction = body.get("systemInstruction")
    tools = body.get("tools")
    
    # Initialize service
    service = GeminiChatService(credentials, api_key, db)
    
    async def generate_stream():
        try:
            async for chunk in service.stream_generate_content(
                model=model_name,
                contents=contents,
                system_instruction=system_instruction,
                generation_config=generation_config,
                tools=tools
            ):
                chunk_json = json.dumps(chunk) if isinstance(chunk, dict) else str(chunk)
                yield f"data: {chunk_json}\n\n"
        except Exception as e:
            logger.error(f"[GEMINI v1beta] streamGenerateContent error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )


@router.post("/web-search", summary="[Gemini] Web Search")
async def web_search(
    request: Request,
    gemini_api_key_header: Optional[str] = Depends(gemini_api_key_header_scheme),
    standard_api_key_header: Optional[str] = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    [Gemini] Perform a web search using Google Search grounding.
    
    This endpoint simplifies web search by handling the tool configuration internally.
    Just provide a query and optionally a model.
    
    Request body:
    - query (required): The search query
    - model (optional): Model to use (default: gemini-2.5-flash)
    
    Response includes:
    - answer: The generated response text
    - sources: Array of sources with uri and title
    - groundingMetadata: Full grounding metadata from the API
    """
    logger.info("[GEMINI v1beta] web-search request received")
    
    # Parse request body
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON body: {str(e)}"
        )
    
    # Extract parameters
    query = body.get("query")
    if not query or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'query' is required and cannot be empty"
        )
    
    model = body.get("model", "gemini-2.5-flash")
    
    # Validate API key (from headers only - same as other Gemini endpoints)
    api_key = await validate_gemini_api_key(
        api_key_from_body=None,
        gemini_api_key_header=gemini_api_key_header,
        standard_api_key_header=standard_api_key_header,
        db=db
    )
    
    # Load credentials
    if not api_key.gemini_credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Gemini credentials found. Please connect your Google account first."
        )
    
    credentials = load_credentials_from_dict(api_key.gemini_credentials)
    
    # Build the request with googleSearch tool
    contents = [
        {
            "role": "user",
            "parts": [{"text": query}]
        }
    ]
    
    tools = [{"googleSearch": {}}]
    
    generation_config = {
        "temperature": 0.7,
        "maxOutputTokens": 2048
    }
    
    # Initialize service and generate
    service = GeminiChatService(credentials, api_key, db)
    
    try:
        response = await service.generate_content(
            model=model,
            contents=contents,
            generation_config=generation_config,
            tools=tools
        )
        
        # Extract the answer text
        answer = ""
        candidates = response.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                if "text" in part:
                    answer += part["text"]
        
        # Extract sources from grounding metadata
        sources = []
        grounding_metadata = candidates[0].get("groundingMetadata", {}) if candidates else {}
        grounding_chunks = grounding_metadata.get("groundingChunks", [])
        
        for chunk in grounding_chunks:
            web = chunk.get("web", {})
            if web:
                sources.append({
                    "uri": web.get("uri", ""),
                    "title": web.get("title", "")
                })
        
        return {
            "query": query,
            "model": model,
            "answer": answer,
            "sources": sources,
            "groundingMetadata": grounding_metadata
        }
        
    except Exception as e:
        logger.error(f"[GEMINI v1beta] web-search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Web search failed: {str(e)}"
        )

