"""Answer Confidence Scorer.
Computes a 0-100 confidence score for a synthesised response based on:
  1. Source coverage ratio (how many sources are actually cited)
  2. Average quality score of cited sources
  3. Citation density (inline [N] markers per 100 words)
Emitted as SSE event {"type":"confidence",...} after "done" in agentic-stream.
Called by: app/api/routes/chat.py (agentic_chat_stream)."""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def compute_confidence(response: str, citations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute answer confidence from the final synthesised response.

    Args:
        response: Full text of the synthesised LLM response.
        citations: List of citation dicts (must have 'id' and optionally 'quality_score').

    Returns:
        Dict with score (0-100), label, cited_sources count, total_sources count.
    """
    if not citations:
        return {"score": 0, "label": "No Sources", "cited_sources": 0, "total_sources": 0}

    # --- 1. Source coverage (max 50 pts) ---
    # Find all [N] markers in the response
    cited_ids = set(re.findall(r"\[(\d{1,2})\]", response))
    coverage_ratio = len(cited_ids) / max(len(citations), 1)
    coverage_score = coverage_ratio * 50

    # --- 2. Average quality of cited sources (max 30 pts) ---
    cited_qualities = [
        c.get("quality_score", 50)
        for c in citations
        if str(c.get("id", "")) in cited_ids
    ]
    avg_quality = (sum(cited_qualities) / len(cited_qualities)) if cited_qualities else 50
    quality_score = avg_quality * 0.3

    # --- 3. Citation density (max 20 pts) ---
    word_count = max(len(response.split()), 1)
    density = len(cited_ids) / (word_count / 100)          # citations per 100 words
    density_score = min(density, 1.0) * 20                 # cap at 1.0 (≥1 citation/100w = full pts)

    # Aggregate
    raw_score = int(coverage_score + quality_score + density_score)
    score = max(0, min(100, raw_score))

    return {
        "score": score,
        "label": _confidence_label(score),
        "cited_sources": len(cited_ids),
        "total_sources": len(citations),
        "coverage_ratio": round(coverage_ratio, 2),
        "avg_source_quality": round(avg_quality, 1),
    }


def _confidence_label(score: int) -> str:
    """Human-readable label for the confidence score bucket."""
    if score >= 85:
        return "High"
    if score >= 65:
        return "Medium"
    if score >= 40:
        return "Low"
    return "Uncertain"
