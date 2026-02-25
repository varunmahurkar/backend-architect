"""
Image Analyzer Tool — FUTURE: Image description and OCR.
Currently returns mock data demonstrating expected output format.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="image_analyzer",
    description="Analyze images to generate descriptions, detect objects, and extract text via OCR.",
    niche="files",
    status=ToolStatus.COMING_SOON,
    icon="image",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"image_url": "https://example.com/photo.jpg"},
            output='{"description": "A photo of a cat sitting on a table", "objects": ["cat", "table"], "text_detected": ""}',
            description="Analyze an image",
        ),
    ],
    input_schema={"image_url": "str"},
    output_schema={"description": "str", "objects": "array", "text_detected": "str"},
    avg_response_ms=2000,
))
@tool
async def image_analyzer(image_url: str) -> str:
    """Analyze an image to describe its contents and detect objects/text. Currently returns mock data (coming soon)."""
    return json.dumps({
        "description": "A photo of a cat sitting on a wooden table near a window",
        "objects": ["cat", "table", "window"],
        "text_detected": "",
        "note": "This tool is coming soon. Showing mock output.",
    })
