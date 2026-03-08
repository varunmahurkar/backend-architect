"""
Semantic Scholar Search Tool — Search 200M+ papers via Semantic Scholar API.
Free: 100 req/5min without key, 1 req/sec with key.
"""

import json
import logging

import httpx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


@nurav_tool(metadata=ToolMetadata(
    name="semantic_scholar_search",
    description="Search Semantic Scholar's 200M+ papers. Returns citation counts, TLDR summaries, influential citations, and related papers.",
    niche="academic",
    status=ToolStatus.ACTIVE,
    icon="brain",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "attention mechanism transformers", "max_results": 3},
            output='[{"paperId": "...", "title": "Attention Is All You Need", "citationCount": 100000, "tldr": "..."}]',
            description="Search for papers on attention mechanisms",
        ),
    ],
    input_schema={"query": "str", "max_results": "int (default 5)", "fields": "str (optional)"},
    output_schema={"type": "array", "items": {"paperId": "str", "title": "str", "authors": "array", "abstract": "str", "citationCount": "int", "tldr": "str", "url": "str", "year": "int"}},
    avg_response_ms=2500,
    success_rate=0.92,
))
@tool
async def semantic_scholar_search(query: str, max_results: int = 5, fields: str = "title,abstract,authors,citationCount,tldr,url,year,externalIds") -> str:
    """Search Semantic Scholar for academic papers. Returns JSON array with citation counts and TLDR summaries."""
    try:
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": fields,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(S2_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        papers = data.get("data", [])
        if not papers:
            return json.dumps({"results": [], "message": f"No papers found for '{query}'."})

        results = []
        for p in papers:
            authors = [a.get("name", "") for a in (p.get("authors") or [])]
            tldr = p.get("tldr")
            tldr_text = tldr.get("text", "") if isinstance(tldr, dict) else ""
            ext_ids = p.get("externalIds") or {}

            results.append({
                "paperId": p.get("paperId", ""),
                "title": p.get("title", ""),
                "authors": authors[:10],
                "abstract": (p.get("abstract") or "")[:2000],
                "citationCount": p.get("citationCount", 0),
                "tldr": tldr_text,
                "url": p.get("url", ""),
                "year": p.get("year"),
                "doi": ext_ids.get("DOI", ""),
            })

        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Semantic Scholar search failed: {str(e)}"})
