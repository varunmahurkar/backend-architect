"""
Quality Validator Tool — Wraps validators.py response validation
Validates that a response adequately addresses the user's query.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="quality_validator",
    description="Validate whether an AI response adequately addresses the user's query. Uses LLM-based relevance checking.",
    niche="analysis",
    status=ToolStatus.ACTIVE,
    icon="shield-check",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "What is Python?", "response_text": "Python is a programming language..."},
            output='{"relevant": true, "reason": "Response directly addresses the definition of Python"}',
            description="Validate a response about Python",
        ),
    ],
    input_schema={"query": "str", "response_text": "str"},
    output_schema={"relevant": "bool", "reason": "str"},
    avg_response_ms=1500,
    success_rate=0.93,
))
@tool
async def quality_validator(query: str, response_text: str) -> str:
    """Validate that an AI response adequately addresses the user's query. Returns relevance judgment."""
    from app.services.agents.validators import validate_response

    result = await validate_response(query=query, response_text=response_text)
    return json.dumps(result, ensure_ascii=False)
