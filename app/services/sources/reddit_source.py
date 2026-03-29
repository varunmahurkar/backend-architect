"""Reddit Source Integration.
Uses Reddit's public JSON API (no authentication required for public posts).
Targets top posts + top comments from relevant subreddits to surface
community best-practices, opinions, and real-world experience.
Called by: services/agents/nodes/searcher.py (research_search_node for opinion/community intent)."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
_REDDIT_COMMENTS_URL = "https://www.reddit.com/comments/{post_id}.json"

_HEADERS = {
    "User-Agent": "NuravBot/1.0 (https://nurav.ai; educational research tool)",
    "Accept": "application/json",
}

# Subreddits to restrict search when topic-specific subs exist
_TOPIC_SUBREDDITS: Dict[str, str] = {
    "python": "r/python+r/learnpython",
    "javascript": "r/javascript+r/webdev",
    "machine learning": "r/MachineLearning+r/learnmachinelearning",
    "llm": "r/LocalLLaMA+r/MachineLearning",
    "finance": "r/personalfinance+r/investing",
    "health": "r/health+r/medicine",
}


async def search_reddit(query: str, max_results: int = 5) -> List[Dict]:
    """Search Reddit for relevant posts and top comments.

    Args:
        query: Search query string.
        max_results: Maximum number of post+comment bundles to return.

    Returns:
        List of dicts: title, url, snippet, content, published_at, source_type.
    """
    max_results = min(max_results, 8)

    try:
        async with httpx.AsyncClient(timeout=7.0, headers=_HEADERS, follow_redirects=True) as client:
            posts = await _search_posts(client, query, max_results)
            if not posts:
                return []

            # Fetch top comments for up to 3 posts concurrently
            comment_tasks = [_fetch_top_comments(client, post["post_id"]) for post in posts[:3]]
            comment_results = await asyncio.gather(*comment_tasks, return_exceptions=True)

        results: List[Dict] = []
        for idx, post in enumerate(posts):
            top_comments: List[str] = []
            if idx < len(comment_results) and not isinstance(comment_results[idx], Exception):
                top_comments = comment_results[idx]  # type: ignore[assignment]

            # Combine post selftext + top comments for rich content
            content_parts = [post["selftext"]] if post["selftext"] else []
            content_parts.extend(f"Comment: {c}" for c in top_comments[:3])
            content = "\n\n".join(content_parts)[:3000]

            snippet = post["selftext"][:300] or (top_comments[0][:200] if top_comments else "")

            results.append({
                "title": post["title"],
                "url": f"https://www.reddit.com{post['permalink']}",
                "snippet": snippet,
                "content": content or post["title"],
                "source_type": "reddit",
                "authors": [f"u/{post['author']}"] if post.get("author") else [],
                "published": post["published_at"],
                "published_at": post["published_at"],
                "metadata": {
                    "subreddit": post["subreddit"],
                    "score": post["score"],
                    "num_comments": post["num_comments"],
                    "post_id": post["post_id"],
                },
            })

        logger.info(f"Reddit returned {len(results)} posts for: {query[:60]!r}")
        return results

    except Exception as e:
        logger.error(f"Reddit search failed: {e}")
        return []


async def _search_posts(client: httpx.AsyncClient, query: str, limit: int) -> List[Dict]:
    """Search Reddit for posts matching the query."""
    try:
        resp = await client.get(
            _REDDIT_SEARCH_URL,
            params={
                "q": query,
                "sort": "relevance",
                "t": "year",          # past year for freshness
                "limit": limit * 2,   # fetch extra to filter low-quality
                "type": "link",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        posts: List[Dict] = []
        children = data.get("data", {}).get("children", [])
        for child in children:
            post = child.get("data", {})
            # Skip posts with low engagement or NSFW
            if post.get("score", 0) < 5 or post.get("over_18"):
                continue
            created_utc = post.get("created_utc", 0)
            published_at = (
                datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
                if created_utc else ""
            )
            posts.append({
                "title": post.get("title", ""),
                "selftext": (post.get("selftext", "") or "")[:1500],
                "permalink": post.get("permalink", ""),
                "author": post.get("author", ""),
                "subreddit": post.get("subreddit_name_prefixed", ""),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "post_id": post.get("id", ""),
                "published_at": published_at,
            })
            if len(posts) >= limit:
                break

        return posts

    except Exception as e:
        logger.warning(f"Reddit post search failed: {e}")
        return []


async def _fetch_top_comments(client: httpx.AsyncClient, post_id: str) -> List[str]:
    """Fetch top-level comments for a post, returning text of top 5."""
    if not post_id:
        return []
    try:
        url = _REDDIT_COMMENTS_URL.format(post_id=post_id)
        resp = await client.get(
            url,
            params={"sort": "top", "limit": 10, "depth": 1},
        )
        resp.raise_for_status()
        data = resp.json()

        # Reddit comments endpoint returns [post_listing, comments_listing]
        if len(data) < 2:
            return []

        comments: List[str] = []
        children = data[1].get("data", {}).get("children", [])
        for child in children:
            body = child.get("data", {}).get("body", "")
            score = child.get("data", {}).get("score", 0)
            # Skip deleted/removed comments and low-quality ones
            if body and body not in ("[deleted]", "[removed]") and score > 1:
                comments.append(body[:400])
            if len(comments) >= 5:
                break

        return comments

    except Exception as e:
        logger.debug(f"Reddit comments fetch failed for {post_id}: {e}")
        return []
