"""
Response Cache Tool — Wraps cache.py get/put operations
Checks and manages the response cache for previously answered queries.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="response_cache",
    description="Check the response cache for previously answered queries. Returns cached responses to avoid redundant computation.",
    niche="knowledge",
    status=ToolStatus.ACTIVE,
    icon="hard-drive",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "what is quantum computing", "mode": "simple"},
            output='{"hit": true, "response": "Quantum computing is...", "citations": [...]}',
            description="Check cache for a previously answered query",
        ),
    ],
    input_schema={"query": "str", "mode": "str (default 'simple')"},
    output_schema={"hit": "bool", "response": "str|null", "citations": "array|null"},
    avg_response_ms=5,
    success_rate=0.99,
))
@tool
async def response_cache_lookup(query: str, mode: str = "simple") -> str:
    """Check the response cache for a previously answered query. Returns cached response or cache miss."""
    from app.services.cache import response_cache

    cached = response_cache.get(query=query, mode=mode)

    if cached:
        return json.dumps({
            "hit": True,
            "response": cached["response"],
            "citations": cached["citations"],
        }, ensure_ascii=False)

    return json.dumps({
        "hit": False,
        "response": None,
        "citations": None,
        "message": "Cache miss — no cached response for this query.",
    })
