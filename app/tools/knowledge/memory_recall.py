"""Memory Recall Tool — COMING SOON: Retrieve user preferences and interaction history."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="memory_recall",
    description="Retrieve user preferences, past interaction context, and learned patterns. Enables personalized responses based on conversation history.",
    niche="knowledge",
    status=ToolStatus.COMING_SOON,
    icon="clock",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"user_id": "user123", "memory_type": "preferences"},
            output='{"preferences": [{"key": "language", "value": "python"}], "recent_topics": ["AI", "ML"]}',
            description="Recall user preferences",
        ),
    ],
    input_schema={"user_id": "str", "query": "str (optional)", "memory_type": "str ('preferences'|'context'|'all')"},
    output_schema={"preferences": "array", "recent_topics": "array", "interaction_patterns": "dict"},
    avg_response_ms=500,
))
@tool
async def memory_recall(user_id: str, query: str = "", memory_type: str = "all") -> str:
    """Recall user preferences and past context. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Memory recall is under development. Will use pgvector + Supabase for personalized context."})
