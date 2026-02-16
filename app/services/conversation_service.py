"""
Conversation Persistence Service
CRUD operations for conversations and messages using Supabase service_role client.
Bypasses RLS since we validate user_id at the application level.
"""

import logging
from typing import Optional, List, Dict, Any
from app.config.settings import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Get Supabase admin client (service role, bypasses RLS)."""
    try:
        from supabase import create_client
    except ImportError:
        raise ImportError("supabase package not installed")

    if not settings.supabase_url:
        raise ValueError("SUPABASE_URL not configured")

    key = settings.supabase_service_role_key or settings.supabase_key
    if not key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY not configured")

    return create_client(settings.supabase_url, key)


async def create_conversation(user_id: str, title: str = "New Conversation") -> Dict[str, Any]:
    """Create a new conversation for a user."""
    client = _get_client()
    result = client.table("conversations").insert({
        "user_id": user_id,
        "title": title,
    }).execute()

    if not result.data:
        raise ValueError("Failed to create conversation")

    logger.info(f"Created conversation {result.data[0]['id']} for user {user_id}")
    return result.data[0]


async def list_conversations(user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """List user's conversations ordered by most recent activity."""
    client = _get_client()
    result = (
        client.table("conversations")
        .select("id, title, created_at, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data or []


async def get_conversation(conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a conversation with all its messages. Returns None if not found or unauthorized."""
    client = _get_client()

    # Fetch conversation (verify ownership)
    conv_result = (
        client.table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not conv_result.data:
        return None

    conversation = conv_result.data[0]

    # Fetch messages ordered by creation time
    msg_result = (
        client.table("conversation_messages")
        .select("id, role, content, citations, metadata, created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )

    conversation["messages"] = msg_result.data or []
    return conversation


async def add_messages(
    conversation_id: str,
    user_id: str,
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Append messages to a conversation.
    Validates user ownership before inserting.
    Each message: {"role": "user"|"assistant", "content": "...", "citations": [...]}
    """
    client = _get_client()

    # Verify conversation ownership
    conv_check = (
        client.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not conv_check.data:
        raise ValueError("Conversation not found or unauthorized")

    # Insert messages
    rows = []
    for msg in messages:
        rows.append({
            "conversation_id": conversation_id,
            "role": msg["role"],
            "content": msg["content"],
            "citations": msg.get("citations", []),
            "metadata": msg.get("metadata", {}),
        })

    result = client.table("conversation_messages").insert(rows).execute()
    logger.info(f"Added {len(rows)} messages to conversation {conversation_id}")
    return result.data or []


async def update_conversation_title(conversation_id: str, user_id: str, title: str) -> Optional[Dict[str, Any]]:
    """Update conversation title. Returns updated record or None if unauthorized."""
    client = _get_client()
    result = (
        client.table("conversations")
        .update({"title": title})
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None


async def delete_conversation(conversation_id: str, user_id: str) -> bool:
    """Delete a conversation and all its messages (CASCADE). Returns True if deleted."""
    client = _get_client()
    result = (
        client.table("conversations")
        .delete()
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    deleted = bool(result.data)
    if deleted:
        logger.info(f"Deleted conversation {conversation_id}")
    return deleted
