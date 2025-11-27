"""
Native Gemini API endpoints.

These endpoints mirror Google's Gemini API format for direct compatibility
with applications designed for the native Gemini API.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.api_key import APIKey
from app.auth.dependencies import validate_api_key_from_header_or_body, api_key_header_scheme
from app.schemas.gemini import (
    GeminiGenerateContentRequest,
    GeminiGenerateContentResponse,
    GeminiModelsListResponse,
    GeminiModelInfo
)
from app.gemini.services.chat import GeminiChatService
from app.gemini.auth import load_credentials_from_dict
from app.gemini.config import SUPPORTED_MODELS

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/gemini",
    tags=["gemini-native"],
)


async def _get_api_key_with_body(
    request: GeminiGenerateContentRequest,
    api_key_header: Optional[str] = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db)
) -> APIKey:
    """Dependency that extracts API key from header or request body."""
    return await validate_api_key_from_header_or_body(
        api_key_from_body=request.api_key,
        api_key_header=api_key_header,
        db=db
    )


@router.get("/models", response_model=GeminiModelsListResponse)
async def list_gemini_models(
    api_key_header: Optional[str] = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    List available Gemini models in native format.
    
    **Authentication:**
    - Via `X-API-Key` header
    - Via `x-goog-api-key` header (Google-style)
    
    **Response:**
    Native Gemini format:
    ```json
    {
        "models": [
            {
                "name": "models/gemini-2.5-pro",
                "displayName": "Gemini 2.5 Pro",
                "description": "...",
                "inputTokenLimit": 1048576,
                "outputTokenLimit": 65535
            }
        ]
    }
    ```
    """
    # Validate API key from header only for GET request
    api_key = await validate_api_key_from_header_or_body(
        api_key_from_body=None,
        api_key_header=api_key_header,
        db=db
    )
    
    logger.info(f"[GEMINI] Native models list from API key: {api_key.prefix}")
    
    models_list = []
    for model in SUPPORTED_MODELS:
        models_list.append(GeminiModelInfo(
            name=model["name"],
            display_name=model.get("display_name", model["id"]),
            description=model.get("description", ""),
            input_token_limit=model.get("input_token_limit", 1048576),
            output_token_limit=model.get("output_token_limit", 65535),
            supported_generation_methods=["generateContent", "streamGenerateContent"]
        ))
    
    return GeminiModelsListResponse(models=models_list)


# @router.post("/models/{model_name}:generateContent", response_model=GeminiGenerateContentResponse)
# async def generate_content(
#     model_name: str,
#     request: GeminiGenerateContentRequest,
#     db: AsyncSession = Depends(get_db),
#     api_key: APIKey = Depends(_get_api_key_with_body)
# ):
#     """
#     Generate content using Gemini API (non-streaming).
#     
#     **Path Parameter:**
#     - `model_name`: Model ID (e.g., "gemini-2.5-pro")
#     
#     **Authentication:**
#     - Via `X-API-Key` header
#     - Via `api_key` field in request body
#     
#     **Request Format:**
#     Native Gemini format:
#     ```json
#     {
#         "contents": [
#             {
#                 "role": "user",
#                 "parts": [{"text": "Hello!"}]
#             }
#         ],
#         "generationConfig": {
#             "temperature": 0.7,
#             "maxOutputTokens": 1024
#         }
#     }
#     ```
#     """
#     logger.info(f"[GEMINI] Native generateContent for model: {model_name}")
#     
#     # Check if Gemini credentials are configured
#     if not api_key.gemini_credentials:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Gemini credentials not configured. Please connect your Google account via the extension."
#         )
#     
#     # Load credentials
#     credentials = load_credentials_from_dict(api_key.gemini_credentials)
#     if not credentials:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to load Gemini credentials"
#         )
#     
#     # Create chat service
#     chat_service = GeminiChatService(
#         credentials=credentials,
#         api_key=api_key,
#         db=db
#     )
#     
#     # Convert request to internal format
#     contents = [content.model_dump(by_alias=True, exclude_none=True) for content in request.contents]
#     system_instruction = request.system_instruction.model_dump(by_alias=True, exclude_none=True) if request.system_instruction else None
#     generation_config = request.generation_config.model_dump(by_alias=True, exclude_none=True) if request.generation_config else None
#     
#     # Convert safety_settings if provided
#     safety_settings = None
#     if request.safety_settings:
#         safety_settings = [s.model_dump(by_alias=True) for s in request.safety_settings]
#     
#     try:
#         gemini_response = await chat_service.generate_content(
#             model=model_name,
#             contents=contents,
#             system_instruction=system_instruction,
#             generation_config=generation_config,
#             tools=request.tools
#         )
#         
#         return GeminiGenerateContentResponse(**gemini_response)
#         
#     except Exception as e:
#         logger.exception(f"[GEMINI] Error in generateContent: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error generating content: {str(e)}"
#         )


# @router.post("/models/{model_name}:streamGenerateContent")
# async def stream_generate_content(
#     model_name: str,
#     request: GeminiGenerateContentRequest,
#     db: AsyncSession = Depends(get_db),
#     api_key: APIKey = Depends(_get_api_key_with_body)
# ):
#     """
#     Generate content using Gemini API (streaming).
#     
#     **Path Parameter:**
#     - `model_name`: Model ID (e.g., "gemini-2.5-pro")
#     
#     **Authentication:**
#     - Via `X-API-Key` header
#     - Via `api_key` field in request body
#     
#     **Response:**
#     Server-Sent Events (SSE) stream with native Gemini format chunks.
#     """
#     logger.info(f"[GEMINI] Native streamGenerateContent for model: {model_name}")
#     
#     # Check if Gemini credentials are configured
#     if not api_key.gemini_credentials:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Gemini credentials not configured. Please connect your Google account via the extension."
#         )
#     
#     # Load credentials
#     credentials = load_credentials_from_dict(api_key.gemini_credentials)
#     if not credentials:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to load Gemini credentials"
#         )
#     
#     # Create chat service
#     chat_service = GeminiChatService(
#         credentials=credentials,
#         api_key=api_key,
#         db=db
#     )
#     
#     # Convert request to internal format
#     contents = [content.model_dump(by_alias=True, exclude_none=True) for content in request.contents]
#     system_instruction = request.system_instruction.model_dump(by_alias=True, exclude_none=True) if request.system_instruction else None
#     generation_config = request.generation_config.model_dump(by_alias=True, exclude_none=True) if request.generation_config else None
#     
#     async def generate_sse():
#         """Generate Server-Sent Events for streaming response."""
#         import json
#         try:
#             async for chunk in chat_service.stream_generate_content(
#                 model=model_name,
#                 contents=contents,
#                 system_instruction=system_instruction,
#                 generation_config=generation_config,
#                 tools=request.tools
#             ):
#                 yield f"data: {json.dumps(chunk)}\n\n"
#             
#         except Exception as e:
#             logger.exception(f"[GEMINI] Streaming error: {e}")
#             error_response = {
#                 "error": {
#                     "message": str(e),
#                     "code": "INTERNAL"
#                 }
#             }
#             yield f"data: {json.dumps(error_response)}\n\n"
#     
#     return StreamingResponse(
#         generate_sse(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "Connection": "keep-alive",
#             "X-Accel-Buffering": "no",
#         }
#     )

