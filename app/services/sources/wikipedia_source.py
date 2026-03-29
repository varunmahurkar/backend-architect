"""Wikipedia Source Integration.
Fetches article summaries via the Wikipedia REST API (free, no key).
Ideal for factual / definition queries — returns intro section + key facts.
Called by: services/agents/nodes/searcher.py (research_search_node)."""

import asyncio
import logging
from typing import List, Dict
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"

_HEADERS = {
    "User-Agent": "NuravBot/1.0 (https://nurav.ai; contact@nurav.ai)",
    "Accept": "application/json",
}


async def search_wikipedia(query: str, max_results: int = 3) -> List[Dict]:
    """Search Wikipedia and return page summaries.

    Args:
        query: Search query string.
        max_results: Maximum number of articles to return (capped at 5).

    Returns:
        List of dicts: title, url, snippet, content, published_at, source_type.
    """
    max_results = min(max_results, 5)

    try:
        async with httpx.AsyncClient(timeout=6.0, headers=_HEADERS) as client:
            # Step 1: Full-text search to get article titles
            titles = await _search_titles(client, query, max_results)
            if not titles:
                return []

            # Step 2: Fetch summaries in parallel
            tasks = [_fetch_summary(client, title) for title in titles]
            summaries = await asyncio.gather(*tasks, return_exceptions=True)

        results: List[Dict] = []
        for item in summaries:
            if isinstance(item, Exception) or item is None:
                continue
            results.append(item)

        logger.info(f"Wikipedia returned {len(results)} articles for: {query[:60]!r}")
        return results

    except Exception as e:
        logger.error(f"Wikipedia search failed: {e}")
        return []


async def _search_titles(client: httpx.AsyncClient, query: str, limit: int) -> List[str]:
    """Use Wikipedia opensearch to get matching article titles."""
    try:
        resp = await client.get(
            _WIKI_SEARCH_URL,
            params={
                "action": "opensearch",
                "search": query,
                "limit": limit,
                "namespace": 0,
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        # opensearch returns [query, [titles], [descriptions], [urls]]
        return data[1] if len(data) > 1 else []
    except Exception as e:
        logger.warning(f"Wikipedia title search failed: {e}")
        return []


async def _fetch_summary(client: httpx.AsyncClient, title: str) -> Dict | None:
    """Fetch REST summary for a single article title."""
    try:
        url = _WIKI_SUMMARY_URL.format(title=quote(title, safe=""))
        resp = await client.get(url)
        if resp.status_code != 200:
            return None

        data = resp.json()
        page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        extract = data.get("extract", "")
        if not extract:
            return None

        return {
            "title": data.get("title", title),
            "url": page_url or f"https://en.wikipedia.org/wiki/{quote(title)}",
            "snippet": extract[:300],
            "content": extract[:3000],
            "source_type": "wikipedia",
            "authors": [],
            "published": "",            # Wikipedia doesn't expose article dates in summary API
            "published_at": "",
            "metadata": {
                "wiki_id": data.get("pageid", ""),
                "description": data.get("description", ""),
            },
        }
    except Exception as e:
        logger.warning(f"Wikipedia summary fetch failed for {title!r}: {e}")
        return None
