"""
News Search Tool — Search real-time news via DuckDuckGo News.
Free, no API key, no rate limits. Returns headlines, snippets, sources, dates.
"""

import json
import logging
from datetime import datetime

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


@nurav_tool(metadata=ToolMetadata(
    name="news_search",
    description="Search real-time news articles from multiple sources. Returns headlines, summaries, publication dates, and source URLs.",
    niche="search",
    status=ToolStatus.ACTIVE,
    icon="newspaper",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "AI regulation 2026", "max_results": 5},
            output='[{"title": "...", "snippet": "...", "url": "...", "source": "...", "date": "..."}]',
            description="Search for recent AI regulation news",
        ),
    ],
    input_schema={"query": "str", "max_results": "int (default 10)", "timelimit": "str ('d'=day, 'w'=week, 'm'=month, optional)"},
    output_schema={"type": "array", "items": {"title": "str", "snippet": "str", "url": "str", "source": "str", "date": "str"}},
    avg_response_ms=2000,
    success_rate=0.93,
))
@tool
async def news_search(query: str, max_results: int = 10, timelimit: str = "") -> str:
    """Search for real-time news articles using DuckDuckGo News."""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            kwargs = {"keywords": query, "max_results": min(max_results, 30)}
            if timelimit in ("d", "w", "m"):
                kwargs["timelimit"] = timelimit

            raw = list(ddgs.news(**kwargs))

        if not raw:
            return json.dumps({"results": [], "message": f"No news found for '{query}'."})

        results = []
        for item in raw:
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("body", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "date": item.get("date", ""),
                "image": item.get("image", ""),
            })

        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"News search failed: {str(e)}"})
