"""
Web Search Tool — Wraps crawler_service.agentic_search()
Searches the web using DuckDuckGo and returns structured results.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="web_search",
    description="Search the web using DuckDuckGo. Returns URLs, titles, and snippets for a given query.",
    niche="search",
    status=ToolStatus.ACTIVE,
    icon="search",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "latest advances in AI", "max_results": 5},
            output='[{"url": "...", "title": "...", "snippet": "..."}]',
            description="Search for recent AI news",
        ),
    ],
    input_schema={"query": "str", "max_results": "int (default 10)"},
    output_schema={"type": "array", "items": {"url": "str", "title": "str", "snippet": "str"}},
    avg_response_ms=2000,
    success_rate=0.95,
))
@tool
async def web_search(query: str, max_results: int = 10) -> str:
    """Search the web for information using DuckDuckGo. Returns JSON array of search results with url, title, and snippet."""
    from app.services.crawler_service import agentic_search

    results = await agentic_search(query=query, max_results=max_results)
    return json.dumps(results, ensure_ascii=False)
