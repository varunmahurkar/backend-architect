"""
Translator Tool — FUTURE: Multi-language translation.
Currently returns mock data demonstrating expected output format.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="translator",
    description="Translate text between languages with automatic source language detection.",
    niche="language",
    status=ToolStatus.COMING_SOON,
    icon="languages",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"text": "Hello world", "target_lang": "fr"},
            output='{"translated_text": "Bonjour le monde", "source_lang": "en", "target_lang": "fr"}',
            description="Translate English to French",
        ),
    ],
    input_schema={"text": "str", "target_lang": "str", "source_lang": "str (optional, auto-detect)"},
    output_schema={"translated_text": "str", "source_lang": "str", "target_lang": "str"},
    avg_response_ms=1000,
))
@tool
async def translator(text: str, target_lang: str = "fr", source_lang: str = "auto") -> str:
    """Translate text to a target language. Currently returns mock data (coming soon)."""
    return json.dumps({
        "translated_text": "Bonjour le monde",
        "source_lang": "en",
        "target_lang": target_lang,
        "note": "This tool is coming soon. Showing mock output.",
    })
