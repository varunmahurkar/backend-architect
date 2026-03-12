"""
Citation Analyzer Tool — Analyze citation networks via Semantic Scholar API.
Finds citing papers, references, metrics, and influential citations. Free API.
"""

import json
import logging

import httpx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

S2_API = "https://api.semanticscholar.org/graph/v1/paper"


async def _resolve_paper_id(paper_id: str) -> str:
    """Resolve DOI or other ID to Semantic Scholar paper ID."""
    if paper_id.startswith("10."):
        return f"DOI:{paper_id}"
    return paper_id


async def _get_paper(paper_id: str) -> dict:
    """Get paper details from Semantic Scholar."""
    resolved = await _resolve_paper_id(paper_id)
    fields = "title,authors,citationCount,influentialCitationCount,year,url,abstract,venue,externalIds"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{S2_API}/{resolved}", params={"fields": fields})
        resp.raise_for_status()
        return resp.json()


async def _get_citations(paper_id: str, limit: int = 50) -> list[dict]:
    """Get papers that cite this paper."""
    resolved = await _resolve_paper_id(paper_id)
    fields = "title,authors,citationCount,year,url,isInfluential"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{S2_API}/{resolved}/citations",
            params={"fields": fields, "limit": min(limit, 1000)},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])


async def _get_references(paper_id: str, limit: int = 50) -> list[dict]:
    """Get papers referenced by this paper."""
    resolved = await _resolve_paper_id(paper_id)
    fields = "title,authors,citationCount,year,url,isInfluential"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{S2_API}/{resolved}/references",
            params={"fields": fields, "limit": min(limit, 1000)},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])


def _format_paper(p: dict) -> dict:
    """Format a paper dict for output."""
    authors = [a.get("name", "") for a in (p.get("authors") or [])]
    return {
        "title": p.get("title", ""),
        "authors": authors[:5],
        "citationCount": p.get("citationCount", 0),
        "year": p.get("year"),
        "url": p.get("url", ""),
    }


@nurav_tool(metadata=ToolMetadata(
    name="citation_analyzer",
    description="Analyze citation networks for a paper. Finds citing papers, references, influential citations, citation velocity, and key metrics via Semantic Scholar.",
    niche="academic",
    status=ToolStatus.ACTIVE,
    icon="git-branch",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"paper_id": "10.48550/arXiv.1706.03762", "depth": 1, "direction": "both"},
            output='{"paper": {"title": "Attention Is All You Need", "citationCount": 100000}, "citations": [...], "references": [...], "metrics": {...}}',
            description="Analyze citation network for the Transformer paper",
        ),
    ],
    input_schema={"paper_id": "str (DOI or Semantic Scholar ID)", "depth": "int (default 1)", "direction": "str ('citations'|'references'|'both')", "limit": "int (default 20)"},
    output_schema={"paper": "dict", "citations": "array", "references": "array", "metrics": "dict"},
    avg_response_ms=5000,
    success_rate=0.88,
))
@tool
async def citation_analyzer(paper_id: str, depth: int = 1, direction: str = "both", limit: int = 20) -> str:
    """Analyze citation network for a paper using its DOI or Semantic Scholar ID."""
    try:
        paper = await _get_paper(paper_id)

        result = {
            "paper": {
                "title": paper.get("title", ""),
                "authors": [a.get("name", "") for a in (paper.get("authors") or [])][:10],
                "citationCount": paper.get("citationCount", 0),
                "influentialCitationCount": paper.get("influentialCitationCount", 0),
                "year": paper.get("year"),
                "venue": paper.get("venue", ""),
                "url": paper.get("url", ""),
                "abstract": (paper.get("abstract") or "")[:1000],
            },
            "citations": [],
            "references": [],
            "metrics": {},
        }

        # Get citations
        if direction in ("citations", "both"):
            raw_citations = await _get_citations(paper_id, limit)
            for item in raw_citations:
                citing = item.get("citingPaper", {})
                result["citations"].append({
                    **_format_paper(citing),
                    "isInfluential": item.get("isInfluential", False),
                })

        # Get references
        if direction in ("references", "both"):
            raw_refs = await _get_references(paper_id, limit)
            for item in raw_refs:
                cited = item.get("citedPaper", {})
                result["references"].append({
                    **_format_paper(cited),
                    "isInfluential": item.get("isInfluential", False),
                })

        # Compute metrics
        total_citations = paper.get("citationCount", 0)
        influential = paper.get("influentialCitationCount", 0)
        year = paper.get("year") or 2024
        years_since = max(1, 2026 - year)

        citation_years = [c.get("year") for c in result["citations"] if c.get("year")]
        recent_citations = sum(1 for y in citation_years if y and y >= 2024)

        result["metrics"] = {
            "total_citations": total_citations,
            "influential_citations": influential,
            "influential_ratio": round(influential / max(total_citations, 1), 3),
            "citations_per_year": round(total_citations / years_since, 1),
            "recent_citations_2024_plus": recent_citations,
            "reference_count": len(result["references"]),
            "top_citing_papers": sorted(result["citations"], key=lambda x: x.get("citationCount", 0), reverse=True)[:5],
        }

        return json.dumps(result, ensure_ascii=False, default=str)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return json.dumps({"error": f"Paper not found: '{paper_id}'. Try a DOI (e.g., 10.48550/arXiv.1706.03762) or Semantic Scholar paper ID."})
        return json.dumps({"error": f"API error {e.response.status_code}: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Citation analysis failed: {str(e)}"})
