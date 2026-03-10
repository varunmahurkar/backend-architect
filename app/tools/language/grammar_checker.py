"""Grammar Checker Tool — COMING SOON: Check grammar, spelling, and style."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="grammar_checker",
    description="Check grammar, spelling, style, and clarity. Returns corrections with explanations and a readability score.",
    niche="language",
    status=ToolStatus.COMING_SOON,
    icon="spell-check",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"text": "Their going to the store tommorrow.", "language": "en"},
            output='{"corrected_text": "They\'re going to the store tomorrow.", "issues": [...], "readability": {"score": 85}}',
            description="Check grammar in a sentence",
        ),
    ],
    input_schema={"text": "str", "language": "str (default 'en')", "style": "str ('academic'|'business'|'casual'|'auto')", "check_types": "str ('grammar,spelling,style')"},
    output_schema={"corrected_text": "str", "issues": "array", "readability": "dict"},
    avg_response_ms=2000,
))
@tool
async def grammar_checker(text: str, language: str = "en", style: str = "auto") -> str:
    """Check grammar and spelling. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Grammar checker is under development. Will use LanguageTool API + LLM for style suggestions."})
