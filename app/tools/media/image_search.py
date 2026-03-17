"""
Image Search Tool — Search royalty-free images via DuckDuckGo Images.
Free, no API key. Returns image URLs, dimensions, and source info.
"""

import json
import logging
import asyncio

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


@nurav_tool(metadata=ToolMetadata(
    name="image_search",
    description="Search for images from the web. Returns image URLs, thumbnails, dimensions, and source information. Great for finding reference images.",
    niche="media",
    status=ToolStatus.ACTIVE,
    icon="image-plus",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "mountain landscape sunset", "max_results": 5},
            output='[{"title": "...", "image_url": "...", "thumbnail": "...", "source": "...", "width": 1920, "height": 1080}]',
            description="Search for mountain landscape images",
        ),
    ],
    input_schema={"query": "str", "max_results": "int (default 10)", "size": "str ('Small'|'Medium'|'Large'|'Wallpaper')", "type_image": "str ('photo'|'clipart'|'gif'|'transparent')"},
    output_schema={"type": "array", "items": {"title": "str", "image_url": "str", "thumbnail": "str", "source": "str", "width": "int", "height": "int"}},
    avg_response_ms=2000,
    success_rate=0.92,
))
@tool
async def image_search(query: str, max_results: int = 10, size: str = "", type_image: str = "") -> str:
    """Search for images from the web."""
    try:
        from duckduckgo_search import DDGS

        def _search():
            with DDGS() as ddgs:
                kwargs = {"keywords": query, "max_results": min(max_results, 50)}
                if size:
                    kwargs["size"] = size
                if type_image:
                    kwargs["type_image"] = type_image
                return list(ddgs.images(**kwargs))

        raw = await asyncio.to_thread(_search)

        if not raw:
            return json.dumps({"results": [], "message": f"No images found for '{query}'."})

        results = []
        for item in raw:
            results.append({
                "title": item.get("title", ""),
                "image_url": item.get("image", ""),
                "thumbnail": item.get("thumbnail", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "width": item.get("width", 0),
                "height": item.get("height", 0),
            })

        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Image search failed: {str(e)}"})
