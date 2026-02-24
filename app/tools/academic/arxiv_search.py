"""
arXiv Search Tool — Wraps sources/arxiv_source.search_arxiv()
Searches arXiv for academic papers and returns structured metadata.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="arxiv_search",
    description="Search arXiv for academic papers. Returns paper titles, authors, abstracts, and PDF links.",
    niche="academic",
    status=ToolStatus.ACTIVE,
    icon="graduation-cap",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "transformer attention mechanism", "max_results": 3},
            output='[{"title": "Attention Is All You Need", "authors": [...], "summary": "...", "pdf_url": "..."}]',
            description="Search for papers on transformer architecture",
        ),
    ],
    input_schema={"query": "str", "max_results": "int (default 5)"},
    output_schema={"type": "array", "items": {"title": "str", "authors": "array", "summary": "str", "pdf_url": "str"}},
    avg_response_ms=3000,
    success_rate=0.92,
))
@tool
async def arxiv_search(query: str, max_results: int = 5) -> str:
    """Search arXiv for academic papers matching the query. Returns JSON array of paper metadata."""
    from app.services.sources.arxiv_source import search_arxiv

    results = await search_arxiv(query=query, max_results=max_results)
    return json.dumps(results, ensure_ascii=False)
