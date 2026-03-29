"""News Source Integration.
Primary: NewsAPI.org (if NEWSAPI_KEY is set).
Fallback: DuckDuckGo news search (always free, no key needed).
Returns articles sorted by recency with publishedAt timestamps.
Called by: services/agents/nodes/searcher.py (research_search_node)."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

_NEWSAPI_URL = "https://newsapi.org/v2/everything"
_DDG_NEWS_URL = "https://duckduckgo.com/"

_HEADERS = {
    "User-Agent": "NuravBot/1.0 (https://nurav.ai)",
    "Accept": "application/json",
}


async def search_news(query: str, max_results: int = 5) -> List[Dict]:
    """Search for recent news articles.

    Tries NewsAPI first if key is configured, otherwise uses DuckDuckGo news
    which requires no API key and always works.

    Args:
        query: Search query string.
        max_results: Maximum number of articles to return.

    Returns:
        List of dicts: title, url, snippet, content, published_at, source_type.
    """
    max_results = min(max_results, 10)

    if settings.newsapi_key:
        results = await _search_newsapi(query, max_results)
        if results:
            return results

    # DuckDuckGo news fallback (always available)
    return await _search_ddg_news(query, max_results)


# ---------------------------------------------------------------------------
# NewsAPI backend
# ---------------------------------------------------------------------------

async def _search_newsapi(query: str, max_results: int) -> List[Dict]:
    """Fetch articles from NewsAPI.org."""
    try:
        async with httpx.AsyncClient(timeout=6.0, headers=_HEADERS) as client:
            resp = await client.get(
                _NEWSAPI_URL,
                params={
                    "q": query,
                    "sortBy": "publishedAt",
                    "pageSize": max_results,
                    "language": "en",
                    "apiKey": settings.newsapi_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        articles = data.get("articles", [])
        results: List[Dict] = []
        for article in articles[:max_results]:
            published_at = article.get("publishedAt", "")
            results.append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "snippet": article.get("description", "")[:300],
                "content": (article.get("description", "") + "\n" + article.get("content", ""))[:2000],
                "source_type": "news",
                "authors": [article.get("author", "")] if article.get("author") else [],
                "published": published_at,
                "published_at": published_at,
                "metadata": {
                    "source_name": article.get("source", {}).get("name", ""),
                    "image_url": article.get("urlToImage", ""),
                },
            })

        logger.info(f"NewsAPI returned {len(results)} articles for: {query[:60]!r}")
        return results

    except Exception as e:
        logger.warning(f"NewsAPI failed: {e}")
        return []


# ---------------------------------------------------------------------------
# DuckDuckGo news fallback (no API key)
# ---------------------------------------------------------------------------

async def _search_ddg_news(query: str, max_results: int) -> List[Dict]:
    """Fetch news via DuckDuckGo's undocumented news endpoint."""
    try:
        from duckduckgo_search import DDGS  # type: ignore[import]

        def _sync_search():
            with DDGS() as ddgs:
                return list(ddgs.news(query, max_results=max_results, region="wt-wt"))

        articles = await asyncio.to_thread(_sync_search)

        results: List[Dict] = []
        for article in articles[:max_results]:
            published_at = _normalise_date(article.get("date", ""))
            results.append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "snippet": article.get("body", "")[:300],
                "content": article.get("body", "")[:2000],
                "source_type": "news",
                "authors": [],
                "published": published_at,
                "published_at": published_at,
                "metadata": {
                    "source_name": article.get("source", ""),
                    "image_url": article.get("image", ""),
                },
            })

        logger.info(f"DDG news returned {len(results)} articles for: {query[:60]!r}")
        return results

    except Exception as e:
        logger.error(f"DDG news search failed: {e}")
        return []


def _normalise_date(raw: str) -> str:
    """Attempt to return ISO 8601 string from various date formats."""
    if not raw:
        return ""
    try:
        # DDG returns relative strings like "1 hour ago" or ISO timestamps
        if "ago" in raw.lower() or "hour" in raw.lower() or "minute" in raw.lower():
            return datetime.now(timezone.utc).isoformat()
        # Try parsing as ISO
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.isoformat()
    except Exception:
        return raw
