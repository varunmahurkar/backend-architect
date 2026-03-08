"""
Image Analyzer Tool — Gemini Vision for AI analysis + Pillow for metadata.
Describes images, detects objects, extracts text via OCR.
"""

import json
import logging
import base64
from typing import Any

import httpx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _download_image(image_url: str) -> tuple[bytes, str]:
    """Download image and return (bytes, content_type)."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        resp = await client.get(image_url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        return resp.content, content_type


def _get_pillow_metadata(image_bytes: bytes) -> dict[str, Any]:
    """Extract image metadata using Pillow."""
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(image_bytes))
    return {
        "dimensions": {"width": img.width, "height": img.height},
        "format": img.format or "unknown",
        "mode": img.mode,
        "file_size_kb": round(len(image_bytes) / 1024, 1),
    }


async def _analyze_with_gemini(image_bytes: bytes, content_type: str, tasks: list[str]) -> dict[str, Any]:
    """Use Gemini Vision to analyze the image."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage
    from app.config.settings import settings

    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY not configured")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.google_api_key,
        temperature=0.3,
        max_output_tokens=1500,
    )

    # Build prompt based on tasks
    task_instructions = []
    if "describe" in tasks:
        task_instructions.append("1. Provide a detailed description of the image.")
    if "objects" in tasks:
        task_instructions.append("2. List the main objects/elements visible in the image.")
    if "ocr" in tasks:
        task_instructions.append("3. Extract any visible text in the image (OCR).")

    prompt = (
        "Analyze this image and respond in JSON format with these fields:\n"
        + "\n".join(task_instructions) + "\n\n"
        "Respond ONLY with valid JSON:\n"
        '{"description": "...", "objects": ["obj1", "obj2"], "text_detected": "any text found or empty string"}'
    )

    # Encode image for Gemini
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    mime = content_type.split(";")[0].strip()
    if "image" not in mime:
        mime = "image/jpeg"

    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_image}"}},
        ]
    )

    response = await llm.ainvoke([message])
    response_text = response.content.strip()

    # Parse JSON from response (handle markdown code blocks)
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    return json.loads(response_text)


@nurav_tool(metadata=ToolMetadata(
    name="image_analyzer",
    description="Analyze images using AI vision to generate descriptions, detect objects, and extract text via OCR. Powered by Gemini Vision.",
    niche="files",
    status=ToolStatus.ACTIVE,
    icon="image",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"image_url": "https://picsum.photos/400", "tasks": "describe,objects"},
            output='{"description": "A scenic landscape with mountains...", "objects": ["mountain", "sky", "trees"], "text_detected": "", "dimensions": {"width": 400, "height": 400}}',
            description="Analyze a random image",
        ),
    ],
    input_schema={"image_url": "str", "tasks": "str (comma-separated: describe,objects,ocr)"},
    output_schema={"description": "str", "objects": "array", "text_detected": "str", "dimensions": "dict", "format": "str", "file_size_kb": "float"},
    avg_response_ms=3000,
    success_rate=0.92,
))
@tool
async def image_analyzer(image_url: str, tasks: str = "describe,objects,ocr") -> str:
    """Analyze an image from a URL: describe contents, detect objects, and extract text via OCR."""
    task_list = [t.strip().lower() for t in tasks.split(",")]

    # Download image
    try:
        image_bytes, content_type = await _download_image(image_url)
    except httpx.TimeoutException:
        return json.dumps({"error": "Timeout downloading image."})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HTTP error {e.response.status_code} downloading image."})
    except Exception as e:
        return json.dumps({"error": f"Failed to download image: {str(e)}"})

    # Get Pillow metadata
    try:
        metadata = _get_pillow_metadata(image_bytes)
    except Exception as e:
        metadata = {"dimensions": {}, "format": "unknown", "file_size_kb": round(len(image_bytes) / 1024, 1)}
        logger.warning(f"Pillow metadata extraction failed: {e}")

    # AI analysis with Gemini
    try:
        ai_result = await _analyze_with_gemini(image_bytes, content_type, task_list)
    except Exception as e:
        logger.warning(f"Gemini Vision failed: {e}")
        # Return Pillow-only metadata as fallback
        return json.dumps({
            "description": "AI analysis unavailable. Image metadata extracted only.",
            "objects": [],
            "text_detected": "",
            **metadata,
            "method": "pillow_only",
            "ai_error": str(e),
        })

    # Merge AI results with Pillow metadata
    result = {
        "description": ai_result.get("description", ""),
        "objects": ai_result.get("objects", []),
        "text_detected": ai_result.get("text_detected", ""),
        **metadata,
        "method": "gemini_vision",
    }

    return json.dumps(result, ensure_ascii=False)
