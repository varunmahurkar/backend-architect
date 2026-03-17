"""
Memory Recall Tool — Retrieve user preferences and interaction context.
MVP: In-memory store. Will migrate to pgvector + Supabase.
"""

import json
import logging
from typing import Any

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

# In-memory user memory store (MVP)
_user_memories: dict[str, dict[str, Any]] = {}


def get_user_memory(user_id: str) -> dict:
    """Get or create a user's memory store."""
    if user_id not in _user_memories:
        _user_memories[user_id] = {
            "preferences": {},
            "recent_topics": [],
            "interaction_count": 0,
        }
    return _user_memories[user_id]


def record_interaction(user_id: str, query: str, topics: list[str] | None = None):
    """Record a user interaction (called by other tools/nodes)."""
    mem = get_user_memory(user_id)
    mem["interaction_count"] += 1
    if topics:
        existing = mem["recent_topics"]
        for t in topics:
            if t not in existing:
                existing.append(t)
        mem["recent_topics"] = existing[-50:]  # Keep last 50
    if query:
        recent_queries = mem.get("recent_queries", [])
        recent_queries.append(query)
        mem["recent_queries"] = recent_queries[-20:]


def set_preference(user_id: str, key: str, value: Any):
    """Set a user preference."""
    mem = get_user_memory(user_id)
    mem["preferences"][key] = value


@nurav_tool(metadata=ToolMetadata(
    name="memory_recall",
    description="Retrieve user preferences, past interaction topics, and learned patterns. Enables personalized responses based on conversation history.",
    niche="knowledge",
    status=ToolStatus.ACTIVE,
    icon="clock",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"user_id": "user123", "memory_type": "all"},
            output='{"preferences": {"language": "python"}, "recent_topics": ["AI", "ML"], "interaction_count": 42}',
            description="Recall user's full memory",
        ),
    ],
    input_schema={"user_id": "str", "query": "str (optional)", "memory_type": "str ('preferences'|'context'|'all')"},
    output_schema={"preferences": "dict", "recent_topics": "array", "interaction_count": "int"},
    avg_response_ms=100,
    success_rate=0.99,
))
@tool
async def memory_recall(user_id: str, query: str = "", memory_type: str = "all") -> str:
    """Recall user preferences and past interaction context."""
    uid = user_id or "default"
    mem = get_user_memory(uid)

    result = {}

    if memory_type in ("preferences", "all"):
        result["preferences"] = mem.get("preferences", {})

    if memory_type in ("context", "all"):
        result["recent_topics"] = mem.get("recent_topics", [])
        result["recent_queries"] = mem.get("recent_queries", [])[-10:]
        result["interaction_count"] = mem.get("interaction_count", 0)

    # If query provided, filter relevant topics
    if query and result.get("recent_topics"):
        query_lower = query.lower()
        relevant = [t for t in result["recent_topics"] if query_lower in t.lower() or t.lower() in query_lower]
        result["relevant_topics"] = relevant

    if not any(result.values()):
        result["message"] = "No stored memories yet. Your preferences and topics are learned as you interact with Nurav AI."

    return json.dumps(result, ensure_ascii=False, default=str)
