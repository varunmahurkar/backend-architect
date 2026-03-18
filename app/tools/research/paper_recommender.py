"""
Paper Recommender Tool — Recommend relevant academic papers.
Uses Semantic Scholar recommendations API + query-based search.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _recommend_by_paper_id(paper_id: str, max_results: int) -> list[dict]:
    """Use Semantic Scholar recommendations API."""
    import httpx
    try:
        url = f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_id}"
        params = {"limit": max_results, "fields": "title,abstract,authors,year,citationCount,externalIds"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        papers = []
        for p in data.get("recommendedPapers", []):
            papers.append({
                "title": p.get("title", ""),
                "abstract": (p.get("abstract") or "")[:300],
                "authors": [a.get("name", "") for a in p.get("authors", [])[:3]],
                "year": p.get("year"),
                "citation_count": p.get("citationCount", 0),
                "url": f"https://semanticscholar.org/paper/{p.get('paperId', '')}",
                "relevance_score": None,
                "reason": "Recommended by Semantic Scholar based on seed paper",
            })
        return papers
    except Exception as e:
        logger.warning(f"S2 recommendations failed: {e}")
        return []


async def _recommend_by_query(query: str, max_results: int) -> list[dict]:
    """Search-based recommendation."""
    import httpx
    try:
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,abstract,authors,year,citationCount",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://api.semanticscholar.org/graph/v1/paper/search", params=params)
            resp.raise_for_status()
            data = resp.json()
        papers = []
        for i, p in enumerate(data.get("data", [])):
            papers.append({
                "title": p.get("title", ""),
                "abstract": (p.get("abstract") or "")[:300],
                "authors": [a.get("name", "") for a in p.get("authors", [])[:3]],
                "year": p.get("year"),
                "citation_count": p.get("citationCount", 0),
                "url": f"https://semanticscholar.org/paper/{p.get('paperId', '')}",
                "relevance_score": round(1.0 - i * 0.05, 2),
                "reason": f"Highly relevant to query: '{query}'",
            })
        return papers
    except Exception as e:
        logger.warning(f"S2 search failed: {e}")
        return []


@nurav_tool(metadata=ToolMetadata(
    name="paper_recommender",
    description="Recommend relevant academic papers based on query, topic, or a seed paper ID. Uses Semantic Scholar's recommendation engine plus LLM-powered relevance explanations.",
    niche="research",
    status=ToolStatus.ACTIVE,
    icon="sparkles",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "attention mechanisms transformers", "max_results": 5},
            output='[{"title": "Attention Is All You Need", "year": 2017, "relevance_score": 0.98, "reason": "Foundational paper on attention"}]',
            description="Get paper recommendations for attention mechanisms",
        ),
    ],
    input_schema={"query": "str (optional)", "seed_paper_id": "str (optional Semantic Scholar paper ID)", "max_results": "int (default 10)"},
    output_schema={"type": "array", "items": {"title": "str", "authors": "array", "year": "int", "url": "str", "relevance_score": "float", "reason": "str"}},
    avg_response_ms=4000,
    success_rate=0.91,
))
@tool
async def paper_recommender(query: str = "", seed_paper_id: str = "", max_results: int = 10) -> str:
    """Recommend relevant academic papers."""
    if not query.strip() and not seed_paper_id.strip():
        return json.dumps({"error": "Provide either a query or a seed_paper_id."})

    max_results = max(1, min(20, max_results))

    papers = []

    # Try seed paper recommendation first
    if seed_paper_id.strip():
        papers = await _recommend_by_paper_id(seed_paper_id.strip(), max_results)

    # Fall back to query-based search
    if not papers and query.strip():
        papers = await _recommend_by_query(query.strip(), max_results)

    if not papers:
        return json.dumps({"error": "No recommendations found. Try a different query or paper ID."})

    # Enrich with LLM relevance explanations if query provided
    if query.strip() and len(papers) > 0:
        try:
            from app.services.llm_service import get_llm
            from langchain_core.messages import HumanMessage, SystemMessage

            papers_text = "\n".join([f"{i+1}. {p['title']} ({p.get('year', '')})" for i, p in enumerate(papers[:10])])
            system = """For each paper, provide a short relevance explanation (1 sentence) explaining why it's relevant to the query.
Respond ONLY with valid JSON array matching the paper count:
["reason for paper 1", "reason for paper 2", ...]"""

            llm = get_llm(provider="google")
            resp = await llm.ainvoke([
                SystemMessage(content=system),
                HumanMessage(content=f"Query: {query}\n\nPapers:\n{papers_text}"),
            ])
            result_text = resp.content.strip()
            if result_text.startswith("```"):
                result_text = "\n".join(result_text.split("\n")[1:-1])
            reasons = json.loads(result_text)
            for i, reason in enumerate(reasons[:len(papers)]):
                papers[i]["reason"] = reason
        except Exception:
            pass  # Keep original reasons

    return json.dumps({
        "recommendations": papers,
        "total": len(papers),
        "query": query,
        "seed_paper_id": seed_paper_id,
    }, ensure_ascii=False)
