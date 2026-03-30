"""Search Nodes — parallel multi-source search with per-source timeouts.
Each source runs concurrently via asyncio.gather(return_exceptions=True) so
a slow or failing source never blocks others.

Sources routed by intent:
  - web (DuckDuckGo) — always included
  - arxiv — academic / scientific intent
  - youtube — tutorial / how-to / video intent
  - wikipedia — factual / definition intent
  - news — current_events / breaking intent
  - reddit — opinion / community / best-practices intent

Called by: agents/graph.py (simple_search_node, research_search_node)."""

import asyncio
import logging
from typing import List, Dict
from app.services.agents.state import AgentState, SourceResult
from app.services.crawler_service import agentic_search
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Per-source timeout caps (seconds) — tuned so slowest source = research timeout
_TIMEOUTS = {
    "web": 6,
    "arxiv": 5,
    "youtube": 6,
    "wikipedia": 4,
    "news": 5,
    "reddit": 6,
}


async def simple_search_node(state: AgentState) -> dict:
    """DuckDuckGo web search for simple queries (< 5s target)."""
    query = state.get("query", "")
    logger.info(f"Simple search for: {query[:100]}")

    try:
        raw_results = await asyncio.wait_for(
            agentic_search(query=query, max_results=5),
            timeout=settings.query_timeout_simple,
        )
        web_results: List[SourceResult] = [_to_web_result(r) for r in raw_results]
        logger.info(f"Simple search returned {len(web_results)} results")
        return {"web_results": web_results, "current_phase": "searched"}

    except asyncio.TimeoutError:
        logger.warning(f"Simple search timed out after {settings.query_timeout_simple}s")
        return {
            "web_results": [],
            "current_phase": "searched",
            "errors": state.get("errors", []) + ["Web search timed out"],
        }
    except Exception as e:
        logger.error(f"Simple search failed: {e}")
        return {
            "web_results": [],
            "current_phase": "searched",
            "errors": state.get("errors", []) + [f"Web search failed: {str(e)}"],
        }


