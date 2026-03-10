"""Image Search Tool — COMING SOON: Search royalty-free images."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="image_search",
    description="Search for royalty-free images from Unsplash and Pexels. Returns image URLs, photographer credits, and dimensions.",
    niche="media",
    status=ToolStatus.COMING_SOON,
    icon="image-plus",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"query": "mountain landscape", "max_results": 5},
            output='[{"url": "...", "thumbnail": "...", "photographer": "...", "source": "unsplash"}]',
            description="Search for mountain landscape images",
        ),
    ],
    input_schema={"query": "str", "max_results": "int (default 5)", "orientation": "str ('landscape'|'portrait'|'squarish')", "source": "str ('unsplash'|'pexels'|'both')"},
    output_schema={"type": "array", "items": {"url": "str", "thumbnail": "str", "photographer": "str", "source": "str", "width": "int", "height": "int"}},
    avg_response_ms=2000,
))
@tool
async def image_search(query: str, max_results: int = 5, orientation: str = "landscape", source: str = "both") -> str:
    """Search for royalty-free images. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Image search is under development. Will use Unsplash + Pexels APIs."})
