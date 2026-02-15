"""
Conversations API Routes
REST endpoints for conversation persistence (CRUD + message management).
All endpoints require authentication.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from app.api.dependencies.auth import get_current_user, TokenPayload
from app.services import conversation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


# === Request/Response Models ===

class CreateConversationRequest(BaseModel):
    """Create conversation request."""
    title: str = Field(default="New Conversation", max_length=200)


class AddMessagesRequest(BaseModel):
    """Add messages to a conversation."""
    messages: List[dict] = Field(..., min_length=1, description="Messages to append")


class UpdateTitleRequest(BaseModel):
    """Update conversation title."""
    title: str = Field(..., min_length=1, max_length=200)


# === Endpoints ===

@router.post("")
async def create_conversation(
    request: CreateConversationRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Create a new conversation for the authenticated user."""
    try:
        conversation = await conversation_service.create_conversation(
            user_id=current_user.sub,
            title=request.title,
        )
        return {"success": True, "conversation": conversation}
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_conversations(
    current_user: TokenPayload = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):
    """List all conversations for the authenticated user, ordered by most recent."""
    try:
        conversations = await conversation_service.list_conversations(
            user_id=current_user.sub,
            limit=limit,
            offset=offset,
        )
        return {"success": True, "conversations": conversations}
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Load a conversation with all its messages."""
    try:
        conversation = await conversation_service.get_conversation(
            conversation_id=conversation_id,
            user_id=current_user.sub,
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"success": True, "conversation": conversation}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{conversation_id}/messages")
async def add_messages(
    conversation_id: str,
    request: AddMessagesRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Append messages to an existing conversation."""
    try:
        messages = await conversation_service.add_messages(
            conversation_id=conversation_id,
            user_id=current_user.sub,
            messages=request.messages,
        )
        return {"success": True, "messages": messages}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{conversation_id}")
async def update_title(
    conversation_id: str,
    request: UpdateTitleRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Update conversation title."""
    try:
        result = await conversation_service.update_conversation_title(
            conversation_id=conversation_id,
            user_id=current_user.sub,
            title=request.title,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"success": True, "conversation": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Delete a conversation and all its messages."""
    try:
        deleted = await conversation_service.delete_conversation(
            conversation_id=conversation_id,
            user_id=current_user.sub,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
