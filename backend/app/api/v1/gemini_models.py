"""
OpenAI-compatible models endpoint for Gemini.

Lists available Gemini models in OpenAI-compatible format.
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.api_key import APIKey
from app.auth.dependencies import get_requesting_user_from_api_key
from app.schemas.gemini import ModelsListResponse, ModelInfo
from app.gemini.config import SUPPORTED_MODELS

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/models",
    tags=["gemini-models"],
)


@router.get("", response_model=ModelsListResponse)
async def list_models(
    api_key: APIKey = Depends(get_requesting_user_from_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    List available Gemini models.
    
    Returns models in OpenAI-compatible format.
    
    **Authentication:**
    - Via `X-API-Key` header
    
    **Response:**
    Same format as OpenAI's /v1/models endpoint:
    ```json
    {
        "object": "list",
        "data": [
            {
                "id": "gemini-2.5-pro",
                "object": "model",
                "created": 1699000000,
                "owned_by": "google"
            },
            ...
        ]
    }
    ```
    """
    logger.info(f"[GEMINI] Models list request from API key: {api_key.prefix}")
    
    # Convert supported models to OpenAI format
    models_data = []
    created_timestamp = int(time.time())
    
    for model in SUPPORTED_MODELS:
        models_data.append(ModelInfo(
            id=model["id"],
            object="model",
            created=created_timestamp,
            owned_by="google"
        ))
    
    return ModelsListResponse(
        object="list",
        data=models_data
    )


@router.get("/{model_id}")
async def get_model(
    model_id: str,
    api_key: APIKey = Depends(get_requesting_user_from_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Get details for a specific model.
    
    **Authentication:**
    - Via `X-API-Key` header
    """
    logger.info(f"[GEMINI] Model details request for: {model_id}")
    
    # Find the model
    for model in SUPPORTED_MODELS:
        if model["id"] == model_id:
            return ModelInfo(
                id=model["id"],
                object="model",
                created=int(time.time()),
                owned_by="google"
            )
    
    # Model not found
    raise HTTPException(
        status_code=404,
        detail=f"Model '{model_id}' not found"
    )

