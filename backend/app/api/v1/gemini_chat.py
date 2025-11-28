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
    import json
    
    # ====== COMPREHENSIVE LOGGING: OPENAI-FORMAT REQUEST FROM CLIENT ======
    logger.info(f"[CLIENT->SERVER] ========== OPENAI-FORMAT REQUEST FROM CLIENT ==========")
    logger.info(f"[CLIENT->SERVER] Endpoint: /gemini/chat/completions")
    logger.info(f"[CLIENT->SERVER] Model: {request.model}")
    logger.info(f"[CLIENT->SERVER] Stream: {request.stream}")
    
    # Log full raw request body from client
    request_dict = request.model_dump(exclude={'api_key'})
    raw_body_json = json.dumps(request_dict, indent=2, ensure_ascii=False, default=str)
    logger.info(f"[CLIENT->SERVER] RAW REQUEST BODY ({len(raw_body_json)} chars):")
    if len(raw_body_json) > 5000:
        logger.info(f"[CLIENT->SERVER] (Body truncated, showing first 5000 chars)")
        logger.info(f"[CLIENT->SERVER] {raw_body_json[:5000]}...")
    else:
        logger.info(f"[CLIENT->SERVER] {raw_body_json}")
    
    # Log summary
    logger.info(f"[CLIENT->SERVER] --- Summary ---")
    logger.info(f"[CLIENT->SERVER]   messages: {len(request.messages)} items")
    logger.info(f"[CLIENT->SERVER]   temperature: {request.temperature}")
    logger.info(f"[CLIENT->SERVER]   top_p: {request.top_p}")
    logger.info(f"[CLIENT->SERVER]   max_tokens: {request.max_tokens}")
    logger.info(f"[CLIENT->SERVER]   stop: {request.stop}")
    logger.info(f"[CLIENT->SERVER] ================================================")
    
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
    
    # Log the converted format
    logger.info(f"[CLIENT->SERVER] Converted to Gemini format:")
    logger.info(f"[CLIENT->SERVER]   contents: {len(contents)} items")
    logger.info(f"[CLIENT->SERVER]   systemInstruction: {bool(system_instruction)}")
    
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
    
    logger.info(f"[CLIENT->SERVER]   generationConfig: {json.dumps(generation_config)}")
    
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
    import json
    
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
        
        # ====== COMPREHENSIVE LOGGING: OPENAI-FORMAT RESPONSE TO CLIENT ======
        logger.info(f"[SERVER->CLIENT] ========== OPENAI-FORMAT RESPONSE TO CLIENT ==========")
        logger.info(f"[SERVER->CLIENT] Endpoint: /gemini/chat/completions (non-streaming)")
        
        # Log full raw response being sent to client
        raw_response_json = json.dumps(openai_response, indent=2, ensure_ascii=False)
        logger.info(f"[SERVER->CLIENT] RAW RESPONSE BODY ({len(raw_response_json)} chars):")
        if len(raw_response_json) > 10000:
            logger.info(f"[SERVER->CLIENT] (Response truncated, showing first 10000 chars)")
            logger.info(f"[SERVER->CLIENT] {raw_response_json[:10000]}...")
        else:
            logger.info(f"[SERVER->CLIENT] {raw_response_json}")
        
        # Log response analysis
        logger.info(f"[SERVER->CLIENT] --- Response Analysis ---")
        choices = openai_response.get("choices", [])
        logger.info(f"[SERVER->CLIENT]   choices: {len(choices)}")
        for c_idx, choice in enumerate(choices):
            message = choice.get("message", {})
            content = message.get("content", "")
            reasoning = message.get("reasoning_content", "")
            logger.info(f"[SERVER->CLIENT]   Choice {c_idx}: content={len(content)} chars, reasoning={len(reasoning)} chars, finish_reason={choice.get('finish_reason')}")
        
        usage = openai_response.get("usage", {})
        logger.info(f"[SERVER->CLIENT]   usage: prompt_tokens={usage.get('prompt_tokens')}, completion_tokens={usage.get('completion_tokens')}")
        logger.info(f"[SERVER->CLIENT] ================================================")
        
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
    import json
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    
    async def generate_sse():
        """Generate Server-Sent Events for streaming response."""
        chunk_count = 0
        total_content_len = 0
        total_reasoning_len = 0
        
        try:
            logger.info(f"[SERVER->CLIENT] ========== OPENAI-FORMAT STREAMING RESPONSE ==========")
            logger.info(f"[SERVER->CLIENT] Endpoint: /gemini/chat/completions (streaming)")
            logger.info(f"[SERVER->CLIENT] Request ID: {request_id}")
            
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
                    chunk_index=chunk_count
                )
                chunk_count += 1
                
                # Track content lengths
                for choice in openai_chunk.get("choices", []):
                    delta = choice.get("delta", {})
                    if delta.get("content"):
                        total_content_len += len(delta["content"])
                    if delta.get("reasoning_content"):
                        total_reasoning_len += len(delta["reasoning_content"])
                
                chunk_json = json.dumps(openai_chunk)
                
                # Log every 10th chunk or first 3 chunks
                if chunk_count <= 3 or chunk_count % 10 == 0:
                    logger.info(f"[SERVER->CLIENT] Chunk #{chunk_count}: {len(chunk_json)} chars")
                    if len(chunk_json) <= 500:
                        logger.info(f"[SERVER->CLIENT] Chunk content: {chunk_json}")
                
                # Format as SSE
                yield f"data: {chunk_json}\n\n"
            
            # Send [DONE] marker
            yield "data: [DONE]\n\n"
            
            logger.info(f"[SERVER->CLIENT] --- Stream Complete ---")
            logger.info(f"[SERVER->CLIENT]   Total chunks: {chunk_count}")
            logger.info(f"[SERVER->CLIENT]   Total content: {total_content_len} chars")
            logger.info(f"[SERVER->CLIENT]   Total reasoning: {total_reasoning_len} chars")
            logger.info(f"[SERVER->CLIENT] ================================================")
            
        except Exception as e:
            logger.exception(f"[GEMINI] Streaming error: {e}")
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "server_error"
                }
            }
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

