"""Paraphraser Tool — COMING SOON: Rewrite text in different tones."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="paraphraser",
    description="Rewrite text in different tones, styles, or complexity levels. Preserves meaning while changing expression.",
    niche="language",
    status=ToolStatus.COMING_SOON,
    icon="pen-line",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"text": "The experiment yielded statistically significant results.", "tone": "simple"},
            output='{"paraphrased": ["The experiment showed important results."], "original_tone": "academic", "target_tone": "simple"}',
            description="Simplify academic text",
        ),
    ],
    input_schema={"text": "str", "tone": "str ('formal'|'casual'|'academic'|'simple'|'technical')", "variations": "int (default 1)"},
    output_schema={"paraphrased": "array", "original_tone": "str", "target_tone": "str"},
    avg_response_ms=2000,
))
@tool
async def paraphraser(text: str, tone: str = "casual", variations: int = 1) -> str:
    """Rewrite text in a different tone. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Paraphraser is under development. Will use LLM with tone-specific prompts."})
