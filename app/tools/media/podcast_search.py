"""
Podcast Search Tool — Search podcasts via Podcast Index API (free, open).
Falls back to DuckDuckGo podcast search if Podcast Index unavailable.
"""

import json
import logging
import asyncio

import httpx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

ITUNES_SEARCH = "https://itunes.apple.com/search"


async def _search_itunes(query: str, max_results: int) -> list[dict]:
    """Search iTunes/Apple Podcasts API (free, no key)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(ITUNES_SEARCH, params={
            "term": query,
            "media": "podcast",
            "entity": "podcastEpisode",
            "limit": min(max_results, 50),
        })
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("results", []):
        results.append({
            "title": item.get("trackName", ""),
            "podcast_name": item.get("collectionName", ""),
            "description": (item.get("description") or item.get("shortDescription") or "")[:500],
            "audio_url": item.get("episodeUrl", ""),
            "url": item.get("trackViewUrl", ""),
            "published": item.get("releaseDate", ""),
            "duration_seconds": item.get("trackTimeMillis", 0) // 1000 if item.get("trackTimeMillis") else None,
            "artwork": item.get("artworkUrl160", ""),
            "genre": item.get("primaryGenreName", ""),
        })
    return results


async def _search_ddg_podcasts(query: str, max_results: int) -> list[dict]:
    """Fallback: DuckDuckGo search for podcasts."""
    from duckduckgo_search import DDGS

    def _search():
        with DDGS() as ddgs:
            return list(ddgs.text(keywords=f"{query} podcast episode", max_results=max_results))

    raw = await asyncio.to_thread(_search)
    results = []
    for item in raw:
        results.append({
            "title": item.get("title", ""),
            "podcast_name": "",
            "description": item.get("body", ""),
            "url": item.get("href", ""),
            "source": "web_search",
        })
    return results


@nurav_tool(metadata=ToolMetadata(
    name="podcast_search",
    description="Search podcast episodes across Apple Podcasts. Returns episode metadata, audio links, duration, and artwork.",
    niche="media",
    status=ToolStatus.ACTIVE,
    icon="headphones",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "machine learning explained", "max_results": 5},
            output='[{"title": "ML Explained Ep 1", "podcast_name": "Data Skeptic", "audio_url": "...", "duration_seconds": 1800}]',
            description="Search for ML podcast episodes",
        ),
    ],
    input_schema={"query": "str", "max_results": "int (default 10)"},
    output_schema={"type": "array", "items": {"title": "str", "podcast_name": "str", "description": "str", "audio_url": "str", "published": "str", "duration_seconds": "int"}},
    avg_response_ms=2000,
    success_rate=0.90,
))
@tool
async def podcast_search(query: str, max_results: int = 10) -> str:
    """Search for podcast episodes via Apple Podcasts."""
    try:
        results = await _search_itunes(query, max_results)
        if results:
            return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"iTunes search failed: {e}")

    try:
        results = await _search_ddg_podcasts(query, max_results)
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Podcast search failed: {str(e)}"})
