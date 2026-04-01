"""
Memory Recall Tool — Retrieve user preferences and interaction context.
Backed by Supabase (user_memories table) with in-memory fallback.
"""

import json
import logging
from typing import Any

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample, tool_error

logger = logging.getLogger(__name__)

# In-memory fallback store
_user_memories: dict[str, dict[str, Any]] = {}


def _get_supabase():
    """Return a Supabase admin client or None if not configured."""
    try:
        from app.services.bloom_filter_service import get_supabase_admin_client
        return get_supabase_admin_client()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public helpers (used by other tools/nodes to record interactions)
# ---------------------------------------------------------------------------

def get_user_memory(user_id: str) -> dict:
    """Get or create a user's in-memory store (fallback)."""
    if user_id not in _user_memories:
        _user_memories[user_id] = {
            "preferences": {},
            "recent_topics": [],
            "interaction_count": 0,
        }
    return _user_memories[user_id]


def record_interaction(user_id: str, query: str, topics: list[str] | None = None):
    """Record a user interaction — writes to Supabase if available, else in-memory."""
    # In-memory update (always, for fast reads within the same process)
    mem = get_user_memory(user_id)
    mem["interaction_count"] += 1
    if topics:
        existing = mem.get("recent_topics", [])
        for t in topics:
            if t not in existing:
                existing.append(t)
        mem["recent_topics"] = existing[-50:]
    if query:
        recent_queries = mem.get("recent_queries", [])
        recent_queries.append(query)
        mem["recent_queries"] = recent_queries[-20:]

    # Supabase async-free upsert (best-effort)
    supabase = _get_supabase()
    if supabase:
        try:
            if topics:
                supabase.table("user_memories").upsert(
                    {"user_id": user_id, "category": "topic", "key": "recent_topics",
                     "value": mem["recent_topics"]},
                    on_conflict="user_id,category,key",
                ).execute()
            supabase.table("user_memories").upsert(
                {"user_id": user_id, "category": "interaction", "key": "count",
                 "value": mem["interaction_count"]},
                on_conflict="user_id,category,key",
            ).execute()
        except Exception as e:
            logger.debug(f"[memory_recall] Supabase record_interaction failed: {e}")


def set_preference(user_id: str, key: str, value: Any):
    """Set a user preference — writes to Supabase if available, else in-memory."""
    mem = get_user_memory(user_id)
    mem["preferences"][key] = value

    supabase = _get_supabase()
    if supabase:
        try:
            supabase.table("user_memories").upsert(
                {"user_id": user_id, "category": "preference", "key": key, "value": value},
                on_conflict="user_id,category,key",
            ).execute()
        except Exception as e:
            logger.debug(f"[memory_recall] Supabase set_preference failed: {e}")


def _load_from_supabase(user_id: str) -> dict | None:
    """Load all memory for a user from Supabase. Returns None if unavailable."""
    supabase = _get_supabase()
    if not supabase:
        return None
    try:
        rows = supabase.table("user_memories").select("*").eq("user_id", user_id).execute()
        if not rows.data:
            return None

        result: dict = {"preferences": {}, "recent_topics": [], "interaction_count": 0, "recent_queries": []}
        for row in rows.data:
            cat, key, val = row["category"], row["key"], row["value"]
            if cat == "preference":
                result["preferences"][key] = val
            elif cat == "topic" and key == "recent_topics":
                result["recent_topics"] = val if isinstance(val, list) else []
            elif cat == "interaction" and key == "count":
                result["interaction_count"] = int(val) if val else 0
            elif cat == "interaction" and key == "recent_queries":
                result["recent_queries"] = val if isinstance(val, list) else []
        return result
    except Exception as e:
        logger.warning(f"[memory_recall] Supabase load failed: {e}, using in-memory fallback")
        return None


@nurav_tool(metadata=ToolMetadata(
    name="memory_recall",
    description="Retrieve user preferences, past interaction topics, and learned patterns. Enables personalized responses based on conversation history.",
    niche="knowledge",
    status=ToolStatus.ACTIVE,
    icon="clock",
    version="1.1.0",
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

    # Try Supabase first, fall back to in-memory
    mem = _load_from_supabase(uid)
    if mem is None:
        mem = get_user_memory(uid)

    result: dict = {}

    if memory_type in ("preferences", "all"):
        result["preferences"] = mem.get("preferences", {})

    if memory_type in ("context", "all"):
        result["recent_topics"] = mem.get("recent_topics", [])
        result["recent_queries"] = (mem.get("recent_queries") or [])[-10:]
        result["interaction_count"] = mem.get("interaction_count", 0)

    # If query provided, filter relevant topics
    if query and result.get("recent_topics"):
        query_lower = query.lower()
        relevant = [t for t in result["recent_topics"] if query_lower in t.lower() or t.lower() in query_lower]
        result["relevant_topics"] = relevant

    if not any(v for v in result.values() if v):
        result["message"] = "No stored memories yet. Your preferences and topics are learned as you interact with Nurav AI."

    return json.dumps(result, ensure_ascii=False, default=str)
