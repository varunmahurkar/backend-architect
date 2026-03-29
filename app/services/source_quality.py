"""Source Quality Scorer.
Assigns each citation a quality_score (0-100) and credibility_tier based on
domain authority, freshness, HTTPS, and snippet quality.
Called by: services/agents/nodes/synthesizer.py (prepare_synthesis_node)."""

import logging
from datetime import datetime, timezone
from typing import List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain tier lookup — O(1) dict, easily extensible
# ---------------------------------------------------------------------------
_DOMAIN_SCORES: dict[str, int] = {
    # Tier 1 — Authoritative (90+)
    "wikipedia.org": 92,
    "arxiv.org": 95,
    "pubmed.ncbi.nlm.nih.gov": 95,
    "nih.gov": 93,
    "who.int": 93,
    "cdc.gov": 93,
    "nasa.gov": 92,
    "nature.com": 94,
    "science.org": 93,
    "sciencedirect.com": 90,
    "springer.com": 90,
    "acm.org": 90,
    "ieee.org": 90,
    "jstor.org": 90,
    "doi.org": 90,
    # Tier 2 — Reputable media & tech (75-89)
    "bbc.com": 85,
    "bbc.co.uk": 85,
    "reuters.com": 87,
    "apnews.com": 86,
    "theguardian.com": 82,
    "nytimes.com": 83,
    "wsj.com": 83,
    "bloomberg.com": 84,
    "ft.com": 83,
    "techcrunch.com": 78,
    "wired.com": 79,
    "arstechnica.com": 80,
    "theverge.com": 76,
    "github.com": 85,
    "stackoverflow.com": 82,
    "docs.python.org": 90,
    "developer.mozilla.org": 90,
    "docs.microsoft.com": 86,
    "learn.microsoft.com": 86,
    "cloud.google.com": 85,
    "aws.amazon.com": 85,
    "openai.com": 82,
    "anthropic.com": 82,
    "huggingface.co": 84,
    # Tier 3 — Community / opinion (55-74)
    "medium.com": 62,
    "substack.com": 62,
    "dev.to": 65,
    "hashnode.com": 60,
    "reddit.com": 58,
    "quora.com": 55,
    "youtube.com": 68,  # video — content quality varies
    # Tier 4 — Unknown/generic (base 45)
}

_CREDIBILITY_MAP: dict[str, str] = {
    "tier1": "authoritative",
    "tier2": "reputable",
    "tier3": "community",
    "tier4": "general",
}

_GOVT_EDU_SUFFIXES = (".gov", ".edu", ".ac.uk", ".ac.au", ".gov.uk", ".mil")


def score_source(url: str, snippet: str = "", published_at: str = "") -> tuple[int, str]:
    """Compute quality_score (0-100) and credibility_tier string for a source URL.

    Args:
        url: Full source URL.
        snippet: Text snippet (used to penalise thin content).
        published_at: ISO 8601 publish date string (used for freshness bonus).

    Returns:
        (quality_score, credibility_tier) tuple.
    """
    domain = _extract_root_domain(url)

    # Base score from exact domain lookup
    base = _DOMAIN_SCORES.get(domain)
    tier = "tier4"

    if base is None:
        # Try suffix-based scoring for .gov / .edu
        base = _score_by_suffix(domain)
        if base >= 90:
            tier = "tier1"
        elif base >= 75:
            tier = "tier2"
        elif base >= 55:
            tier = "tier3"
    else:
        if base >= 90:
            tier = "tier1"
        elif base >= 75:
            tier = "tier2"
        elif base >= 55:
            tier = "tier3"

    # Freshness bonus (+10 if within 7 days, +5 if within 30 days)
    freshness = _freshness_bonus(published_at)

    # HTTPS bonus
    https_bonus = 5 if url.startswith("https://") else 0

    # Thin content penalty
    snippet_penalty = -10 if snippet and len(snippet.strip()) < 50 else 0

    score = min(100, base + freshness + https_bonus + snippet_penalty)
    credibility = _CREDIBILITY_MAP.get(tier, "general")
    return score, credibility


def score_sources(citations: list) -> list:
    """Enrich a list of citation dicts/objects with quality_score + credibility_tier.

    Works with both dict citations (from state) and Pydantic Citation objects.
    Returns the same list (mutated in-place) for chaining.
    """
    for c in citations:
        if isinstance(c, dict):
            url = c.get("url", "")
            snippet = c.get("snippet", "")
            published_at = c.get("published_at", "")
            score, tier = score_source(url, snippet, published_at)
            c["quality_score"] = score
            c["credibility_tier"] = tier
        else:
            # Pydantic model
            url = getattr(c, "url", "")
            snippet = getattr(c, "snippet", "")
            published_at = getattr(c, "published_at", "")
            score, tier = score_source(url, snippet, published_at)
            try:
                c.quality_score = score
                c.credibility_tier = tier
            except Exception:
                pass

    return citations


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_root_domain(url: str) -> str:
    """Extract root domain (e.g. 'bbc.com') from a full URL."""
    try:
        netloc = urlparse(url).netloc.lower()
        # Strip 'www.' prefix
        return netloc.removeprefix("www.")
    except Exception:
        return url.lower()


def _score_by_suffix(domain: str) -> int:
    """Assign a score based on TLD suffix for unknown domains."""
    for suffix in _GOVT_EDU_SUFFIXES:
        if domain.endswith(suffix):
            return 90  # government / educational — tier 1
    return 45  # unknown domain — tier 4 base


def _freshness_bonus(published_at: str) -> int:
    """Return freshness bonus points based on article age."""
    if not published_at:
        return 0
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_days = (now - dt).days
        if age_days <= 7:
            return 10
        if age_days <= 30:
            return 5
        return 0
    except Exception:
        return 0