async def research_search_node(state: AgentState) -> dict:
    """Parallel multi-source search for research/deep queries (5-15s target).

    Runs all applicable sources concurrently. Each source has its own timeout
    so a slow source degrades gracefully without blocking others.
    """
    query = state.get("query", "")
    required_sources = state.get("requires_sources", ["web"])
    intent = state.get("query_intent", "factual")
    logger.info(f"Research search: {query[:100]} | sources={required_sources} | intent={intent}")

    errors = list(state.get("errors", []))

    # Build task map based on required sources and intent
    task_map: Dict[str, asyncio.Task] = {}

    if "web" in required_sources:
        task_map["web"] = asyncio.ensure_future(
            asyncio.wait_for(_search_web(query), timeout=_TIMEOUTS["web"])
        )

    if "arxiv" in required_sources:
        task_map["arxiv"] = asyncio.ensure_future(
            asyncio.wait_for(_search_arxiv(query), timeout=_TIMEOUTS["arxiv"])
        )

    if "youtube" in required_sources:
        task_map["youtube"] = asyncio.ensure_future(
            asyncio.wait_for(_search_youtube(query), timeout=_TIMEOUTS["youtube"])
        )

    # Route additional sources by intent
    if intent in ("factual", "definition", "explanation") or "wikipedia" in required_sources:
        task_map["wikipedia"] = asyncio.ensure_future(
            asyncio.wait_for(_search_wikipedia(query), timeout=_TIMEOUTS["wikipedia"])
        )

    if intent in ("current_events", "news", "recent") or "news" in required_sources:
        task_map["news"] = asyncio.ensure_future(
            asyncio.wait_for(_search_news(query), timeout=_TIMEOUTS["news"])
        )

    if intent in ("opinion", "community", "recommendation") or "reddit" in required_sources:
        task_map["reddit"] = asyncio.ensure_future(
            asyncio.wait_for(_search_reddit(query), timeout=_TIMEOUTS["reddit"])
        )

    # Gather all concurrently — exceptions are captured, not raised
    task_items = list(task_map.items())
    results_gathered = await asyncio.gather(
        *[item[1] for item in task_items],
        return_exceptions=True,
    )

    results_map: Dict[str, List[SourceResult]] = {}
    for (name, _), result in zip(task_items, results_gathered):
        if isinstance(result, Exception):
            logger.error(f"{name} search failed: {result}")
            errors.append(f"{name} search failed: {str(result)[:80]}")
            results_map[name] = []
        else:
            results_map[name] = result or []

    web_results = results_map.get("web", [])
    academic_results = results_map.get("arxiv", [])
    youtube_results = results_map.get("youtube", [])
    wikipedia_results = results_map.get("wikipedia", [])
    news_results = results_map.get("news", [])
    reddit_results = results_map.get("reddit", [])

    logger.info(
        f"Research totals: web={len(web_results)}, arxiv={len(academic_results)}, "
        f"youtube={len(youtube_results)}, wiki={len(wikipedia_results)}, "
        f"news={len(news_results)}, reddit={len(reddit_results)}"
    )

    return {
        "web_results": web_results,
        "academic_results": academic_results,
        "youtube_results": youtube_results,
        "wikipedia_results": wikipedia_results,
        "news_results": news_results,
        "reddit_results": reddit_results,
        "current_phase": "searched",
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Source helpers — each returns List[SourceResult]
# ---------------------------------------------------------------------------

async def _search_web(query: str) -> List[SourceResult]:
    """DuckDuckGo general web search."""
    raw = await agentic_search(query=query, max_results=10)
    return [_to_web_result(r) for r in raw]


def _to_web_result(r: dict) -> SourceResult:
    return {
        "title": r.get("title", ""),
        "url": r.get("url", ""),
        "snippet": r.get("snippet", ""),
        "content": r.get("snippet", ""),
        "source_type": "web",
        "authors": [],
        "published": "",
        "published_at": "",
        "metadata": {},
    }


async def _search_arxiv(query: str) -> List[SourceResult]:
    """arXiv academic papers."""
    try:
        from app.services.sources.arxiv_source import search_arxiv
        papers = await search_arxiv(query=query, max_results=5)
        return [
            {
                "title": p.get("title", ""),
                "url": p.get("pdf_url", ""),
                "snippet": p.get("summary", "")[:500],
                "content": p.get("summary", ""),
                "source_type": "arxiv",
                "authors": p.get("authors", []),
                "published": p.get("published", ""),
                "published_at": p.get("published", ""),
                "metadata": {
                    "arxiv_id": p.get("arxiv_id", ""),
                    "categories": p.get("categories", []),
                },
            }
            for p in papers
        ]
    except ImportError:
        logger.warning("arxiv package not installed")
        return []


async def _search_youtube(query: str) -> List[SourceResult]:
    """YouTube videos with transcripts."""
    try:
        from app.services.sources.youtube_source import search_youtube
        videos = await search_youtube(query=query, max_results=3)
        return [
            {
                "title": v.get("title", ""),
                "url": v.get("url", ""),
                "snippet": v.get("description", "")[:300],
                "content": v.get("transcript", v.get("description", ""))[:2000],
                "source_type": "youtube",
                "authors": [v.get("channel", "")],
                "published": v.get("published", ""),
                "published_at": v.get("published", ""),
                "metadata": {
                    "video_id": v.get("video_id", ""),
                    "channel": v.get("channel", ""),
                },
            }
            for v in videos
        ]
    except ImportError:
        logger.warning("YouTube packages not installed")
        return []


async def _search_wikipedia(query: str) -> List[SourceResult]:
    """Wikipedia article summaries."""
    from app.services.sources.wikipedia_source import search_wikipedia
    articles = await search_wikipedia(query=query, max_results=2)
    return [
        {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "snippet": a.get("snippet", ""),
            "content": a.get("content", ""),
            "source_type": "wikipedia",
            "authors": [],
            "published": "",
            "published_at": "",
            "metadata": a.get("metadata", {}),
        }
        for a in articles
    ]


async def _search_news(query: str) -> List[SourceResult]:
    """Recent news articles."""
    from app.services.sources.news_source import search_news
    articles = await search_news(query=query, max_results=5)
    return [
        {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "snippet": a.get("snippet", ""),
            "content": a.get("content", ""),
            "source_type": "news",
            "authors": a.get("authors", []),
            "published": a.get("published_at", ""),
            "published_at": a.get("published_at", ""),
            "metadata": a.get("metadata", {}),
        }
        for a in articles
    ]


async def _search_reddit(query: str) -> List[SourceResult]:
    """Reddit community posts and top comments."""
    from app.services.sources.reddit_source import search_reddit
    posts = await search_reddit(query=query, max_results=5)
    return [
        {
            "title": p.get("title", ""),
            "url": p.get("url", ""),
            "snippet": p.get("snippet", ""),
            "content": p.get("content", ""),
            "source_type": "reddit",
            "authors": p.get("authors", []),
            "published": p.get("published_at", ""),
            "published_at": p.get("published_at", ""),
            "metadata": p.get("metadata", {}),
        }
        for p in posts
    ]
