"""
YouTube Source Integration
Searches YouTube for relevant videos and optionally fetches transcripts.
Uses youtube-transcript-api for transcript extraction (no API key needed for transcripts).
Falls back to DuckDuckGo for video search if YouTube Data API key is unavailable.
"""

import logging
import asyncio
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


async def search_youtube(query: str, max_results: int = 3) -> List[Dict]:
    """
    Search YouTube for videos matching the query.

    Attempts YouTube Data API first, falls back to DuckDuckGo video search.
    Fetches transcripts for each video when available.

    Args:
        query: Search query string
        max_results: Maximum number of videos to return

    Returns:
        List of video dictionaries with title, url, channel, transcript, etc.
    """
    logger.info(f"Searching YouTube: '{query}' (max_results={max_results})")

    # Try YouTube Data API first
    videos = await _search_via_api(query, max_results)

    # Fallback to DuckDuckGo video search
    if not videos:
        videos = await _search_via_duckduckgo(query, max_results)

    # Fetch transcripts for found videos
    if videos:
        videos = await _enrich_with_transcripts(videos)

    logger.info(f"YouTube search returned {len(videos)} videos")
    return videos


async def _search_via_api(query: str, max_results: int) -> List[Dict]:
    """Search using YouTube Data API v3 (requires API key)."""
    try:
        from app.config.settings import settings
        if not settings.youtube_api_key:
            return []

        from googleapiclient.discovery import build

        def _sync_search():
            youtube = build("youtube", "v3", developerKey=settings.youtube_api_key)
            request = youtube.search().list(
                q=query,
                part="snippet",
                maxResults=max_results,
                type="video",
                relevanceLanguage="en",
            )
            return request.execute()

        response = await asyncio.to_thread(_sync_search)

        results = []
        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            snippet = item.get("snippet", {})
            results.append({
                "title": snippet.get("title", ""),
                "video_id": video_id,
                "channel": snippet.get("channelTitle", ""),
                "description": snippet.get("description", ""),
                "published": snippet.get("publishedAt", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "transcript": None,
                "source": "youtube",
            })
        return results

    except ImportError:
        logger.debug("google-api-python-client not installed")
        return []
    except Exception as e:
        logger.warning(f"YouTube API search failed: {e}")
        return []


async def _search_via_duckduckgo(query: str, max_results: int) -> List[Dict]:
    """Fallback: search YouTube via DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS

        def _sync_search():
            with DDGS() as ddgs:
                results = list(ddgs.videos(
                    f"site:youtube.com {query}",
                    max_results=max_results,
                ))
            return results

        raw_results = await asyncio.to_thread(_sync_search)

        results = []
        for r in raw_results:
            # Extract video ID from URL
            url = r.get("content", r.get("embed_url", ""))
            video_id = _extract_video_id(url)
            if not video_id:
                continue

            results.append({
                "title": r.get("title", ""),
                "video_id": video_id,
                "channel": r.get("publisher", ""),
                "description": r.get("description", ""),
                "published": r.get("published", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "transcript": None,
                "source": "youtube",
            })
        return results

    except Exception as e:
        logger.warning(f"DuckDuckGo video search failed: {e}")
        return []


async def _enrich_with_transcripts(videos: List[Dict]) -> List[Dict]:
    """Fetch transcripts for YouTube videos using youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        logger.debug("youtube-transcript-api not installed, skipping transcripts")
        return videos

    async def _fetch_transcript(video: Dict) -> Dict:
        video_id = video.get("video_id", "")
        if not video_id:
            return video
        try:
            def _sync_transcript():
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
                return " ".join([t["text"] for t in transcript_data])

            transcript = await asyncio.to_thread(_sync_transcript)
            video["transcript"] = transcript[:5000]  # Cap transcript length
        except Exception as e:
            logger.debug(f"Transcript unavailable for {video_id}: {e}")
            video["transcript"] = None
        return video

    # Fetch transcripts in parallel
    enriched = await asyncio.gather(*[_fetch_transcript(v) for v in videos])
    return list(enriched)


def _extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    if not url:
        return None
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)

        if "youtube.com" in parsed.netloc:
            qs = parse_qs(parsed.query)
            return qs.get("v", [None])[0]
        elif "youtu.be" in parsed.netloc:
            return parsed.path.lstrip("/")
        elif "youtube.com/embed/" in url:
            return parsed.path.split("/embed/")[-1].split("?")[0]
    except Exception:
        pass
    return None
