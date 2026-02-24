"""
YouTube Search Tool — Wraps sources/youtube_source.search_youtube()
Searches YouTube for videos and optionally fetches transcripts.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="youtube_search",
    description="Search YouTube for relevant videos with optional transcript extraction. Great for tutorials and visual explanations.",
    niche="media",
    status=ToolStatus.ACTIVE,
    icon="play-circle",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "python asyncio tutorial", "max_results": 3},
            output='[{"title": "...", "url": "...", "channel": "...", "transcript": "..."}]',
            description="Search for Python async tutorial videos",
        ),
    ],
    input_schema={"query": "str", "max_results": "int (default 3)"},
    output_schema={"type": "array", "items": {"title": "str", "url": "str", "channel": "str", "transcript": "str|null"}},
    avg_response_ms=5000,
    success_rate=0.88,
))
@tool
async def youtube_search(query: str, max_results: int = 3) -> str:
    """Search YouTube for videos matching the query. Returns JSON array with video metadata and transcripts."""
    from app.services.sources.youtube_source import search_youtube

    results = await search_youtube(query=query, max_results=max_results)
    return json.dumps(results, ensure_ascii=False)
