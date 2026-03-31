"""Synthesizer Node — builds quality-sorted citations and synthesis prompt.
LLM streaming happens in the endpoint after graph completion for true token-by-token streaming.
Enhancements vs v1:
  - Sources sorted by quality_score (highest-authority first in LLM context)
  - Structured prompts: research/deep modes produce sectioned responses
  - Wikipedia, News, Reddit sources included in context
  - Confidence scoring metadata stored in state
Called by: agents/graph.py → prepare_synthesis → endpoint streaming."""

import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse
from app.services.agents.state import AgentState, SourceResult, CitationEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts — vary by query mode
# ---------------------------------------------------------------------------

_BASE_CITATION_RULES = """
## CITATION RULES — MANDATORY
1. Add inline citations: [1], [2], [3] immediately after facts from sources.
2. The number matches Source [N] labels below.
3. Group: [1, 2] not [1][2]. Only cite from the provided sources.
"""

_BASE_FORMATTING = """
## FORMATTING
- **Bold** key terms. `code` for technical terms. ```language for blocks.
- Use > blockquotes when quoting directly.
- Bullet points for lists, ## headers for sections.
"""

_LIVE_DATA_RULES = """
## LIVE DATA MARKERS — USE WHEN QUERY IS ABOUT CURRENT PRICES, WEATHER, OR MARKETS
If the user asks about stock prices, crypto prices, or weather conditions, embed live data markers:
- Stock: [[LIVE:stock:TICKER]] — e.g., [[LIVE:stock:AAPL]] for Apple stock
- Crypto: [[LIVE:crypto:COIN_ID]] — e.g., [[LIVE:crypto:bitcoin]] for Bitcoin price (use CoinGecko IDs: bitcoin, ethereum, etc.)
- Weather: [[LIVE:weather:CITY]] — e.g., [[LIVE:weather:London]] for London weather
Place the marker inline where the live data fits naturally (after mentioning the asset/location).
Only use markers when live data is clearly relevant — do NOT use for historical or general queries.
"""

SYNTHESIS_PROMPT_SIMPLE = f"""You are Nurav AI, an intelligent research assistant. Provide a clear, accurate answer using the provided sources.
{_BASE_CITATION_RULES}{_BASE_FORMATTING}{_LIVE_DATA_RULES}
Be concise and direct. Prioritise higher-numbered authoritative sources when available."""

SYNTHESIS_PROMPT_RESEARCH = f"""You are Nurav AI, an intelligent research assistant. Provide a comprehensive, well-structured answer.
{_BASE_CITATION_RULES}{_BASE_FORMATTING}{_LIVE_DATA_RULES}
Structure your response with these sections:
## Overview
[1-2 sentence summary]

## Key Findings
[Bullet points with inline citations for each fact]

## Details
[Expanded explanation, comparisons, nuances]

## Related Topics
[2-3 follow-up areas the user might want to explore]

Synthesise across web, academic, news, and community sources. Highlight where sources agree or disagree."""

SYNTHESIS_PROMPT_DEEP = f"""You are Nurav AI, a deep research assistant producing expert-level reports.
{_BASE_CITATION_RULES}{_BASE_FORMATTING}{_LIVE_DATA_RULES}
Structure your response as an academic report:

## Executive Summary
[2-3 sentence TL;DR suitable for an expert audience]

## Background & Context
[Historical or conceptual foundations with citations]

## Key Findings & Evidence
[Detailed bullet points grouped by sub-topic, heavily cited]

## Analysis & Discussion
[Synthesis of evidence, disagreements, open questions]

## Practical Implications
[What this means in practice]

## References Summary
[Brief note on source types and quality]

Prefer academic and authoritative sources. Be specific, cite frequently, and acknowledge uncertainty."""


def _get_prompt_for_mode(mode: Optional[str]) -> str:
    if mode == "deep":
        return SYNTHESIS_PROMPT_DEEP
    if mode == "research":
        return SYNTHESIS_PROMPT_RESEARCH
    return SYNTHESIS_PROMPT_SIMPLE


