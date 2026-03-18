"""
Literature Review Tool — Automated literature reviews across academic sources.
Searches arXiv + Semantic Scholar, then synthesizes findings with LLM.
"""

import json
import logging
import asyncio

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _search_arxiv(query: str, max_results: int) -> list[dict]:
    """Search arXiv for papers."""
    try:
        import httpx
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("http://export.arxiv.org/api/query", params=params)
            resp.raise_for_status()

        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            id_el = entry.find("atom:id", ns)
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None]
            published_el = entry.find("atom:published", ns)
            papers.append({
                "title": title_el.text.strip().replace("\n", " ") if title_el is not None else "",
                "abstract": summary_el.text.strip().replace("\n", " ")[:500] if summary_el is not None else "",
                "authors": authors[:3],
                "year": published_el.text[:4] if published_el is not None else "",
                "url": id_el.text if id_el is not None else "",
                "source": "arXiv",
            })
        return papers
    except Exception as e:
        logger.warning(f"arXiv search failed: {e}")
        return []


async def _search_semantic_scholar(query: str, max_results: int) -> list[dict]:
    """Search Semantic Scholar."""
    try:
        import httpx
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,abstract,authors,year,externalIds,citationCount",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://api.semanticscholar.org/graph/v1/paper/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        papers = []
        for p in data.get("data", []):
            papers.append({
                "title": p.get("title", ""),
                "abstract": (p.get("abstract") or "")[:500],
                "authors": [a.get("name", "") for a in p.get("authors", [])[:3]],
                "year": str(p.get("year", "")),
                "citation_count": p.get("citationCount", 0),
                "url": f"https://semanticscholar.org/paper/{p.get('paperId', '')}",
                "source": "Semantic Scholar",
            })
        return papers
    except Exception as e:
        logger.warning(f"Semantic Scholar search failed: {e}")
        return []


@nurav_tool(metadata=ToolMetadata(
    name="literature_review",
    description="Automated literature review across arXiv and Semantic Scholar. Searches multiple sources, deduplicates, and synthesizes findings into a structured review with themes, methodology, and gaps.",
    niche="research",
    status=ToolStatus.ACTIVE,
    icon="library",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"topic": "CRISPR gene editing therapy", "max_papers": 10},
            output='{"review": "...", "papers": [...], "themes": [...], "gaps": [...], "methodology_summary": "..."}',
            description="Generate a literature review on CRISPR therapy",
        ),
    ],
    input_schema={"topic": "str", "max_papers": "int (default 15)", "sources": "str ('arxiv,semantic_scholar')", "focus": "str (optional aspect to emphasize)"},
    output_schema={"review": "str", "papers": "array", "themes": "array", "gaps": "array", "methodology_summary": "str"},
    avg_response_ms=20000,
    success_rate=0.88,
))
@tool
async def literature_review(topic: str, max_papers: int = 15, sources: str = "arxiv,semantic_scholar", focus: str = "") -> str:
    """Generate an automated literature review."""
    if not topic.strip():
        return json.dumps({"error": "No topic provided."})

    max_papers = max(3, min(30, max_papers))
    per_source = max_papers // 2

    source_list = [s.strip() for s in sources.lower().split(",")]

    # Search sources in parallel
    tasks = []
    if "arxiv" in source_list:
        tasks.append(_search_arxiv(topic, per_source))
    if "semantic_scholar" in source_list:
        tasks.append(_search_semantic_scholar(topic, per_source))

    results = await asyncio.gather(*tasks)
    all_papers = []
    for r in results:
        all_papers.extend(r)

    # Deduplicate by title similarity
    seen_titles = set()
    unique_papers = []
    for p in all_papers:
        title_key = p["title"].lower()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_papers.append(p)

    unique_papers = unique_papers[:max_papers]

    if not unique_papers:
        return json.dumps({"error": "No papers found. Try a different topic or broader search terms."})

    # Synthesize with LLM
    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        papers_summary = "\n\n".join([
            f"Title: {p['title']}\nAuthors: {', '.join(p['authors'])}\nYear: {p['year']}\nAbstract: {p['abstract']}"
            for p in unique_papers[:15]
        ])

        focus_note = f"\nFocus especially on: {focus}" if focus else ""

        system = f"""You are an expert academic researcher writing a literature review.
Analyze the provided papers and synthesize them into a structured review.{focus_note}

Respond ONLY with valid JSON:
{{
  "review": "A comprehensive 3-5 paragraph literature review synthesis",
  "themes": ["major theme 1", "major theme 2", "..."],
  "gaps": ["research gap 1", "gap 2", "..."],
  "methodology_summary": "Summary of common research methodologies used",
  "key_findings": ["finding 1", "finding 2", "..."],
  "temporal_trends": "How the field has evolved over time"
}}"""

        llm = get_llm(provider="google")
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Topic: {topic}\n\nPapers:\n{papers_summary}"),
        ])
        result_text = resp.content.strip()
        if result_text.startswith("```"):
            result_text = "\n".join(result_text.split("\n")[1:-1])

        synthesis = json.loads(result_text)
    except Exception as e:
        logger.warning(f"LLM synthesis failed: {e}")
        synthesis = {
            "review": f"Literature review for '{topic}' based on {len(unique_papers)} papers.",
            "themes": [],
            "gaps": [],
            "methodology_summary": "",
            "key_findings": [],
        }

    return json.dumps({
        "review": synthesis.get("review", ""),
        "papers": unique_papers,
        "themes": synthesis.get("themes", []),
        "gaps": synthesis.get("gaps", []),
        "methodology_summary": synthesis.get("methodology_summary", ""),
        "key_findings": synthesis.get("key_findings", []),
        "temporal_trends": synthesis.get("temporal_trends", ""),
        "total_papers": len(unique_papers),
        "sources_searched": source_list,
        "topic": topic,
    }, ensure_ascii=False)
