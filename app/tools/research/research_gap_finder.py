"""
Research Gap Finder Tool — Identify gaps and opportunities in existing literature.
Analyzes paper abstracts, conclusions, and "future work" sections.
"""

import json
import logging
import asyncio

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _fetch_papers(topic: str, max_papers: int) -> list[dict]:
    """Fetch papers from arXiv and Semantic Scholar."""
    import httpx

    async def arxiv():
        try:
            params = {"search_query": f"all:{topic}", "start": 0, "max_results": max_papers, "sortBy": "relevance"}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get("http://export.arxiv.org/api/query", params=params)
                resp.raise_for_status()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            papers = []
            for entry in root.findall("atom:entry", ns):
                t = entry.find("atom:title", ns)
                s = entry.find("atom:summary", ns)
                papers.append({
                    "title": t.text.strip() if t is not None else "",
                    "abstract": s.text.strip() if s is not None else "",
                    "source": "arXiv",
                })
            return papers
        except Exception:
            return []

    async def semantic():
        try:
            params = {"query": topic, "limit": max_papers, "fields": "title,abstract,year,citationCount"}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get("https://api.semanticscholar.org/graph/v1/paper/search", params=params)
                resp.raise_for_status()
                data = resp.json()
            return [{"title": p.get("title", ""), "abstract": (p.get("abstract") or ""), "year": p.get("year"), "source": "S2"} for p in data.get("data", [])]
        except Exception:
            return []

    results = await asyncio.gather(arxiv(), semantic())
    combined = results[0] + results[1]
    # Deduplicate
    seen = set()
    out = []
    for p in combined:
        key = p["title"].lower()[:40]
        if key not in seen and p["title"]:
            seen.add(key)
            out.append(p)
    return out[:max_papers]


@nurav_tool(metadata=ToolMetadata(
    name="research_gap_finder",
    description="Identify gaps and opportunities in existing literature. Analyzes paper abstracts and 'future work' sections to find under-explored areas, methodological weaknesses, and conflicting findings.",
    niche="research",
    status=ToolStatus.ACTIVE,
    icon="search-x",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"topic": "reinforcement learning robotics", "max_papers": 15},
            output='{"gaps": ["Limited real-world deployment studies", ...], "future_directions": [...], "conflicting_findings": [...]}',
            description="Find research gaps in RL robotics",
        ),
    ],
    input_schema={"topic": "str", "papers": "str (optional JSON array of paper abstracts)", "max_papers": "int (default 20)"},
    output_schema={"gaps": "array", "future_directions": "array", "methodology_gaps": "array", "conflicting_findings": "array", "opportunity_score": "dict"},
    avg_response_ms=18000,
    success_rate=0.87,
))
@tool
async def research_gap_finder(topic: str, papers: str = "[]", max_papers: int = 20) -> str:
    """Find research gaps in a topic area."""
    if not topic.strip():
        return json.dumps({"error": "No topic provided."})

    max_papers = max(5, min(40, max_papers))

    # Use provided papers or fetch them
    paper_list = []
    try:
        parsed = json.loads(papers)
        if isinstance(parsed, list) and parsed:
            paper_list = parsed
    except (json.JSONDecodeError, ValueError):
        pass

    if not paper_list:
        paper_list = await _fetch_papers(topic, max_papers)

    if not paper_list:
        return json.dumps({"error": "No papers found. Try a different topic."})

    # Synthesize gaps with LLM
    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        papers_text = "\n\n".join([
            f"[{i+1}] {p.get('title', 'Untitled')}\n{str(p.get('abstract', ''))[:400]}"
            for i, p in enumerate(paper_list[:20])
        ])

        system = """You are an expert research analyst specializing in identifying research gaps.
Analyze the provided papers and identify:
1. What has NOT been studied adequately
2. Methodological weaknesses in current literature
3. Conflicting findings that need resolution
4. Emerging areas with insufficient coverage

Respond ONLY with valid JSON:
{
  "gaps": ["specific gap 1", "gap 2", "..."],
  "future_directions": ["promising direction 1", "direction 2", "..."],
  "methodology_gaps": ["methodological weakness 1", "..."],
  "conflicting_findings": ["area of conflict 1", "..."],
  "underrepresented_populations": ["group 1", "..."],
  "opportunity_score": {
    "novelty_opportunity": "high|medium|low",
    "methodological_opportunity": "high|medium|low",
    "application_opportunity": "high|medium|low"
  },
  "summary": "1-2 sentence summary of the main gaps"
}"""

        llm = get_llm(provider="google")
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Topic: {topic}\n\nAnalyze these papers for research gaps:\n{papers_text}"),
        ])
        result_text = resp.content.strip()
        if result_text.startswith("```"):
            result_text = "\n".join(result_text.split("\n")[1:-1])

        analysis = json.loads(result_text)
        analysis["papers_analyzed"] = len(paper_list)
        analysis["topic"] = topic
        return json.dumps(analysis, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "error": f"Gap analysis failed: {str(e)}",
            "papers_analyzed": len(paper_list),
            "topic": topic,
        })
