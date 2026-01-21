"""
Chat API routes for LLM interactions.
Supports multiple providers with streaming responses.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Literal
from app.api.dependencies.auth import get_current_user, get_optional_user, TokenPayload
from app.services.llm_service import (
    chat,
    chat_stream,
    get_available_providers,
    LLMProvider,
)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """Single chat message."""
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    """Chat request payload."""
    message: str = Field(..., min_length=1, max_length=10000)
    provider: Optional[LLMProvider] = "google"
    chat_history: Optional[list[ChatMessage]] = None
    system_prompt: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    """Chat response payload."""
    success: bool
    message: str
    provider: str
    model: Optional[str] = None


class ProvidersResponse(BaseModel):
    """Available providers response."""
    providers: list[dict]


@router.post("/completions", response_model=ChatResponse)
async def chat_completions(
    request: ChatRequest,
    current_user: Optional[TokenPayload] = Depends(get_optional_user),
):
    """
    Send a message to the LLM and get a response.

    - **message**: User message (required)
    - **provider**: LLM provider - google, openai, anthropic (default: google)
    - **chat_history**: Previous messages for context
    - **system_prompt**: Custom system prompt
    - **stream**: Enable streaming (use /chat/stream endpoint instead)
    """
    try:
        # Convert chat history to dict format
        history = None
        if request.chat_history:
            history = [{"role": msg.role, "content": msg.content} for msg in request.chat_history]

        response = await chat(
            message=request.message,
            provider=request.provider,
            chat_history=history,
            system_prompt=request.system_prompt,
        )

        return ChatResponse(
            success=True,
            message=response,
            provider=request.provider or "google",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {str(e)}",
        )


@router.post("/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    current_user: Optional[TokenPayload] = Depends(get_optional_user),
):
    """
    Stream a response from the LLM.

    Returns Server-Sent Events (SSE) stream.
    """
    try:
        # Convert chat history to dict format
        history = None
        if request.chat_history:
            history = [{"role": msg.role, "content": msg.content} for msg in request.chat_history]

        async def generate():
            try:
                async for chunk in chat_stream(
                    message=request.message,
                    provider=request.provider,
                    chat_history=history,
                    system_prompt=request.system_prompt,
                ):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: [ERROR] {str(e)}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers():
    """
    Get list of available LLM providers.

    Returns configured providers with their models.
    """
    providers = get_available_providers()

    if not providers:
        return ProvidersResponse(providers=[{
            "id": "google",
            "name": "Google Gemini",
            "model": "gemini-1.5-pro",
            "available": False,
            "message": "No API keys configured",
        }])

    return ProvidersResponse(providers=providers)
