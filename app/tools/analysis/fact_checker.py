"""
Fact Checker Tool — Cross-reference claims against web + academic sources.
Uses existing search tools + LLM judgment for verdict.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _gather_evidence(claim: str, sources: list[str]) -> list[dict]:
    """Search for evidence using existing tools."""
    evidence = []

    if "web" in sources:
        try:
            from app.services.crawler_service import agentic_search
            results = await agentic_search(query=claim, max_results=5)
            for r in results[:5]:
                evidence.append({
                    "source": "web",
                    "title": r.get("title", ""),
                    "text": r.get("snippet", "")[:500],
                    "url": r.get("url", ""),
                })
        except Exception as e:
            logger.warning(f"Web search for fact-checking failed: {e}")

    if "academic" in sources:
        try:
            from app.services.sources.arxiv_source import search_arxiv
            results = await search_arxiv(query=claim, max_results=3)
            for r in results[:3]:
                evidence.append({
                    "source": "arxiv",
                    "title": r.get("title", ""),
                    "text": (r.get("summary", "") or "")[:500],
                    "url": r.get("pdf_url", ""),
                })
        except Exception as e:
            logger.warning(f"arXiv search for fact-checking failed: {e}")

    return evidence


async def _judge_claim(claim: str, evidence: list[dict]) -> dict:
    """Use LLM to judge whether evidence supports or refutes the claim."""
    from app.services.llm_service import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    evidence_text = "\n\n".join(
        f"[{e['source']}] {e['title']}: {e['text']}" for e in evidence
    )

    system = """You are a fact-checker. Given a claim and evidence, determine if the claim is supported, refuted, or inconclusive.
Respond ONLY with valid JSON:
{
  "verdict": "supported" | "refuted" | "inconclusive",
  "confidence": 0.0 to 1.0,
  "reasoning": "Brief explanation of your verdict",
  "evidence_assessment": [{"source_index": 0, "supports": true/false, "relevance": "high/medium/low", "note": "..."}]
}"""

    llm = get_llm(provider="google")
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=f"Claim: {claim}\n\nEvidence:\n{evidence_text}"),
    ])

    text = response.content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


@nurav_tool(metadata=ToolMetadata(
    name="fact_checker",
    description="Cross-reference claims against web and academic sources. Returns verdict (supported/refuted/inconclusive), confidence score, and evidence trail.",
    niche="analysis",
    status=ToolStatus.ACTIVE,
    icon="check-circle",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"claim": "The Earth is approximately 4.5 billion years old"},
            output='{"verdict": "supported", "confidence": 0.98, "reasoning": "...", "evidence": [...]}',
            description="Verify a scientific claim",
        ),
    ],
    input_schema={"claim": "str", "context": "str (optional)", "sources": "str (comma-separated: web,academic)"},
    output_schema={"verdict": "str", "confidence": "float", "reasoning": "str", "evidence": "array"},
    avg_response_ms=8000,
    success_rate=0.88,
))
@tool
async def fact_checker(claim: str, context: str = "", sources: str = "web,academic") -> str:
    """Verify a factual claim against web and academic sources."""
    if not claim.strip():
        return json.dumps({"error": "No claim provided."})

    source_list = [s.strip() for s in sources.split(",")]
    full_claim = f"{claim}. Context: {context}" if context else claim

    try:
        evidence = await _gather_evidence(full_claim, source_list)

        if not evidence:
            return json.dumps({
                "verdict": "inconclusive",
                "confidence": 0.0,
                "reasoning": "No evidence found to verify this claim.",
                "evidence": [],
            })

        judgment = await _judge_claim(claim, evidence)

        # Enrich evidence with source details
        for i, e in enumerate(evidence):
            e["supports"] = None
            if i < len(judgment.get("evidence_assessment", [])):
                assessment = judgment["evidence_assessment"][i]
                e["supports"] = assessment.get("supports")
                e["relevance"] = assessment.get("relevance", "medium")

        return json.dumps({
            "verdict": judgment.get("verdict", "inconclusive"),
            "confidence": judgment.get("confidence", 0.5),
            "reasoning": judgment.get("reasoning", ""),
            "evidence": evidence,
            "sources_checked": source_list,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Fact-checking failed: {str(e)}"})
