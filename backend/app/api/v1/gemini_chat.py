"""
[Gemini] Chat completions endpoint.

This module provides a /chat/completions endpoint that accepts OpenAI-format
requests and translates them to Gemini API calls, returning OpenAI-format responses.

IMPORTANT: This endpoint runs entirely on the server - no routing to browser extensions.
Authentication is via X-API-Key header or api_key field in request body.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.api_key import APIKey
from app.auth.dependencies import (
    validate_gemini_api_key,
    gemini_api_key_header_scheme,
    api_key_header_scheme
)
from app.schemas.gemini import ChatCompletionRequest, ChatCompletionResponse
from app.gemini.services.chat import (
    GeminiChatService,
    convert_openai_messages_to_gemini,
    convert_gemini_response_to_openai,
    convert_gemini_chunk_to_openai
)
from app.gemini.auth import load_credentials_from_dict

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/gemini/chat",
    tags=["gemini"],
)


async def _get_gemini_api_key(
    request: ChatCompletionRequest,
    gemini_api_key_header: Optional[str] = Depends(gemini_api_key_header_scheme),
    standard_api_key_header: Optional[str] = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db)
) -> APIKey:
    """
    Dependency that extracts API key for Gemini endpoints.
    
    Accepts (in order of precedence):
    1. x-goog-api-key header (Google-style)
    2. X-API-Key header (standard)
    3. api_key field in request body
    """
    return await validate_gemini_api_key(
        api_key_from_body=request.api_key,
        gemini_api_key_header=gemini_api_key_header,
        standard_api_key_header=standard_api_key_header,
        db=db
    )


@router.post("/completions", response_model=ChatCompletionResponse, summary="[Gemini] Chat Completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(_get_gemini_api_key)
):
    """
    Create a chat completion using Gemini models.
    
    This endpoint runs entirely on the server (no browser extension proxy).
    It accepts OpenAI-compatible request format and translates to Gemini API.
    
    **Authentication (in order of precedence):**
    - Via `x-goog-api-key` header (Google-style, recommended)
    - Via `X-API-Key` header (LinkedIn Gateway style)
    - Via `api_key` field in request body
    
    **Supported Models:**
    - gemini-2.5-pro, gemini-2.5-flash
    - gemini-2.5-pro-search, gemini-2.5-flash-search (with Google Search)
    - gemini-1.5-pro, gemini-1.5-flash
    
    **Request Format:**
    - `model`: Model ID (e.g., "gemini-2.5-pro")
    - `messages`: List of message objects with `role` and `content`
    - `temperature`, `top_p`, `max_tokens`: Generation parameters
    - `stream`: Set to true for streaming response
    - `api_key`: (optional) API key if not provided in header
    """
    logger.info(f"[GEMINI] Chat completion request for model: {request.model}")
    logger.info(f"[GEMINI] Messages count: {len(request.messages)}")
    logger.info(f"[GEMINI] Temperature: {request.temperature}, top_p: {request.top_p}, stream: {request.stream}")
    
    # Check if Gemini credentials are configured
    if not api_key.gemini_credentials:
        logger.warning(f"[GEMINI] No credentials for API key {api_key.prefix}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Gemini credentials not configured. Please connect your Google account via the extension."
        )
    
    # Load credentials
    credentials = load_credentials_from_dict(api_key.gemini_credentials)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load Gemini credentials"
        )
    
    # Create chat service
    chat_service = GeminiChatService(
        credentials=credentials,
        api_key=api_key,
        db=db
    )
    
    # Convert OpenAI messages to Gemini format
    contents, system_instruction = convert_openai_messages_to_gemini(
        [msg.model_dump() for msg in request.messages]
    )
    
    # Build generation config
    generation_config = {}
    if request.temperature is not None:
        generation_config["temperature"] = request.temperature
    if request.top_p is not None:
        generation_config["topP"] = request.top_p
    if request.max_tokens is not None:
        generation_config["maxOutputTokens"] = request.max_tokens
    if request.stop:
        stop_sequences = [request.stop] if isinstance(request.stop, str) else request.stop
        generation_config["stopSequences"] = stop_sequences
    
    # Handle streaming vs non-streaming
    if request.stream:
        return await _handle_streaming_completion(
            chat_service=chat_service,
            model=request.model,
            contents=contents,
            system_instruction=system_instruction,
            generation_config=generation_config if generation_config else None
        )
    else:
        return await _handle_non_streaming_completion(
            chat_service=chat_service,
            model=request.model,
            contents=contents,
            system_instruction=system_instruction,
            generation_config=generation_config if generation_config else None
        )


async def _handle_non_streaming_completion(
    chat_service: GeminiChatService,
    model: str,
    contents: list,
    system_instruction: Optional[dict],
    generation_config: Optional[dict]
) -> ChatCompletionResponse:
    """Handle non-streaming chat completion."""
    try:
        gemini_response = await chat_service.generate_content(
            model=model,
            contents=contents,
            system_instruction=system_instruction,
            generation_config=generation_config
        )
        
        # Convert to OpenAI format
        openai_response = convert_gemini_response_to_openai(
            gemini_response=gemini_response,
            model=model
        )
        
        return ChatCompletionResponse(**openai_response)
        
    except Exception as e:
        logger.exception(f"[GEMINI] Error generating content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating content: {str(e)}"
        )


async def _handle_streaming_completion(
    chat_service: GeminiChatService,
    model: str,
    contents: list,
    system_instruction: Optional[dict],
    generation_config: Optional[dict]
) -> StreamingResponse:
    """Handle streaming chat completion."""
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    
    async def generate_sse():
        """Generate Server-Sent Events for streaming response."""
        try:
            chunk_index = 0
            
            async for gemini_chunk in chat_service.stream_generate_content(
                model=model,
                contents=contents,
                system_instruction=system_instruction,
                generation_config=generation_config
            ):
                # Convert chunk to OpenAI format
                openai_chunk = convert_gemini_chunk_to_openai(
                    gemini_chunk=gemini_chunk,
                    model=model,
                    request_id=request_id,
                    chunk_index=chunk_index
                )
                chunk_index += 1
                
                # Format as SSE
                import json
                yield f"data: {json.dumps(openai_chunk)}\n\n"
            
            # Send [DONE] marker
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.exception(f"[GEMINI] Streaming error: {e}")
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "server_error"
                }
            }
            import json
            yield f"data: {json.dumps(error_chunk)}\n\n"
    
    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

