"""
Search Nodes
Handles web search (simple mode) and parallel multi-source search (research mode).
Aggregates results from DuckDuckGo, arXiv, and YouTube.
"""

import logging
import asyncio
from typing import List, Dict
from app.services.agents.state import AgentState, SourceResult
from app.services.crawler_service import agentic_search
from app.config.settings import settings

logger = logging.getLogger(__name__)


async def simple_search_node(state: AgentState) -> dict:
    """
    Simple web search using existing DuckDuckGo integration.
    Used for quick factual queries (< 5s target).
    """
    query = state.get("query", "")
    logger.info(f"Simple search for: {query[:100]}")

    try:
        raw_results = await asyncio.wait_for(
            agentic_search(query=query, max_results=5),
            timeout=settings.query_timeout_simple,
        )

        web_results: List[SourceResult] = []
        for result in raw_results:
            web_results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", ""),
                "content": result.get("snippet", ""),
                "source_type": "web",
                "authors": [],
                "published": "",
                "metadata": {},
            })

        logger.info(f"Simple search returned {len(web_results)} results")
        return {
            "web_results": web_results,
            "current_phase": "searched",
        }

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
    """
    Parallel multi-source search for research-level queries.
    Searches web, arXiv, and YouTube concurrently (5-15s target).
    """
    query = state.get("query", "")
    required_sources = state.get("requires_sources", ["web"])
    logger.info(f"Research search for: {query[:100]}, sources: {required_sources}")

    errors = list(state.get("errors", []))

    # Per-source timeout: 60% of the overall research timeout
    per_source_timeout = settings.query_timeout_research * 0.6

    # Build list of search coroutines to run in parallel with timeouts
    tasks = {}

    if "web" in required_sources:
        tasks["web"] = asyncio.wait_for(_search_web(query), timeout=per_source_timeout)

    if "arxiv" in required_sources:
        tasks["arxiv"] = asyncio.wait_for(_search_arxiv(query), timeout=per_source_timeout)

    if "youtube" in required_sources:
        tasks["youtube"] = asyncio.wait_for(_search_youtube(query), timeout=per_source_timeout)

    # Execute all searches in parallel
    results_map = {}
    if tasks:
        task_items = list(tasks.items())
        coroutines = [item[1] for item in task_items]
        names = [item[0] for item in task_items]

        gathered = await asyncio.gather(*coroutines, return_exceptions=True)

        for name, result in zip(names, gathered):
            if isinstance(result, Exception):
                logger.error(f"{name} search failed: {result}")
                errors.append(f"{name} search failed: {str(result)}")
                results_map[name] = []
            else:
                results_map[name] = result

    web_results = results_map.get("web", [])
    academic_results = results_map.get("arxiv", [])
    youtube_results = results_map.get("youtube", [])

    logger.info(f"Research search totals: web={len(web_results)}, arxiv={len(academic_results)}, youtube={len(youtube_results)}")

    return {
        "web_results": web_results,
        "academic_results": academic_results,
        "youtube_results": youtube_results,
        "current_phase": "searched",
        "errors": errors,
    }


async def _search_web(query: str) -> List[SourceResult]:
    """Search DuckDuckGo for general web results."""
    try:
        raw_results = await agentic_search(query=query, max_results=10)
        results: List[SourceResult] = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("snippet", ""),
                "content": r.get("snippet", ""),
                "source_type": "web",
                "authors": [],
                "published": "",
                "metadata": {},
            })
        return results
    except Exception as e:
        logger.error(f"Web search error: {e}")
        raise


async def _search_arxiv(query: str) -> List[SourceResult]:
    """Search arXiv for academic papers."""
    try:
        from app.services.sources.arxiv_source import search_arxiv
        papers = await search_arxiv(query=query, max_results=5)
        results: List[SourceResult] = []
        for paper in papers:
            results.append({
                "title": paper.get("title", ""),
                "url": paper.get("pdf_url", ""),
                "snippet": paper.get("summary", "")[:500],
                "content": paper.get("summary", ""),
                "source_type": "arxiv",
                "authors": paper.get("authors", []),
                "published": paper.get("published", ""),
                "metadata": {
                    "arxiv_id": paper.get("arxiv_id", ""),
                    "categories": paper.get("categories", []),
                },
            })
        return results
    except ImportError:
        logger.warning("arxiv package not installed, skipping arXiv search")
        return []
    except Exception as e:
        logger.error(f"arXiv search error: {e}")
        raise


async def _search_youtube(query: str) -> List[SourceResult]:
    """Search YouTube for video results with transcripts."""
    try:
        from app.services.sources.youtube_source import search_youtube
        videos = await search_youtube(query=query, max_results=3)
        results: List[SourceResult] = []
        for video in videos:
            results.append({
                "title": video.get("title", ""),
                "url": video.get("url", ""),
                "snippet": video.get("description", "")[:300],
                "content": video.get("transcript", video.get("description", ""))[:2000],
                "source_type": "youtube",
                "authors": [video.get("channel", "")],
                "published": video.get("published", ""),
                "metadata": {
                    "video_id": video.get("video_id", ""),
                    "channel": video.get("channel", ""),
                },
            })
        return results
    except ImportError:
        logger.warning("YouTube packages not installed, skipping YouTube search")
        return []
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        raise