async def prepare_synthesis_node(state: AgentState) -> dict:
    """Build quality-sorted citations and synthesis messages list.
    Stores in state for endpoint token-by-token streaming."""
    query = state.get("query", "")
    mode = state.get("mode") or state.get("query_complexity", "simple")
    chat_history = state.get("chat_history")
    custom_system = state.get("system_prompt")
    logger.info(f"Preparing synthesis: {query[:80]!r} | mode={mode}")

    # Collect all source types
    web_results = state.get("web_results", [])
    academic_results = state.get("academic_results", [])
    youtube_results = state.get("youtube_results", [])
    wikipedia_results = state.get("wikipedia_results", [])
    news_results = state.get("news_results", [])
    reddit_results = state.get("reddit_results", [])
    rag_context = state.get("rag_context", [])

    # Score sources with quality metadata
    from app.services.source_quality import score_sources

    all_sources: List[SourceResult] = (
        web_results + academic_results + youtube_results
        + wikipedia_results + news_results + reddit_results
    )

    # Enrich each source dict with quality_score + credibility_tier
    for src in all_sources:
        from app.services.source_quality import score_source
        qs, tier = score_source(
            src.get("url", ""),
            src.get("snippet", ""),
            src.get("published_at", ""),
        )
        src["quality_score"] = qs
        src["credibility_tier"] = tier

    # Sort by quality descending so highest-authority sources appear first in LLM context
    all_sources.sort(key=lambda s: s.get("quality_score", 0), reverse=True)

    # Build citations list
    citations: List[CitationEntry] = []
    for i, source in enumerate(all_sources, 1):
        domain = _extract_domain(source.get("url", ""))
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32" if domain else ""
        citations.append({
            "id": i,
            "url": source.get("url", ""),
            "root_url": f"https://{domain}",
            "title": source.get("title", ""),
            "snippet": source.get("snippet", "")[:200],
            "source_type": source.get("source_type", "web"),
            "favicon_url": favicon_url,
            "quality_score": source.get("quality_score", 0),
            "credibility_tier": source.get("credibility_tier", "general"),
            "published_at": source.get("published_at", ""),
        })

    # Build context string grouped by source type
    context_parts = _build_context_string(all_sources)

    if rag_context:
        context_parts.append("## Previous Context (Knowledge Base)")
        for i, ctx in enumerate(rag_context, 1):
            context_parts.append(
                f"Context [{i}]:\n- Source: {ctx.get('source', 'kb')}\n"
                f"- Content: {ctx.get('content', '')[:800]}\n"
            )

    context_text = "\n".join(context_parts)

    # Assemble final system prompt
    base_prompt = _get_prompt_for_mode(mode)
    if custom_system:
        base_prompt = f"{base_prompt}\n\nAdditional instructions: {custom_system}"

    full_system = f"{base_prompt}\n\n--- SOURCES ---\n{context_text}\n--- END SOURCES ---"

    # Inject personalization context when opt-in is active
    personalization_context = state.get("personalization_context")
    user_memory = state.get("user_memory")
    if personalization_context or user_memory:
        user_ctx_parts = ["--- USER CONTEXT (personalisation) ---"]
        if user_memory:
            topics = user_memory.get("recent_topics") or []
            prefs = user_memory.get("preferences") or {}
            relevant = user_memory.get("relevant_topics") or []
            count = user_memory.get("interaction_count", 0)
            if relevant:
                user_ctx_parts.append(f"Relevant past topics: {', '.join(relevant)}")
            elif topics:
                user_ctx_parts.append(f"Recent interests: {', '.join(topics[:5])}")
            if prefs:
                pref_str = ", ".join(f"{k}={v}" for k, v in list(prefs.items())[:5])
                user_ctx_parts.append(f"Preferences: {pref_str}")
            if count > 0:
                user_ctx_parts.append(f"Interaction history: {count} prior conversations")
        if personalization_context:
            ctx_summary = personalization_context.get("context_summary", "")
            if ctx_summary and ctx_summary != "No relevant knowledge found.":
                user_ctx_parts.append(f"Knowledge graph context: {ctx_summary}")
        user_ctx_parts.append("--- END USER CONTEXT ---")
        user_ctx_text = "\n".join(user_ctx_parts)
        # Prepend to system prompt so LLM can reference it
        full_system = f"{user_ctx_text}\n\n{full_system}"

    # Build message list for LLM
    messages = [{"role": "system", "content": full_system}]
    if chat_history:
        for msg in chat_history:
            role = msg.get("role", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": query})

    logger.info(f"Synthesis ready: {len(citations)} citations | mode={mode}")

    return {
        "citations": citations,
        "synthesis_system_prompt": full_system,
        "synthesis_messages": messages,
        "current_phase": "synthesized",
    }


# ---------------------------------------------------------------------------
# Context string builder
# ---------------------------------------------------------------------------

def _build_context_string(sources: List[SourceResult]) -> List[str]:
    """Build numbered source context grouped by type for the LLM prompt."""
    # Group by source_type
    groups: Dict[str, List[tuple]] = {}
    for i, src in enumerate(sources, 1):
        st = src.get("source_type", "web")
        groups.setdefault(st, []).append((i, src))

    parts: List[str] = []

    type_labels = {
        "web": "Web Sources",
        "arxiv": "Academic Sources (arXiv)",
        "youtube": "Video Sources",
        "wikipedia": "Wikipedia",
        "news": "News Sources",
        "reddit": "Community Discussion (Reddit)",
    }

    for source_type, label in type_labels.items():
        if source_type not in groups:
            continue
        parts.append(f"## {label}")
        for idx, src in groups[source_type]:
            domain = _extract_domain(src.get("url", ""))
            authors = ", ".join(src.get("authors", [])[:3])
            pub = src.get("published_at", "") or src.get("published", "")
            quality = src.get("quality_score", 0)

            meta_lines = []
            if authors:
                meta_lines.append(f"- Authors: {authors}")
            if pub:
                meta_lines.append(f"- Published: {pub[:10]}")
            meta_lines.append(f"- Quality: {quality}/100")

            parts.append(
                f"Source [{idx}] ({label}):\n"
                f"- URL: {src.get('url', '')}\n"
                f"- Domain: {domain}\n"
                f"- Title: {src.get('title', '')}\n"
                + "\n".join(meta_lines) + "\n"
                f"- Content: {src.get('content', src.get('snippet', ''))[:1500]}\n"
            )

    return parts


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "") or url
    except Exception:
        return url
