"""
Google Scholar Search Tool — Search academic papers via scraping.
Uses scholarly library as primary, DuckDuckGo academic search as fallback.
Free, no API key required.
"""

import json
import logging
import asyncio

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _search_ddg_scholar(query: str, max_results: int) -> list[dict]:
    """Fallback: Use DuckDuckGo to search for academic content."""
    from duckduckgo_search import DDGS

    academic_query = f"{query} site:scholar.google.com OR site:researchgate.net OR site:academia.edu OR filetype:pdf"

    def _do_search():
        with DDGS() as ddgs:
            return list(ddgs.text(keywords=academic_query, max_results=max_results))

    raw = await asyncio.to_thread(_do_search)

    results = []
    for item in raw:
        results.append({
            "title": item.get("title", ""),
            "authors": [],
            "snippet": item.get("body", ""),
            "url": item.get("href", ""),
            "citation_count": None,
            "year": None,
            "source": "web_search",
        })
    return results


async def _search_semantic_scholar_broad(query: str, max_results: int, year_from: int, year_to: int) -> list[dict]:
    """Use Semantic Scholar API for broad academic search (better than scraping Google Scholar)."""
    import httpx

    params = {
        "query": query,
        "limit": min(max_results, 100),
        "fields": "title,authors,abstract,citationCount,url,year,externalIds,venue",
    }
    if year_from:
        params["year"] = f"{year_from}-" if not year_to else f"{year_from}-{year_to}"
    elif year_to:
        params["year"] = f"-{year_to}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get("https://api.semanticscholar.org/graph/v1/paper/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    papers = data.get("data", [])
    results = []
    for p in papers:
        authors = [a.get("name", "") for a in (p.get("authors") or [])]
        ext = p.get("externalIds") or {}
        results.append({
            "title": p.get("title", ""),
            "authors": authors[:8],
            "snippet": (p.get("abstract") or "")[:500],
            "url": p.get("url", ""),
            "citation_count": p.get("citationCount", 0),
            "year": p.get("year"),
            "venue": p.get("venue", ""),
            "doi": ext.get("DOI", ""),
            "source": "semantic_scholar",
        })
    return results


@nurav_tool(metadata=ToolMetadata(
    name="google_scholar_search",
    description="Search for academic papers across scholarly databases. Returns papers with citation counts, authors, and abstracts from Semantic Scholar + web fallback.",
    niche="academic",
    status=ToolStatus.ACTIVE,
    icon="book-open",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "deep learning image classification", "max_results": 5},
            output='[{"title": "...", "authors": [...], "citation_count": 500, "url": "...", "year": 2023}]',
            description="Search for image classification papers",
        ),
    ],
    input_schema={"query": "str", "max_results": "int (default 10)", "year_from": "int (optional)", "year_to": "int (optional)"},
    output_schema={"type": "array", "items": {"title": "str", "authors": "array", "snippet": "str", "url": "str", "citation_count": "int", "year": "int"}},
    avg_response_ms=3000,
    success_rate=0.90,
))
@tool
async def google_scholar_search(query: str, max_results: int = 10, year_from: int = 0, year_to: int = 0) -> str:
    """Search for academic papers. Uses Semantic Scholar API with web search fallback."""
    try:
        results = await _search_semantic_scholar_broad(query, max_results, year_from, year_to)
        if results:
            return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Semantic Scholar search failed: {e}")

    # Fallback to DuckDuckGo
    try:
        results = await _search_ddg_scholar(query, max_results)
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Scholar search failed: {str(e)}"})
